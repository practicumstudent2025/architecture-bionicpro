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
from app.auth import get_current_user_id

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
    user_id: int = Depends(get_current_user_id),  # RBAC: user_id извлекается из токена
    client: Client = Depends(get_clickhouse_client)
):
    """
    Получение отчётов о работе протезов.
    
    RBAC (Role-Based Access Control): пользователь может видеть только свои отчёты.
    user_id автоматически извлекается из токена аутентификации и используется для фильтрации данных.
    
    - **date_from**: Начальная дата (по умолчанию - последние 30 дней)
    - **date_to**: Конечная дата (по умолчанию - сегодня)
    - **prosthesis_id**: Фильтр по конкретному протезу (опционально)
    
    Требуется аутентификация через заголовок Authorization: Bearer <token>
    
    Security:
        - Все запросы фильтруются по user_id из токена
        - Пользователь не может запросить отчёты другого пользователя
        - Фильтрация происходит на уровне SQL-запроса к ClickHouse
    """
    # user_id уже извлечён и валидирован через dependency get_current_user_id
    # Это гарантирует, что пользователь аутентифицирован и может видеть только свои данные
    
    # Установка дат по умолчанию
    if not date_to:
        date_to = date.today()
    if not date_from:
        date_from = date_to - timedelta(days=30)
    
    try:
        # Формирование запроса к ClickHouse
        # КРИТИЧНО: RBAC фильтрация по user_id - пользователь видит ТОЛЬКО свои данные
        # user_id берётся из токена аутентификации, а не из параметров запроса
        # Это предотвращает попытки запросить данные другого пользователя
        query_parts = [
            "SELECT user_id, prosthesis_id, report_date, report_hour,",
            "movements_count, battery_level_avg, battery_level_min, battery_level_max,",
            "usage_hours, avg_movements_per_hour, peak_activity_hour,",
            "crm_user_name, crm_prosthesis_model, crm_prosthesis_serial",
            "FROM reports_warehouse.prosthesis_usage_reports",
            f"WHERE user_id = {user_id}",  # RBAC: фильтрация по user_id из токена
            f"AND report_date >= '{date_from}'",
            f"AND report_date <= '{date_to}'"
        ]
        
        # Добавление фильтра по протезу, если указан
        # Важно: фильтр применяется только к протезам текущего пользователя
        if prosthesis_id:
            query_parts.append(f"AND prosthesis_id = {prosthesis_id}")
        
        query_parts.append("ORDER BY report_date DESC, report_hour DESC LIMIT 1000")
        
        query = " ".join(query_parts)
        
        logger.info(f"Executing query for user_id={user_id}, date_from={date_from}, date_to={date_to}")
        
        # Выполнение запроса
        result = client.execute(query)
        
        # Преобразование результатов
        # ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА БЕЗОПАСНОСТИ: валидация, что все данные принадлежат текущему пользователю
        # Это защита от потенциальных ошибок в SQL-запросе или манипуляций с данными
        reports = []
        for row in result:
            row_user_id = row[0]
            
            # RBAC проверка: убеждаемся, что user_id в строке совпадает с user_id из токена
            # Это дополнительный уровень защиты на случай ошибок в запросе
            if row_user_id != user_id:
                logger.warning(
                    f"SECURITY WARNING: Row user_id ({row_user_id}) != authenticated user_id ({user_id}). "
                    f"Skipping row to prevent data leakage."
                )
                continue  # Пропускаем строки, которые не принадлежат текущему пользователю
            
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
    user_id: int = Depends(get_current_user_id),  # RBAC: user_id извлекается из токена
    client: Client = Depends(get_clickhouse_client)
):
    """
    Получение сводной статистики (использует материализованное представление).
    
    Быстрее, чем полный отчёт, так как использует предварительно агрегированные данные.
    
    RBAC (Role-Based Access Control): пользователь может видеть только свою статистику.
    user_id автоматически извлекается из токена аутентификации.
    
    Security:
        - Все запросы фильтруются по user_id из токена
        - Пользователь не может запросить статистику другого пользователя
    """
    # user_id уже извлечён и валидирован через dependency get_current_user_id
    
    if not date_to:
        date_to = date.today()
    if not date_from:
        date_from = date_to - timedelta(days=30)
    
    try:
        # Использование материализованного представления для быстрого доступа
        # КРИТИЧНО: RBAC фильтрация по user_id - пользователь видит ТОЛЬКО свою статистику
        query = f"""
        SELECT 
            report_date,
            sum(total_movements) as total_movements,
            avg(avg_battery_level) as avg_battery,
            sum(total_usage_hours) as total_hours
        FROM reports_warehouse.daily_prosthesis_reports
        WHERE user_id = {user_id}  -- RBAC: фильтрация по user_id из токена
        AND report_date >= '{date_from}'
        AND report_date <= '{date_to}'
        GROUP BY report_date
        ORDER BY report_date DESC
        """
        
        logger.info(f"Executing summary query for user_id={user_id}, date_from={date_from}, date_to={date_to}")
        
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
