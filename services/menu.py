# --- Third-party libraries ---
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import Optional

# --- Internal modules ---
from services.config import format_supabase_summary
from services.database import get_user_data, update_user_data

async def update_last_menu_message_id(message_id: int, user_id: int):
    """
    Сохраняет id последнего сообщения с меню.
    
    Args:
        message_id: ID сообщения
        user_id: ID пользователя
    """
    await update_user_data(user_id, {"last_menu_message_id": message_id})


async def get_last_menu_message_id(user_id: Optional[int]):
    """
    Возвращает id последнего отправленного сообщения с меню.
    
    Args:
        user_id: ID пользователя
    """
    if user_id is None:
        return None
        
    user_data = await get_user_data(user_id)
    return user_data.get("last_menu_message_id")


def config_action_keyboard(active: bool) -> InlineKeyboardMarkup:
    """
    Генерирует inline-клавиатуру для меню с действиями.
    """
    toggle_text = "🔴 Disable" if active else "🟢 Enable"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=toggle_text, callback_data="toggle_active"),
            InlineKeyboardButton(text="✏️ Profiles", callback_data="profiles_menu")
        ],
        [
            InlineKeyboardButton(text="♻️ Reset", callback_data="reset_bought"),
            InlineKeyboardButton(text="⚙️ Userbot", callback_data="userbot_menu")
        ],
        [
            InlineKeyboardButton(text="💰 Top up", callback_data="deposit_menu"),
            InlineKeyboardButton(text="↩️ Withdraw", callback_data="refund_menu")
        ],
        [
            InlineKeyboardButton(text="🎏 Catalog", callback_data="catalog"),
            InlineKeyboardButton(text="❓ Help", callback_data="show_help")
        ]
    ])


async def update_menu(bot, chat_id: int, user_id: int, message_id: int):
    """
    Обновляет меню в чате: удаляет предыдущее и отправляет новое.
    """
    # Получаем данные пользователя из Supabase
    user_data = await get_user_data(user_id)
    active = user_data.get("active", False)
    
    # Формируем текст меню из данных Supabase
    menu_text = await format_supabase_summary(user_id)
    
    await delete_menu(bot=bot, chat_id=chat_id, user_id=user_id, current_message_id=message_id)
    await send_menu(bot=bot, chat_id=chat_id, text=menu_text, active=active, user_id=user_id)


async def delete_menu(bot, chat_id: int, user_id: int = None, current_message_id: int = None):
    """
    Удаляет последнее сообщение с меню, если оно отличается от текущего.
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
        user_id: ID пользователя (опционально)
        current_message_id: ID текущего сообщения (опционально)
    """
    if user_id is None:
        return
        
    last_menu_message_id = await get_last_menu_message_id(user_id)
    if last_menu_message_id and last_menu_message_id != current_message_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=last_menu_message_id)
        except TelegramBadRequest as e:
            error_text = str(e)
            if "message can't be deleted for everyone" in error_text:
                await bot.send_message(
                    chat_id,
                    "⚠️ The previous menu is outdated and cannot be deleted (more than 48 hours have passed). Use the current menu.\n"
                )
            elif "message to delete not found" in error_text:
                pass
            else:
                raise


async def send_menu(bot, chat_id: int, text: str, active: bool, user_id: int) -> int:
    """
    Отправляет новое меню в чат и обновляет id последнего сообщения.
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
        text: Текст меню
        active: Статус активности
        user_id: ID пользователя
    """
    sent = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=config_action_keyboard(active)
    )
    await update_last_menu_message_id(sent.message_id, user_id)
    return sent.message_id


def payment_keyboard(amount):
    """
    Генерирует inline-клавиатуру с кнопкой оплаты для инвойса.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text=f"Top up ★{amount:,}", pay=True)
    return builder.as_markup()