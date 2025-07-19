# --- Standard libraries ---
import os
import logging
from typing import Optional, Dict, Any, List

# --- Third-party libraries ---
# Удаляем aiofiles, так как больше не нужен для работы с файлами

# --- Internal modules ---
from services.database import get_user_data, update_user_data, get_user_profiles

logger = logging.getLogger(__name__)

CURRENCY = 'XTR'
VERSION = '1.0.0'
# Удаляем CONFIG_PATH, так как больше не используем файл
DEV_MODE = False # Purchase of test gifts
MAX_PROFILES = 3 # Maximum message length is 4096 characters
PURCHASE_COOLDOWN = 0.3 # Number of purchases per second
USERBOT_UPDATE_COOLDOWN = 50 # Base waiting time in seconds for requesting gift list through userbot

def add_allowed_user(user_id):
    # В публичном режиме эта функция ничего не делает
    pass

def DEFAULT_PROFILE(user_id: int) -> dict:
    """Creates a profile with default settings for the specified user."""
    return {
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

# Заменяем старые функции на новые, работающие с Supabase

async def get_valid_config(user_id: int) -> dict:
    """
    Получает данные пользователя из Supabase.
    Сохраняется для обратной совместимости со старым кодом.
    """
    user_data = await get_user_data(user_id)
    profiles = await get_user_profiles(user_id)
    
    # Получаем данные юзербота из отдельной таблицы
    from services.database import get_user_userbot_data
    userbot_data = await get_user_userbot_data(user_id)
    
    # Преобразуем данные из Supabase в формат, совместимый со старыми функциями
    config = {
        "BALANCE": user_data.get("balance", 0),
        "ACTIVE": user_data.get("active", False),
        "LAST_MENU_MESSAGE_ID": user_data.get("last_menu_message_id"),
        "PROFILES": profiles if profiles else [DEFAULT_PROFILE(user_id)],
        "USERBOT": {
            "API_ID": userbot_data.get("api_id") if userbot_data else None,
            "API_HASH": userbot_data.get("api_hash") if userbot_data else None,
            "PHONE": userbot_data.get("phone") if userbot_data else None,
            "USER_ID": userbot_data.get("user_id") if userbot_data else None,
            "USERNAME": userbot_data.get("username") if userbot_data else None,
            "BALANCE": user_data.get("userbot_balance", 0),  # Баланс юзербота хранится в users
            "ENABLED": userbot_data.get("enabled", False) if userbot_data else False
        }
    }
    return config

async def save_config(config: dict):
    """
    Сохраняет конфигурацию в Supabase.
    Сохраняется для обратной совместимости со старым кодом.
    """
    if not config:
        logger.error("Попытка сохранения пустой конфигурации")
        return
    
    # Получаем user_id из первого профиля (предполагаем, что он всегда есть)
    profiles = config.get("PROFILES", [])
    if not profiles:
        logger.error("Нет профилей в конфигурации")
        return
    
    profile = profiles[0]
    user_id = profile.get("user_id") or profile.get("TARGET_USER_ID")
    if not user_id:
        logger.error("Не удалось определить user_id")
        return
    
    # Обновляем основные данные пользователя
    user_data = {
        "balance": config.get("BALANCE", 0),
        "active": config.get("ACTIVE", False),
        "last_menu_message_id": config.get("LAST_MENU_MESSAGE_ID"),
        "userbot_balance": config.get("USERBOT", {}).get("BALANCE", 0)  # Баланс юзербота в users
    }
    
    # Обновляем данные пользователя в Supabase
    await update_user_data(user_id, user_data)
    
    # Обновляем данные юзербота в отдельной таблице
    userbot_data = config.get("USERBOT", {})
    if userbot_data:
        from services.database import update_user_userbot_data
        userbot_update_data = {
            "api_id": userbot_data.get("API_ID"),
            "api_hash": userbot_data.get("API_HASH"),
            "phone": userbot_data.get("PHONE"),
            "user_id": userbot_data.get("USER_ID"),
            "username": userbot_data.get("USERNAME"),
            "enabled": userbot_data.get("ENABLED", False)
        }
        await update_user_userbot_data(user_id, userbot_update_data)
    
    logger.info(f"Configuration saved in Supabase.")

async def format_supabase_summary(user_id: int) -> str:
    """
    Форматирует текст меню из данных Supabase
    """
    # Получаем данные пользователя и профили
    user_data = await get_user_data(user_id)
    profiles = await get_user_profiles(user_id)
    
    # Получаем основные данные
    balance = user_data.get("balance", 0)
    active = user_data.get("active", False)
    userbot_enabled = user_data.get("userbot_enabled", False)
    userbot_balance = user_data.get("userbot_balance", 0)
    
    logger.info(f"Formatting menu for user {user_id}: balance={balance}, active={active}, userbot_enabled={userbot_enabled}, userbot_balance={userbot_balance}")
    
    # Формируем текст
    status = "🟢 ACTIVE" if active else "🔴 INACTIVE"
    header = f"<b>★ BALANCE: {balance:,}</b> {CURRENCY}\n<b>STATUS: {status}</b>\n"
    
    # Информация о юзерботе
    if userbot_enabled:
        userbot_info = f"\n<b>🤖 USERBOT:</b> ✅ ACTIVE, ★{userbot_balance:,}"
    else:
        userbot_info = "\n<b>🤖 USERBOT:</b> ❌ DISABLED"
    
    # Информация о профилях
    profiles_info = "\n\n<b>📊 PROFILES:</b>\n"
    for i, profile in enumerate(profiles, 1):
        target_display = get_target_display(profile, user_id)
        done = profile.get("done", False)
        count = profile.get("count", 0)
        bought = profile.get("bought", 0)
        limit = profile.get("limit", 0)
        spent = profile.get("spent", 0)
        sender = profile.get("sender", "bot")
        
        status_emoji = "✅" if done else "⏳"
        sender_emoji = "👤" if sender == "bot" else "🤖"
        
        profiles_info += (
            f"{i}. {status_emoji} {sender_emoji} <b>{target_display}</b>\n"
            f"   {bought}/{count} gifts, {spent:,}/{limit:,} ★\n"
        )
    
    return header + userbot_info + profiles_info

# Остальные функции, которые не используют config.json, остаются без изменений

# Сохраняем функции для работы с профилями
def get_target_display(profile: dict, user_id: int) -> str:
    """
    Возвращает строку с описанием получателя подарка
    """
    target_user_id = profile.get("target_user_id")
    target_chat_id = profile.get("target_chat_id")
    return get_target_display_local(target_user_id, target_chat_id, user_id)

def get_target_display_local(target_user_id: Optional[int], target_chat_id: Optional[str], user_id: int) -> str:
    """
    Возвращает строку с описанием получателя подарка на основе ID или username
    """
    if target_user_id == user_id:
        return "yourself"
    elif target_user_id:
        return f"user {target_user_id}"
    elif target_chat_id:
        if target_chat_id.lstrip('-').isdigit():
            return f"chat {target_chat_id}"
        else:
            return f"@{target_chat_id.lstrip('@')}"
    else:
        return "unknown"

# Удаляем неиспользуемые функции load_config, ensure_config, validate_profile, validate_config,
# migrate_config_if_needed, add_profile, update_profile, remove_profile и др.

# Добавляем функции для работы с профилями, которые используются в handlers_wizard.py
async def add_profile(config: dict, profile_data: dict):
    """
    Добавляет новый профиль в конфигурацию пользователя.
    """
    user_id = profile_data.get("user_id")
    if not user_id:
        logger.error("user_id не указан в данных профиля")
        return False
    
    try:
        from services.database import add_user_profile
        result = await add_user_profile(user_id, profile_data)
        return result is not None
    except Exception as e:
        logger.error(f"Ошибка при добавлении профиля: {e}")
        return False

async def update_profile(config: dict, profile_index: int, profile_data: dict):
    """
    Обновляет профиль в конфигурации пользователя.
    """
    try:
        from services.database import get_user_profiles, update_user_profile
        
        user_id = profile_data.get("user_id")
        if not user_id:
            logger.error("user_id не указан в данных профиля")
            return False
        
        # Получаем профили пользователя
        profiles = await get_user_profiles(user_id)
        
        if profile_index >= len(profiles):
            logger.error(f"Индекс профиля {profile_index} превышает количество профилей")
            return False
        
        # Получаем ID профиля для обновления
        profile_id = profiles[profile_index].get("id")
        if not profile_id:
            logger.error("Не удалось получить ID профиля для обновления")
            return False
        
        result = await update_user_profile(profile_id, profile_data)
        return result is not None
    except Exception as e:
        logger.error(f"Ошибка при обновлении профиля: {e}")
        return False

async def remove_profile(config: dict, profile_index: int, user_id: int):
    """
    Удаляет профиль из конфигурации пользователя.
    """
    try:
        from services.database import get_user_profiles, delete_user_profile
        
        # Получаем профили пользователя
        profiles = await get_user_profiles(user_id)
        
        if profile_index >= len(profiles):
            logger.error(f"Индекс профиля {profile_index} превышает количество профилей")
            return False
        
        # Получаем ID профиля для удаления
        profile_id = profiles[profile_index].get("id")
        if not profile_id:
            logger.error("Не удалось получить ID профиля для удаления")
            return False
        
        result = await delete_user_profile(profile_id)
        return result
    except Exception as e:
        logger.error(f"Ошибка при удалении профиля: {e}")
        return False
