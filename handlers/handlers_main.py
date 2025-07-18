# --- Third-party libraries ---
from aiogram import F, Bot
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

# --- Internal modules ---
from services.config import format_supabase_summary, get_target_display
from services.database import get_user_data, update_user_data, get_user_profiles
from services.menu import update_menu, config_action_keyboard 
from services.balance import refresh_balance
from services.buy_bot import buy_gift

def register_main_handlers(dp, bot: Bot, version):
    """
    Registers the main handlers for the main menu, start and control commands.
    """

    @dp.message(CommandStart())
    async def command_status_handler(message: Message, state: FSMContext):
        """
        Handles the /start command - updates the balance and shows the main menu.
        Clears all FSM states for the user.
        """
        # В публичном режиме разрешаем доступ всем пользователям
        await state.clear()
        
        # Используем Supabase для получения данных пользователя
        user_id = message.from_user.id
        await refresh_balance(bot, user_id)
        await update_menu(bot=bot, chat_id=message.chat.id, user_id=user_id, message_id=message.message_id)


    @dp.callback_query(F.data == "main_menu")
    async def start_callback(call: CallbackQuery, state: FSMContext):
        """
        Shows the main menu when the "Menu" button is clicked.
        Clears all FSM states for the user.
        """
        await state.clear()
        await call.answer()
        
        # Используем Supabase для получения данных пользователя
        user_id = call.from_user.id
        await refresh_balance(call.bot, user_id)
        await update_menu(
            bot=call.bot,
            chat_id=call.message.chat.id,
            user_id=user_id,
            message_id=call.message.message_id
        )


    @dp.callback_query(F.data == "show_help")
    async def help_callback(call: CallbackQuery):
        """
        Shows detailed instructions for working with the bot.
        """
        user_id = call.from_user.id
        
        # Получаем профили пользователя из Supabase
        profiles = await get_user_profiles(user_id)
        # По умолчанию первый профиль
        profile = profiles[0] if profiles else None
        
        if profile:
            target_display = get_target_display(profile, user_id)
        else:
            target_display = "yourself"
            
        bot_info = await call.bot.get_me()
        bot_username = bot_info.username
        help_text = (
            f"<b>🛠 Bot management <code>v{version}</code> :</b>\n\n"
            "<b>🟢 Enable / 🔴 Disable</b> — starts or stops purchases.\n"
            "<b>✏️ Profiles</b> — Adding and deleting profiles with configurations for purchasing gifts.\n"
            "<b>♻️ Reset</b> — resets the number of already purchased gifts for all profiles, so as not to create again such profiles.\n"
            "<b>⚙️ Userbot</b> — managing the Telegram account session.\n"
            "<b>💰 Top up</b> — deposit stars in the bot.\n"
            "<b>↩️ Withdraw</b> — return stars by transaction ID or withdraw all stars at once by command /withdraw_all.\n"
            "<b>🎏 Catalog</b> — list of available gifts to purchase in the market.\n\n"
            "<b>📌 Tips:</b>\n\n"
            f"❗️ If the recipient of the gift is another user, he must enter this bot <code>@{bot_username}</code> and press <code>/start</code>.\n"
            "❗️ The recipient of the gift <b>account</b> — write <b>id</b> of the user (you can find it here @userinfobot).\n"
            "❗️ The recipient of the gift <b>channel</b> — write <b>username</b> of the channel.\n"
            "❗️ If the gift is sent <b>through a Userbot</b>, specify <b>only username</b> of the recipient — regardless of whether it is a user or a channel.\n"
            "❗️ To send a gift to another account, there must be a conversation between accounts.\n"
            f"❗️ To top up the bot's balance from any account, enter this bot <code>@{bot_username}</code> and press <code>/start</code>, to call the top-up menu.\n"
            "❗️ How to view the <b>transaction ID</b> for returning stars? Click on the payment message in the chat with the bot and there will be the transaction ID.\n"
            f"❗️ Want to test the bot? Buy a gift 🧸 for ★15 from the bot's balance, recipient {target_display}.\n\n"
            "<b>🐸 Author: @mirvaId</b>\n"
            "<b>📢 Channel: https://t.me/+kJTdSYRGDc45OTE8</b>"
        )
        button = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Test? Buy 🧸 for ★15", callback_data="buy_test_gift")],
            [InlineKeyboardButton(text="☰ Menu", callback_data="main_menu")]
        ])
        await call.answer()
        await call.message.answer(help_text, reply_markup=button, disable_web_page_preview=True)

    
    @dp.callback_query(F.data == "show_userbot_help")
    async def userbot_help_callback(call: CallbackQuery):
        help_text = (
            "🔐 <b>How to get api_id and api_hash for a Telegram account:</b>\n\n"
            "┌1️⃣ Go to the site: <a href=\"https://my.telegram.org\">https://my.telegram.org</a>\n"
            "├2️⃣ Log in, specifying the phone number and Telegram code\n"
            "├3️⃣ Select: <code>API development tools</code>\n"
            "├4️⃣ Enter <code>App title</code> (e.g. <code>GiftApp</code>)\n"
            "├5️⃣ Specify <code>Short name</code> (any short name)\n"
            "└6️⃣ After that you will get:\n"
            "    ├🔸 <b>App api_id</b> (number)\n"
            "    └🔸 <b>App api_hash</b> (set of characters)\n\n"
            "📥 These data are entered when connecting the userbot.\n\n"
            "📍 <b>Important:</b> After creating <b>api_id</b> and <b>api_hash</b> it may take 2–3 days — this is a normal Telegram limitation!\n\n"
            "📍 You cannot connect a userbot from the same account from which you manage this bot. Use a separate account for the userbot (twink).\n\n"
            "⚠️ Do not transfer <b>api_id</b> and <b>api_hash</b> to other people!"
        )
        button = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⚙️ Userbot", callback_data="userbot_menu"),
            InlineKeyboardButton(text="☰ Menu", callback_data="userbot_main_menu")
        ]])
        await call.answer()
        await call.message.answer(help_text, reply_markup=button, disable_web_page_preview=True)


    @dp.callback_query(F.data == "buy_test_gift")
    async def buy_test_gift(call: CallbackQuery):
        """
        Purchase of a test gift to check the bot's work.
        """
        gift_id = '5170233102089322756'
        user_id = call.from_user.id
        
        # Получаем профили пользователя из Supabase
        profiles = await get_user_profiles(user_id)
        # По умолчанию первый профиль
        profile = profiles[0] if profiles else None
        
        if not profile:
            await call.answer("Error: Profile not found")
            return
            
        TARGET_USER_ID = profile.get("target_user_id")
        TARGET_CHAT_ID = profile.get("target_chat_id")
        target_display = get_target_display(profile, user_id)

        success = await buy_gift(
            bot=call.bot,
            env_user_id=user_id,
            gift_id=gift_id,
            user_id=TARGET_USER_ID,
            chat_id=TARGET_CHAT_ID,
            gift_price=15,
            file_id=None
        )
        if not success:
            await call.answer()
            await call.message.answer("⚠️ Purchase of a gift 🧸 for ★15 is not possible.\n"
                                      "💰 Top up the balance! Check the recipient's address!\n"
                                      "🚦 Status changed to 🔴 (inactive).")
            # Обновляем статус пользователя в базе данных
            await update_user_data(user_id, {"active": False})
            await update_menu(bot=call.bot, chat_id=call.message.chat.id, user_id=user_id, message_id=call.message.message_id)
            return

        await call.answer()
        await call.message.answer(f"✅ Gift 🧸 for ★15 purchased. Recipient: {target_display}.")
        await update_menu(bot=call.bot, chat_id=call.message.chat.id, user_id=user_id, message_id=call.message.message_id)


    @dp.callback_query(F.data == "reset_bought")
    async def reset_bought_callback(call: CallbackQuery):
        """
        Reset counters of purchased gifts and completion statuses for all profiles.
        """
        user_id = call.from_user.id
        
        # Получаем данные пользователя и его профили из Supabase
        profiles = await get_user_profiles(user_id)
        
        # Сбрасываем счетчики во всех профилях
        from services.database import update_user_profile
        for profile in profiles:
            profile["bought"] = 0
            profile["spent"] = 0
            profile["done"] = False
            # Обновляем каждый профиль в таблице profiles
            await update_user_profile(profile["id"], profile)
        
        # Устанавливаем статус неактивный
        await update_user_data(user_id, {"active": False})
        
        # Получаем данные для отображения меню
        menu_text = await format_supabase_summary(user_id)
        
        try:
            await call.message.edit_text(
                menu_text,
                reply_markup=config_action_keyboard(False)
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise
        await call.answer("Purchase counter reset.")


    @dp.callback_query(F.data == "toggle_active")
    async def toggle_active_callback(call: CallbackQuery):
        """
        Switching the bot's status: active/inactive.
        """
        user_id = call.from_user.id
        
        # Получаем данные пользователя из Supabase
        user_data = await get_user_data(user_id)
        
        # Переключаем статус
        new_active = not user_data.get("active", False)
        await update_user_data(user_id, {"active": new_active})
        
        # Получаем текст меню из Supabase
        menu_text = await format_supabase_summary(user_id)
        
        await call.message.edit_text(
            menu_text,
            reply_markup=config_action_keyboard(new_active)
        )
        await call.answer("Status updated")


    @dp.pre_checkout_query()
    async def pre_checkout_handler(pre_checkout_query):
        """
        Processing a pre-payment in Telegram Invoice.
        """
        await pre_checkout_query.answer(ok=True)


    @dp.message(F.successful_payment)
    async def process_successful_payment(message: Message):
        """
        Processing a successful balance top-up through Telegram Invoice.
        """
        user_id = message.from_user.id
        
        await message.answer(
            f'✅ Balance successfully topped up.',
            message_effect_id="5104841245755180586"
        )
        
        # Обновляем баланс пользователя в базе данных
        balance = await refresh_balance(bot, user_id)
        await update_menu(bot=bot, chat_id=message.chat.id, user_id=user_id, message_id=message.message_id)
