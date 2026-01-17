"""
Reports API - Backend для сервиса отчётов
Возвращает отчёты из витрины ClickHouse
"""

from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.responses import JSONResponse
from typing import Optional, List
from datetime import date, datetime, timedelta
from pydantic import BaseModel
from clickhouse_driver import Client
import os
import logging

from app.database import get_clickhouse_client
from app.auth import verify_token, get_user_id_from_token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Reports API",
    description="API для получения отчётов о работе протезов",
    version="1.0.0"
)

# Модели данных
class ReportItem(BaseModel):
    """Элемент отчёта"""
    user_id: int
    prosthesis_id: int
    report_date: date
    report_hour: datetime
    movements_count: int
    battery_level_avg: float
    battery_level_min: float
    battery_level_max: float
    usage_hours: float
    avg_movements_per_hour: float
    peak_activity_hour: int
    crm_user_name: str
    crm_prosthesis_model: str
    crm_prosthesis_serial: str

class ReportResponse(BaseModel):
    """Ответ с отчётом"""
    user_id: int
    total_records: int
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    reports: List[ReportItem]
    summary: dict

class HealthResponse(BaseModel):
    """Статус здоровья API"""
    status: str
    clickhouse_connected: bool


@app.get("/health", response_model=HealthResponse)
async def health_check(client: Client = Depends(get_clickhouse_client)):
    """Проверка здоровья API и подключения к ClickHouse"""
    try:
        client.execute("SELECT 1")
        clickhouse_connected = True
    except Exception as e:
        logger.error(f"ClickHouse connection error: {e}")
        clickhouse_connected = False
    
    return HealthResponse(
        status="healthy" if clickhouse_connected else "degraded",
        clickhouse_connected=clickhouse_connected
    )


@app.get("/reports", response_model=ReportResponse)
async def get_reports(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    prosthesis_id: Optional[int] = None,
    authorization: Optional[str] = Header(None),
    client: Client = Depends(get_clickhouse_client)
):
    """
    Получение отчётов о работе протезов
    
    - **date_from**: Начальная дата (по умолчанию - последние 30 дней)
    - **date_to**: Конечная дата (по умолчанию - сегодня)
    - **prosthesis_id**: Фильтр по конкретному протезу (опционально)
    
    Требуется аутентификация через заголовок Authorization
    """
    # Аутентификация и получение user_id
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    try:
        # Проверка токена через BFF Service
        # В продакшене здесь будет вызов BFF для валидации токена
        user_id = get_user_id_from_token(authorization)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")
    
    # Установка дат по умолчанию
    if not date_to:
        date_to = date.today()
    if not date_from:
        date_from = date_to - timedelta(days=30)
    
    try:
        # Формирование запроса к ClickHouse
        # RBAC: фильтрация по user_id - пользователь видит только свои данные
        query_parts = [
            "SELECT user_id, prosthesis_id, report_date, report_hour,",
            "movements_count, battery_level_avg, battery_level_min, battery_level_max,",
            "usage_hours, avg_movements_per_hour, peak_activity_hour,",
            "crm_user_name, crm_prosthesis_model, crm_prosthesis_serial",
            "FROM reports_warehouse.prosthesis_usage_reports",
            f"WHERE user_id = {user_id}",
            f"AND report_date >= '{date_from}'",
            f"AND report_date <= '{date_to}'"
        ]
        
        # Добавление фильтра по протезу, если указан
        if prosthesis_id:
            query_parts.append(f"AND prosthesis_id = {prosthesis_id}")
        
        query_parts.append("ORDER BY report_date DESC, report_hour DESC LIMIT 1000")
        
        query = " ".join(query_parts)
        
        # Выполнение запроса
        result = client.execute(query)
        
        # Преобразование результатов
        reports = []
        for row in result:
            reports.append(ReportItem(
                user_id=row[0],
                prosthesis_id=row[1],
                report_date=row[2],
                report_hour=row[3],
                movements_count=row[4],
                battery_level_avg=row[5],
                battery_level_min=row[6],
                battery_level_max=row[7],
                usage_hours=row[8],
                avg_movements_per_hour=row[9],
                peak_activity_hour=row[10],
                crm_user_name=row[11] or "",
                crm_prosthesis_model=row[12] or "",
                crm_prosthesis_serial=row[13] or ""
            ))
        
        # Расчёт сводной статистики
        if reports:
            total_movements = sum(r.movements_count for r in reports)
            total_usage_hours = sum(r.usage_hours for r in reports)
            avg_battery = sum(r.battery_level_avg for r in reports) / len(reports)
            
            summary = {
                "total_movements": total_movements,
                "total_usage_hours": round(total_usage_hours, 2),
                "avg_battery_level": round(avg_battery, 2),
                "prostheses_count": len(set(r.prosthesis_id for r in reports)),
                "days_covered": len(set(r.report_date for r in reports))
            }
        else:
            summary = {
                "total_movements": 0,
                "total_usage_hours": 0,
                "avg_battery_level": 0,
                "prostheses_count": 0,
                "days_covered": 0
            }
        
        logger.info(f"Retrieved {len(reports)} reports for user {user_id}")
        
        return ReportResponse(
            user_id=user_id,
            total_records=len(reports),
            date_from=date_from,
            date_to=date_to,
            reports=reports,
            summary=summary
        )
        
    except Exception as e:
        logger.error(f"Error retrieving reports: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving reports: {str(e)}")


@app.get("/reports/summary")
async def get_reports_summary(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    authorization: Optional[str] = Header(None),
    client: Client = Depends(get_clickhouse_client)
):
    """
    Получение сводной статистики (использует материализованное представление)
    Быстрее, чем полный отчёт, так как использует предварительно агрегированные данные
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    try:
        user_id = get_user_id_from_token(authorization)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        raise HTTPException(status_code=401, detail="Authentication failed")
    
    if not date_to:
        date_to = date.today()
    if not date_from:
        date_from = date_to - timedelta(days=30)
    
    try:
        # Использование материализованного представления для быстрого доступа
        query = f"""
        SELECT 
            report_date,
            sum(total_movements) as total_movements,
            avg(avg_battery_level) as avg_battery,
            sum(total_usage_hours) as total_hours
        FROM reports_warehouse.daily_prosthesis_reports
        WHERE user_id = {user_id}
        AND report_date >= '{date_from}'
        AND report_date <= '{date_to}'
        GROUP BY report_date
        ORDER BY report_date DESC
        """
        
        result = client.execute(query)
        
        summary = []
        for row in result:
            summary.append({
                "date": row[0].isoformat() if isinstance(row[0], date) else str(row[0]),
                "total_movements": row[1],
                "avg_battery_level": round(row[2], 2),
                "total_usage_hours": round(row[3], 2)
            })
        
        return {"user_id": user_id, "daily_summary": summary}
        
    except Exception as e:
        logger.error(f"Error retrieving summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
