# --- Standard libraries ---
import logging

# --- Third-party libraries ---
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

class AccessControlMiddleware(BaseMiddleware):
    """
    Access control middleware: allows only certain user_id.
    Rejects all other requests.
    """
    FREE_CALLBACKS = {"guest_deposit_menu"}
    FREE_STATES = {"ConfigWizard:guest_deposit_amount"}

    def __init__(self, allowed_user_ids: list[int]):
        """
        :param allowed_user_ids: List of allowed user_id.
        :param bot: Bot instance.
        """
        self.allowed_user_ids = allowed_user_ids
        super().__init__()

    async def __call__(self, handler, event: TelegramObject, data: dict):
        """
        Checks if the user is in the list of allowed users.
        If denied, sends a notification and blocks processing.
        """
        user = data.get("event_from_user")
        if user and user.id not in self.allowed_user_ids:
            # Allow the payment button press
            if isinstance(event, CallbackQuery) and getattr(event, "data", None) in self.FREE_CALLBACKS:
                return await handler(event, data)
            # Allow payment (FSM state)
            fsm_state = data.get("state")
            if fsm_state:
                state_name = await fsm_state.get_state()
                if state_name in self.FREE_STATES:
                    return await handler(event, data)
            # Allow invoice messages (invoice)
            if isinstance(event, Message):
                if getattr(event, "invoice", None) or getattr(event, "successful_payment", None):
                    return await handler(event, data)
            # Everything else is prohibited
            try:
                if isinstance(event, Message):
                    await show_guest_menu(event)
                elif isinstance(event, CallbackQuery):
                    await event.answer("⛔️ No access", show_alert=True)
            except Exception as e:
                logger.error(f"Failed to send refusal to user {user.id}: {e}")
            return
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
        "⛔️ You have <b>no access</b> to the control panel.\n\n"
        "<b>🤖 Source code: <a href=\"https://github.com/mirvald-space/GiftNinjaBot.git\">GitHub</a></b>\n"
        "<b>🐸 Author: @mirvaId</b>\n<b>📢 Channel: https://t.me/+kJTdSYRGDc45OTE8</b>",
        reply_markup=kb
    )