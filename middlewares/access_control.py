# --- Standard libraries ---
import logging
from typing import Optional, List

# --- Third-party libraries ---
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

class AccessControlMiddleware(BaseMiddleware):
    """
    Access control middleware: allows all users to access the bot.
    """
    FREE_CALLBACKS = {"guest_deposit_menu"}
    FREE_STATES = {"ConfigWizard:guest_deposit_amount"}

    def __init__(self, allowed_user_ids: Optional[List[int]] = None):
        """
        :param allowed_user_ids: List of allowed user_id (not used in public mode).
        :param bot: Bot instance.
        """
        self.allowed_user_ids = allowed_user_ids or []
        super().__init__()

    async def __call__(self, handler, event: TelegramObject, data: dict):
        """
        Public access mode: all users are allowed.
        """
        # Allow access to all users
        return await handler(event, data)
    
async def show_guest_menu(message: Message):
    """
    Shows the guest menu for unauthorized users.   
    """
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💰 Top up", callback_data="guest_deposit_menu")
            ]
        ]
    )
    await message.answer(
        "✅ You can <b>receive gifts</b> from this bot.\n"
        "💰 You can <b>top up</b> stars in the bot.\n"
        "✅ You have <b>full access</b> to the control panel.\n\n"
        "<b>🤖 Source code: <a href=\"https://github.com/mirvald-space/GiftNinjaBot.git\">GitHub</a></b>\n"
        "<b>🐸 Author: @mirvaId</b>\n<b>📢 Channel: https://t.me/+kJTdSYRGDc45OTE8</b>",
        reply_markup=kb
    )