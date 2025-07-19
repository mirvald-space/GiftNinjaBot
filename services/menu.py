# --- Third-party libraries ---
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- Internal modules ---
from services.config import load_config, save_config, get_valid_config, format_config_summary
from services.database import get_user_data, update_user_data

async def update_last_menu_message_id(message_id: int, user_id: int = None):
    """
    Saves the id of the last menu message.
    
    Args:
        message_id: Message ID to save
        user_id: User ID (if None, uses the old config method)
    """
    if user_id is None:
        # Старый метод с использованием файла конфигурации
        config = await load_config()
        config["LAST_MENU_MESSAGE_ID"] = message_id
        await save_config(config)
    else:
        # Новый метод с использованием Supabase
        await update_user_data(user_id, {"last_menu_message_id": message_id})


async def get_last_menu_message_id(user_id: int = None):
    """
    Returns the id of the last sent menu message.
    
    Args:
        user_id: User ID (if None, uses the old config method)
    """
    if user_id is None:
        # Старый метод с использованием файла конфигурации
        config = await load_config()
        return config.get("LAST_MENU_MESSAGE_ID")
    else:
        # Новый метод с использованием Supabase
        user_data = await get_user_data(user_id)
        return user_data.get("last_menu_message_id")


def config_action_keyboard(active: bool) -> InlineKeyboardMarkup:
    """
    Generates inline keyboard for menu with actions.
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
    Updates the menu in the chat: deletes the previous one and sends a new one.
    """
    # Получаем данные пользователя из Supabase
    user_data = await get_user_data(user_id)
    active = user_data.get("active", False)
    
    # Для отображения используем старый метод
    config = await get_valid_config(user_id)
    config["ACTIVE"] = active
    
    await delete_menu(bot=bot, chat_id=chat_id, current_message_id=message_id, user_id=user_id)
    await send_menu(bot=bot, chat_id=chat_id, config=config, text=format_config_summary(config, user_id), user_id=user_id)


async def delete_menu(bot, chat_id: int, current_message_id: int = None, user_id: int = None):
    """
    Deletes the last menu message if it differs from the current one.
    
    Args:
        bot: Bot instance
        chat_id: Chat ID
        current_message_id: Current message ID
        user_id: User ID (if None, uses the old config method)
    """
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


async def send_menu(bot, chat_id: int, config: dict, text: str, user_id: int = None) -> int:
    """
    Sends a new menu to the chat and updates the id of the last message.
    
    Args:
        bot: Bot instance
        chat_id: Chat ID
        config: Configuration
        text: Menu text
        user_id: User ID (if None, uses the old config method)
    """
    sent = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=config_action_keyboard(config.get("ACTIVE"))
    )
    await update_last_menu_message_id(sent.message_id, user_id)
    return sent.message_id


def payment_keyboard(amount):
    """
    Generates inline keyboard with payment button for invoice.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text=f"Top up ★{amount:,}", pay=True)
    return builder.as_markup()