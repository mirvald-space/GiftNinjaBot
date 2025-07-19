# --- Standard libraries ---
import os
import logging
from typing import Dict, Any, Optional, List, Union

# --- Third-party libraries ---
from supabase import create_client, Client
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv(override=False)

# Получение URL и ключа Supabase из переменных окружения
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Глобальный клиент Supabase
_supabase_client = None

def get_supabase_client() -> Client:
    """
    Получение клиента Supabase (синглтон)
    """
    global _supabase_client
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL и SUPABASE_KEY должны быть указаны в .env файле")
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client

async def get_user_data(user_id: Optional[int]) -> Dict[str, Any]:
    """
    Получение данных пользователя из базы данных.
    Если пользователя нет, создается новая запись.
    Если user_id равен None, возвращаются данные по умолчанию.
    """
    if user_id is None:
        return {
            "user_id": None,
            "balance": 0,
            "active": False,
            "last_menu_message_id": None,
            "userbot_enabled": False,
            "userbot_balance": 0
        }
        
    try:
        supabase = get_supabase_client()
        
        # Проверяем, существует ли пользователь
        response = supabase.table("users").select("*").eq("user_id", user_id).execute()
        
        # Если пользователь не найден, создаем нового
        if len(response.data) == 0:
            # Создаем нового пользователя с начальными данными
            new_user = {
                "user_id": user_id,
                "balance": 0,
                "active": False,
                "last_menu_message_id": None,
                "userbot_enabled": False,
                "userbot_balance": 0
            }
            
            response = supabase.table("users").insert(new_user).execute()
            return response.data[0]
        
        return response.data[0]
    except Exception as e:
        logger.error(f"Ошибка при получении данных пользователя: {e}")
        # Возвращаем данные по умолчанию в случае ошибки
        return {
            "user_id": user_id,
            "balance": 0,
            "active": False,
            "last_menu_message_id": None,
            "userbot_enabled": False,
            "userbot_balance": 0
        }

async def update_user_data(user_id: int, data: Dict[str, Any]) -> Union[Dict[str, Any], None]:
    """
    Обновление данных пользователя в базе данных.
    """
    try:
        supabase = get_supabase_client()
        
        # Обновляем данные пользователя
        response = supabase.table("users").update(data).eq("user_id", user_id).execute()
        
        if len(response.data) == 0:
            # Если пользователь не найден, создаем нового
            data["user_id"] = user_id
            response = supabase.table("users").insert(data).execute()
        
        return response.data[0]
    except Exception as e:
        logger.error(f"Ошибка при обновлении данных пользователя: {e}")
        return None

async def get_user_profiles(user_id: int) -> List[Dict[str, Any]]:
    """
    Получение профилей пользователя из базы данных.
    """
    try:
        supabase = get_supabase_client()
        
        # Получаем профили пользователя
        response = supabase.table("profiles").select("*").eq("user_id", user_id).execute()
        
        # Если профилей нет, создаем один по умолчанию
        if len(response.data) == 0:
            default_profile = {
                "user_id": user_id,
                "name": None,
                "min_price": 5000,
                "max_price": 10000,
                "min_supply": 1000,
                "max_supply": 10000,
                "limit": 1000000,
                "count": 5,
                "target_user_id": user_id,
                "target_chat_id": None,
                "target_type": None,
                "sender": "bot",
                "bought": 0,
                "spent": 0,
                "done": False
            }
            
            response = supabase.table("profiles").insert(default_profile).execute()
        
        return response.data
    except Exception as e:
        logger.error(f"Ошибка при получении профилей пользователя: {e}")
        # Возвращаем профиль по умолчанию в случае ошибки
        return [{
            "user_id": user_id,
            "name": None,
            "min_price": 5000,
            "max_price": 10000,
            "min_supply": 1000,
            "max_supply": 10000,
            "limit": 1000000,
            "count": 5,
            "target_user_id": user_id,
            "target_chat_id": None,
            "target_type": None,
            "sender": "bot",
            "bought": 0,
            "spent": 0,
            "done": False
        }]

async def add_user_profile(user_id: int, profile_data: Dict[str, Any]) -> Union[Dict[str, Any], None]:
    """
    Добавление нового профиля пользователя.
    """
    try:
        supabase = get_supabase_client()
        
        # Добавляем user_id к данным профиля
        profile_data["user_id"] = user_id
        
        # Создаем новый профиль
        response = supabase.table("profiles").insert(profile_data).execute()
        
        return response.data[0]
    except Exception as e:
        logger.error(f"Ошибка при добавлении профиля пользователя: {e}")
        return None

