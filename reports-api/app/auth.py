"""
Аутентификация и авторизация
Интеграция с BFF Service для проверки токенов
"""

import os
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

# URL BFF Service для валидации токенов
BFF_SERVICE_URL = os.getenv("BFF_SERVICE_URL", "http://bff-service:8080")
BFF_VALIDATE_ENDPOINT = f"{BFF_SERVICE_URL}/api/auth/validate"


def verify_token(token: str) -> bool:
    """
    Проверка токена через BFF Service
    
    В продакшене здесь будет вызов BFF Service для валидации токена
    Для демонстрации используется упрощённая проверка
    """
    # В продакшене: вызов BFF Service
    # try:
    #     response = httpx.get(
    #         BFF_VALIDATE_ENDPOINT,
    #         headers={"Authorization": token},
    #         timeout=5.0
    #     )
    #     return response.status_code == 200
    # except Exception as e:
    #     logger.error(f"BFF validation error: {e}")
    #     return False
    
    # Для демонстрации: упрощённая проверка
    # В реальном приложении токен должен быть валидирован через BFF
    if not token or not token.startswith("Bearer "):
        return False
    
    # Извлечение user_id из токена (для демонстрации)
    # В продакшене user_id будет возвращён BFF Service
    return True


def get_user_id_from_token(authorization: str) -> Optional[int]:
    """
    Извлечение user_id из токена авторизации
    
    В продакшене здесь будет вызов BFF Service для получения user_id
    """
    if not authorization:
        return None
    
    # Удаление префикса "Bearer "
    token = authorization.replace("Bearer ", "").strip()
    
    if not token:
        return None
    
    # Для демонстрации: извлечение user_id из токена
    # В продакшене: вызов BFF Service
    # try:
    #     response = httpx.get(
    #         f"{BFF_SERVICE_URL}/api/auth/user",
    #         headers={"Authorization": authorization},
    #         timeout=5.0
    #     )
    #     if response.status_code == 200:
    #         data = response.json()
    #         return data.get("user_id")
    # except Exception as e:
    #     logger.error(f"BFF user info error: {e}")
    #     return None
    
    # Для демонстрации: упрощённая логика
    # В реальном приложении токен должен быть JWT или проверен через BFF
    # Здесь извлекаем user_id из токена (для тестирования)
    try:
        # Если токен содержит user_id (для демонстрации)
        # В продакшене это будет JWT токен, декодируемый или проверяемый через BFF
        if "user_id:" in token:
            user_id_str = token.split("user_id:")[1].split(";")[0]
            return int(user_id_str)
        # По умолчанию для демонстрации возвращаем user_id=1
        # В продакшене это должно быть извлечено из токена
        return 1
    except Exception:
        logger.warning("Could not extract user_id from token, using default")
        return 1
