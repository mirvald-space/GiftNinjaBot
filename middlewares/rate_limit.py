# --- Standard libraries ---
import time
import logging

# --- Third-party libraries ---
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject, CallbackQuery

logger = logging.getLogger(__name__)

class RateLimitMiddleware(BaseMiddleware):
    """
    Middleware for spam protection: limits the frequency of command execution and button presses.
    Applicable to both text messages (Message) and CallbackQuery.

    The limitation applies separately for each command and user.
    Users from the allowed_user_ids list are not limited.
    """
    def __init__(self, commands_limits: dict = None, allowed_user_ids: list[int] = None):
        """
        :param commands_limits: Dictionary with limits in the format {command: interval_in_seconds}
        :param allowed_user_ids: List of user_ids allowed to ignore limitations
        """
        self.last_times = {}  # user_id -> {command: timestamp}
        self.commands_limits = commands_limits or {}  # command: seconds
        self.allowed_user_ids = allowed_user_ids or []

    async def __call__(self, handler, event: TelegramObject, data: dict):
        """
        Main middleware method: checks the frequency of command/button calls.
        If the limit is exceeded - the message/request is ignored and a warning is sent to the user.
        """
        now = time.monotonic()
        user_id = None
        command = None

        if isinstance(event, Message):
            user_id = event.from_user.id
            command = event.text.split()[0] if event.text else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            command = event.data

        if user_id is None or command is None:
            return await handler(event, data)

        if user_id in self.allowed_user_ids:
            return await handler(event, data)

        for cmd, limit in self.commands_limits.items():
            if command == cmd:
                user_times = self.last_times.setdefault(user_id, {})
                last = user_times.get(cmd, 0)

                if now - last < limit:
                    if isinstance(event, Message):
                        await event.answer("⏳ Please don't spam. Try again later.")
                    elif isinstance(event, CallbackQuery):
                        await event.answer("⏳ Please don't spam.", show_alert=True)
                    return
                user_times[cmd] = now

        return await handler(event, data)