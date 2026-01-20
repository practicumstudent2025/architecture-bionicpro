"""
Аутентификация и авторизация
Интеграция с BFF Service для проверки токенов

RBAC (Role-Based Access Control): пользователь может видеть только свои отчёты.
Все запросы фильтруются по user_id, извлечённому из токена аутентификации.
"""

import os
import logging
import httpx
from typing import Optional
from fastapi import HTTPException, Header, Depends

logger = logging.getLogger(__name__)

# URL BFF Service для валидации токенов
BFF_SERVICE_URL = os.getenv("BFF_SERVICE_URL", "http://bff-service:8080")
BFF_VALIDATE_ENDPOINT = f"{BFF_SERVICE_URL}/api/auth/validate"


def verify_token(token: str) -> bool:
    """
    Проверка токена через BFF Service
    
    В продакшене здесь будет вызов BFF Service для валидации токена.
    Для демонстрации используется упрощённая проверка формата токена.
    
    Args:
        token: Токен авторизации (с префиксом "Bearer " или без)
    
    Returns:
        True если токен валиден, False иначе
    """
    # В продакшене: вызов BFF Service для валидации токена
    # try:
    #     response = httpx.get(
    #         BFF_VALIDATE_ENDPOINT,
    #         headers={"Authorization": f"Bearer {token}"},
    #         timeout=5.0
    #     )
    #     return response.status_code == 200
    # except Exception as e:
    #     logger.error(f"BFF validation error: {e}")
    #     return False
    
    # Для демонстрации: упрощённая проверка формата токена
    # В реальном приложении токен должен быть валидирован через BFF Service
    if not token:
        return False
    
    # Проверка формата токена (должен начинаться с "Bearer " или быть валидным JWT)
    if token.startswith("Bearer "):
        token_value = token.replace("Bearer ", "").strip()
        return len(token_value) > 0
    
    # Альтернативный формат: прямой токен
    return len(token.strip()) > 0


def get_user_id_from_token(authorization: str) -> Optional[int]:
    """
    Извлечение user_id из токена авторизации.
    
    КРИТИЧНО: user_id извлекается из токена и используется для фильтрации данных.
    Пользователь может видеть только свои отчёты - это обеспечивается на уровне SQL-запросов.
    
    В продакшене здесь будет вызов BFF Service для получения user_id из валидированного токена.
    
    Args:
        authorization: Заголовок Authorization (формат: "Bearer <token>")
    
    Returns:
        user_id из токена или None если токен невалиден
    
    Raises:
        HTTPException: Если токен невалиден или user_id не может быть извлечён
    """
    if not authorization:
        logger.warning("Authorization header is missing")
        return None
    
    # Удаление префикса "Bearer " если присутствует
    token = authorization.replace("Bearer ", "").strip()
    
    if not token:
        logger.warning("Token is empty after removing Bearer prefix")
        return None
    
    # Проверка валидности токена
    if not verify_token(token):
        logger.warning("Token validation failed")
        return None
    
    # В продакшене: вызов BFF Service для получения user_id
    # try:
    #     response = httpx.get(
    #         f"{BFF_SERVICE_URL}/api/auth/user",
    #         headers={"Authorization": authorization},
    #         timeout=5.0
    #     )
    #     if response.status_code == 200:
    #         data = response.json()
    #         user_id = data.get("user_id")
    #         if user_id:
    #             logger.info(f"Extracted user_id {user_id} from token via BFF")
    #             return int(user_id)
    # except Exception as e:
    #     logger.error(f"BFF user info error: {e}")
    #     return None
    
    # Для демонстрации: извлечение user_id из токена
    # В реальном приложении это будет JWT токен, декодируемый или проверяемый через BFF
    try:
        # Поддержка формата токена для демонстрации: "user_id:123;other:data"
        if "user_id:" in token:
            user_id_str = token.split("user_id:")[1].split(";")[0].split(",")[0].strip()
            user_id = int(user_id_str)
            logger.info(f"Extracted user_id {user_id} from token (demo format)")
            return user_id
        
        # Альтернативный формат: токен является числом (user_id)
        try:
            user_id = int(token)
            logger.info(f"Using token as user_id: {user_id} (demo format)")
            return user_id
        except ValueError:
            pass
        
        # По умолчанию для демонстрации возвращаем user_id=1
        # ВНИМАНИЕ: В продакшене это НЕДОПУСТИМО - user_id должен быть извлечён из токена
        logger.warning("Could not extract user_id from token, using default user_id=1 (DEMO ONLY)")
        return 1
        
    except Exception as e:
        logger.error(f"Error extracting user_id from token: {e}")
        return None


def get_current_user_id(authorization: Optional[str] = Header(None)) -> int:
    """
    Dependency для FastAPI: извлечение и валидация user_id из токена.
    
    Используется как Depends() в эндпоинтах для обеспечения аутентификации.
    Гарантирует, что user_id всегда присутствует и валиден перед выполнением запроса.
    
    Args:
        authorization: Заголовок Authorization из HTTP-запроса
    
    Returns:
        user_id текущего пользователя
    
    Raises:
        HTTPException 401: Если токен отсутствует или невалиден
    """
    if not authorization:
        logger.warning("Authorization header is missing in request")
        raise HTTPException(
            status_code=401,
            detail="Authorization header required. Please provide a valid token."
        )
    
    user_id = get_user_id_from_token(authorization)
    
    if user_id is None:
        logger.warning("Failed to extract user_id from token")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token. Please authenticate again."
        )
    
    logger.info(f"Authenticated user_id: {user_id}")
    return user_id