async def update_user_profile(profile_id: int, profile_data: Dict[str, Any]) -> Union[Dict[str, Any], None]:
    """
    Обновление профиля пользователя.
    """
    try:
        supabase = get_supabase_client()
        
        # Обновляем профиль
        response = supabase.table("profiles").update(profile_data).eq("id", profile_id).execute()
        
        return response.data[0]
    except Exception as e:
        logger.error(f"Ошибка при обновлении профиля пользователя: {e}")
        return None

async def delete_user_profile(profile_id: int) -> bool:
    """
    Удаление профиля пользователя.
    """
    try:
        supabase = get_supabase_client()
        
        # Удаляем профиль
        response = supabase.table("profiles").delete().eq("id", profile_id).execute()
        
        return len(response.data) > 0
    except Exception as e:
        logger.error(f"Ошибка при удалении профиля пользователя: {e}")
        return False

async def get_user_balance(user_id: int) -> int:
    """
    Получение баланса пользователя.
    """
    try:
        user_data = await get_user_data(user_id)
        return user_data.get("balance", 0)
    except Exception as e:
        logger.error(f"Ошибка при получении баланса пользователя: {e}")
        return 0

async def update_user_balance(user_id: int, delta: int) -> int:
    """
    Обновление баланса пользователя на указанную дельту.
    """
    try:
        user_data = await get_user_data(user_id)
        current_balance = user_data.get("balance", 0)
        new_balance = max(0, current_balance + delta)
        
        await update_user_data(user_id, {"balance": new_balance})
        
        return new_balance
    except Exception as e:
        logger.error(f"Ошибка при обновлении баланса пользователя: {e}")
        return 0

async def get_user_userbot_balance(user_id: int) -> int:
    """
    Получение баланса юзербота пользователя.
    """
    try:
        user_data = await get_user_data(user_id)
        return user_data.get("userbot_balance", 0)
    except Exception as e:
        logger.error(f"Ошибка при получении баланса юзербота пользователя: {e}")
        return 0

async def update_user_userbot_balance(user_id: int, delta: int) -> int:
    """
    Обновление баланса юзербота пользователя на указанную дельту.
    """
    try:
        user_data = await get_user_data(user_id)
        current_balance = user_data.get("userbot_balance", 0)
        new_balance = max(0, current_balance + delta)
        
        await update_user_data(user_id, {"userbot_balance": new_balance})
        
        return new_balance
    except Exception as e:
        logger.error(f"Ошибка при обновлении баланса юзербота пользователя: {e}")
        return 0

async def get_user_userbot_data(user_id: int) -> Union[Dict[str, Any], None]:
    """
    Получение данных юзербота пользователя из таблицы userbots.
    """
    try:
        supabase = get_supabase_client()
        
        # Получаем данные юзербота из таблицы userbots
        response = supabase.table("userbots").select("*").eq("user_id", user_id).execute()
        
        if len(response.data) == 0:
            # Если записи нет, возвращаем None
            return None
        
        userbot_data = response.data[0]
        return {
            "api_id": userbot_data.get("api_id"),
            "api_hash": userbot_data.get("api_hash"),
            "phone": userbot_data.get("phone"),
            "user_id": userbot_data.get("user_id"),
            "username": userbot_data.get("username"),
            "balance": 0,  # Баланс юзербота хранится в таблице users
            "enabled": userbot_data.get("enabled", False)
        }
    except Exception as e:
        logger.error(f"Ошибка при получении данных юзербота пользователя: {e}")
        return None

async def update_user_userbot_data(user_id: int, data: Dict[str, Any]) -> Union[Dict[str, Any], None]:
    """
    Обновление данных юзербота пользователя в таблице userbots.
    """
    try:
        supabase = get_supabase_client()
        
        # Подготавливаем данные для таблицы userbots
        userbot_data = {
            "user_id": user_id,
            "api_id": data.get("api_id"),
            "api_hash": data.get("api_hash"),
            "phone": data.get("phone"),
            "username": data.get("username"),
            "enabled": data.get("enabled", False)
        }
        
        # Проверяем, существует ли запись юзербота
        response = supabase.table("userbots").select("*").eq("user_id", user_id).execute()
        
        if len(response.data) == 0:
            # Создаем новую запись
            response = supabase.table("userbots").insert(userbot_data).execute()
        else:
            # Обновляем существующую запись
            response = supabase.table("userbots").update(userbot_data).eq("user_id", user_id).execute()
        
        if response.data:
            result = response.data[0]
            return {
                "api_id": result.get("api_id"),
                "api_hash": result.get("api_hash"),
                "phone": result.get("phone"),
                "user_id": result.get("user_id"),
                "username": result.get("username"),
                "balance": 0,  # Баланс юзербота хранится в таблице users
                "enabled": result.get("enabled", False)
            }
        return None
    except Exception as e:
        logger.error(f"Ошибка при обновлении данных юзербота пользователя: {e}")
        return None 