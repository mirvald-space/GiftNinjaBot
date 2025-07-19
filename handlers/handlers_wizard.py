# --- Standard libraries ---
import logging

# --- Third-party libraries ---
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError

# --- Internal modules ---
from services.config import get_valid_config, get_target_display, save_config
from services.menu import update_menu, payment_keyboard
from services.balance import refresh_balance, refund_all_star_payments
from services.config import CURRENCY, MAX_PROFILES, add_profile, remove_profile, update_profile
from services.userbot import is_userbot_active, userbot_send_self, delete_userbot_session, start_userbot, continue_userbot_signin, finish_userbot_signin
from utils.misc import now_str, is_valid_profile_name, PHONE_REGEX, API_HASH_REGEX

logger = logging.getLogger(__name__)
wizard_router = Router()


class ConfigWizard(StatesGroup):
    """
    Class of states for FSM wizard (step-by-step configuration editing).
    Each state is a separate step in the process.
    """
    min_price = State()
    max_price = State()
    min_supply = State()
    max_supply = State()
    count = State()
    limit = State()
    user_id = State()
    edit_min_price = State()
    edit_max_price = State()
    edit_min_supply = State()
    edit_max_supply = State()
    edit_count = State()
    edit_limit = State()
    edit_user_id = State()
    edit_gift_sender = State()
    gift_sender = State()
    edit_profile_name = State()
    deposit_amount = State()
    refund_id = State()
    guest_deposit_amount = State()
    userbot_api_id = State()
    userbot_api_hash = State()
    userbot_phone = State()
    userbot_code = State()
    userbot_password = State()


@wizard_router.callback_query(F.data == "userbot_menu")
async def on_userbot_menu(call: CallbackQuery):
    """
    Calls for updating the userbot menu after the callback.
    """
    await userbot_menu(call.message, call.from_user.id)
    await call.answer()


async def userbot_menu(message: Message, user_id: int, edit: bool = False):
    """
    Forms and sends (or edits) the userbot menu for the user.
    """
    config = await get_valid_config(user_id)
    userbot = config.get("USERBOT", {})

    userbot_username = userbot.get("USERNAME")
    userbot_user_id = userbot.get("USER_ID")
    phone = userbot.get("PHONE")
    enabled = userbot.get("ENABLED", False)

    if is_userbot_active(user_id):
        status_button = InlineKeyboardButton(
            text="🔕 Turn off" if enabled else "🔔 Turn on",
            callback_data="userbot_disable" if enabled else "userbot_enable"
        )
        text = (
            "✅ <b>Userbot connected.</b>\n\n"
            f"┌ <b>User:</b> {'@' + userbot_username if userbot_username else '—'} (<code>{userbot_user_id}</code>)\n"
            f"├ <b>Number:</b> <code>{phone or '—'}</code>\n"
            f"└ <b>Status:</b> {'🔔 On ' if enabled else '🔕 Off'}\n\n"
            f"❗️ Status 🔕 <b>pauses</b> the <b>userbot</b>."
        )
        keyboard = [
            [
                status_button,
                InlineKeyboardButton(text="🗑 Delete", callback_data="userbot_confirm_delete")
            ],
            [
                InlineKeyboardButton(text="📘 Instructions", callback_data="show_userbot_help"),
                InlineKeyboardButton(text="☰ Menu", callback_data="userbot_main_menu")
            ]
        ]
    else:
        text = (
            "🚫 <b>Userbot not connected.</b>\n\n"
            "📋 <b>Prepare the following data:</b>\n\n"
            "🔸 <code>api_id</code>\n"
            "🔸 <code>api_hash</code>\n"
            "�� <code>Phone number</code>\n\n"
            "📎 Get <b><a href=\"https://my.telegram.org\">API data</a></b>\n"
            "📜 Read <b><a href=\"https://core.telegram.org/api/terms\">terms of use</a></b>" 
        )
        keyboard = [
            [InlineKeyboardButton(text="➕ Connect userbot", callback_data="init_userbot")],
            [InlineKeyboardButton(text="📘 Instructions", callback_data="show_userbot_help")],
            [InlineKeyboardButton(text="☰ Menu", callback_data="userbot_main_menu")]
        ]

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    try:
        if edit:
            await message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        else:
            await message.answer(text, reply_markup=markup, disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"⚠️ Error when updating menu: {e}")


@wizard_router.callback_query(F.data == "userbot_confirm_delete")
async def confirm_userbot_delete(call: CallbackQuery):
    """
    Requests confirmation of userbot session deletion from the user.
    """
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Yes", callback_data="userbot_delete_yes"),
            InlineKeyboardButton(text="❌ No", callback_data="userbot_delete_no")
        ]
    ])
    await call.message.edit_text(
        "❗ Are you sure you want to <b>delete the userbot</b>?",
        reply_markup=kb
    )
    await call.answer()


@wizard_router.callback_query(F.data == "userbot_delete_no")
async def cancel_userbot_delete(call: CallbackQuery):
    """
    Cancels the userbot session deletion process and returns to the menu.
    """
    user_id = call.from_user.id
    await call.answer("Cancelled.")
    await userbot_menu(call.message, user_id, edit=True)


@wizard_router.callback_query(F.data == "userbot_delete_yes")
async def userbot_delete_handler(call: CallbackQuery):
    """
    Deletes the userbot session data from the user's configuration.
    """
    user_id = call.from_user.id
    success = await delete_userbot_session(user_id)

    if success:
        await call.message.answer("✅ Userbot deleted.")
        await userbot_menu(call.message, user_id, edit=False)
    else:
        await call.message.answer("🚫 Unable to delete userbot. It may have already been deleted.")
        await userbot_menu(call.message, user_id, edit=False)

    await call.answer()


@wizard_router.callback_query(F.data == "userbot_enable")
async def userbot_enable_handler(call: CallbackQuery):
    """
    Enables the userbot session in the configuration and updates the menu.
    """
    user_id = call.from_user.id
    username = call.from_user.username
    bot_user = await call.bot.get_me()
    bot_username = bot_user.username
    
    # Обновляем статус юзербота в таблице userbots
    from services.database import update_user_userbot_data
    await update_user_userbot_data(user_id, {"enabled": True})

    await call.answer()

    text_message = (
        f"🔔 <b>Userbot enabled.</b>\n\n"
        f"┌🤖 <b>Bot:</b> @{bot_username}\n"
        f"├👤 <b>User:</b> @{username} (<code>{user_id}</code>)\n"
        f"└🕒 <b>Time:</b> {now_str()} (UTC)"
    )
    success_send_message = await userbot_send_self(user_id, text_message)

    if success_send_message:
        logger.info("Userbot successfully enabled.")
    else:
        logger.error("Userbot successfully enabled, but the message could not be sent.")

    await userbot_menu(call.message, user_id, edit=True)


@wizard_router.callback_query(F.data == "userbot_disable")
async def userbot_disable_handler(call: CallbackQuery):
    """
    Disables the userbot session in the configuration and updates the menu.
    """
    user_id = call.from_user.id
    username = call.from_user.username
    bot_user = await call.bot.get_me()
    bot_username = bot_user.username
    
    # Обновляем статус юзербота в таблице userbots
    from services.database import update_user_userbot_data
    await update_user_userbot_data(user_id, {"enabled": False})

    await call.answer()

    text_message = (
        f"🔕 <b>Userbot disabled.</b>\n\n"
        f"┌🤖 <b>Bot:</b> @{bot_username}\n"
        f"├👤 <b>User:</b> @{username} (<code>{user_id}</code>)\n"
        f"└🕒 <b>Time:</b> {now_str()} (UTC)"
    )
    success_send_message = await userbot_send_self(user_id, text_message)

    if success_send_message:
        logger.info("Userbot successfully disabled.")
    else:
        logger.error("Userbot successfully disabled, but the message could not be sent.")

    await userbot_menu(call.message, user_id, edit=True)


@wizard_router.callback_query(F.data == "init_userbot")
async def init_userbot_handler(call: CallbackQuery, state: FSMContext):
    """
    Starts the process of connecting a new userbot session (step input api_id).
    """
    await call.message.answer("📥 Enter <b>api_id</b>:\n\n/cancel — cancel")
    await state.set_state(ConfigWizard.userbot_api_id)
    await call.answer()


@wizard_router.message(ConfigWizard.userbot_api_id)
async def get_api_id(message: Message, state: FSMContext):
    """
    Processes the input of api_id from the user and moves to the next step.
    """
    if await try_cancel(message, state):
        return
    
    if not message.text:
        await message.answer("🚫 Only text input is supported.\n\n/cancel — cancel")
        return
    
    text = message.text.strip()

    if not text.isdigit() or not (10000 <= int(text) <= 9999999999):
        await message.answer("🚫 Invalid format. Enter a correct number.\n\n/cancel — cancel")
        return
    
    value = int(text)
    await state.update_data(api_id=value)
    await message.answer("📥 Enter <b>api_hash</b>:\n\n/cancel — cancel")
    await state.set_state(ConfigWizard.userbot_api_hash)


@wizard_router.message(ConfigWizard.userbot_api_hash)
async def get_api_hash(message: Message, state: FSMContext):
    """
    Processes the input of api_hash and moves to the step of entering the phone number.
    """
    if await try_cancel(message, state):
        return
    
    if not message.text:
        await message.answer("🚫 Only text input is supported.\n\n/cancel — cancel")
        return
    
    api_hash = message.text.strip()

    if not API_HASH_REGEX.fullmatch(api_hash):
        await message.answer("🚫 Invalid format. Make sure api_hash is copied completely (32 characters).\n\n/cancel — cancel")
        return

    await state.update_data(api_hash=api_hash)
    await message.answer("📥 Enter the phone number (in the format <code>+490123456789</code>):\n\n/cancel — cancel")
    await state.set_state(ConfigWizard.userbot_phone)


@wizard_router.message(ConfigWizard.userbot_phone)
async def get_phone(message: Message, state: FSMContext):
    """
    Saves the phone number and initiates sending the confirmation code.
    """
    if await try_cancel(message, state):
        return
    
    if not message.text:
        await message.answer("🚫 Only text input is supported.\n\n/cancel — cancel")
        return
    
    raw_phone = message.text.strip()
    phone = raw_phone.replace(" ", "")

    if not PHONE_REGEX.match(phone):
        await message.answer("🚫 Invalid format for phone number.\nEnter in the format: <code>+490123456789</code>\n\n/cancel — cancel")
        return
    
    await state.update_data(phone=phone)

    success = await start_userbot(message, state)
    if not success:
        await userbot_menu(message, message.from_user.id, edit=False)
        await state.clear()
        return
    await message.answer("📥 Enter the received code:\n\n/cancel — cancel")
    await state.set_state(ConfigWizard.userbot_code)


@wizard_router.message(ConfigWizard.userbot_code)
async def get_code(message: Message, state: FSMContext):
    """
    Processes the confirmation code and, if necessary, requests a password.
    """
    if await try_cancel(message, state):
        return
    
    if not message.text:
        await message.answer("🚫 Only text input is supported.\n\n/cancel — cancel")
        return
    
    await state.update_data(code=message.text.strip())
    success, need_password, retry = await continue_userbot_signin(message, state)
    if retry:
        return
    if not success:
        await message.answer("🚫 Code error. Userbot connection interrupted.")
        await userbot_menu(message, message.from_user.id, edit=False)
        await state.clear()
        return
    if need_password:
        await message.answer("📥 Enter password:\n\n/cancel — cancel")
        await state.set_state(ConfigWizard.userbot_password)
    else:
        user_id = message.from_user.id
        username = message.from_user.username
        bot_user = await message.bot.get_me()
        bot_username = bot_user.username
        text_message = (
            f"✅ <b>Userbot successfully connected.</b>\n"
            f"┌🤖 <b>Bot:</b> @{bot_username}\n"
            f"├👤 <b>User:</b> @{username} (<code>{user_id}</code>)\n"
            f"└🕒 <b>Time:</b> {now_str()} (UTC)"
        )
        success_send_message = await userbot_send_self(user_id, text_message)

        if success_send_message:
            await message.answer("✅ Userbot successfully connected.")
        else:
            await message.answer("✅ Userbot successfully connected.\n🚫 Error sending confirmation.")

        await userbot_menu(message, message.from_user.id, edit=False)
        await state.clear()


@wizard_router.message(ConfigWizard.userbot_password)
async def get_password(message: Message, state: FSMContext):
    """
    Processes the input of password from Telegram account and completes userbot's authorization.
    """
    if await try_cancel(message, state):
        return
    
    if not message.text:
        await message.answer("🚫 Only text input is supported.\n\n/cancel — cancel")
        return
    
    await state.update_data(password=message.text.strip())
    success, retry = await finish_userbot_signin(message, state)
    if retry:
        return
    if success:
        user_id = message.from_user.id
        username = message.from_user.username
        bot_user = await message.bot.get_me()
        bot_username = bot_user.username
        text_message = (
            f"✅ <b>Userbot successfully connected.</b>\n"
            f"┌🤖 <b>Bot:</b> @{bot_username}\n"
            f"├👤 <b>User:</b> @{username} (<code>{user_id}</code>)\n"
            f"└🕒 <b>Time:</b> {now_str()} (UTC)"
        )
        success_send_message = await userbot_send_self(user_id, text_message)

        if success_send_message:
            await message.answer("✅ Userbot successfully connected.")
        else:
            await message.answer("✅ Userbot successfully connected.\n🚫 Error sending confirmation.")
    else:
        await message.answer("🚫 Incorrect password. Userbot connection interrupted.")

    await userbot_menu(message, message.from_user.id, edit=False)
    await state.clear()


@wizard_router.callback_query(F.data == "userbot_main_menu")
async def userbot_main_menu_callback(call: CallbackQuery, state: FSMContext):
    """
    Shows the main menu by clicking the "Menu" button.
    Clears all FSM states for the user.
    """
    await state.clear()
    await call.answer()
    await safe_edit_text(call.message, "✅ Userbot configuration completed.", reply_markup=None)
    await refresh_balance(call.bot, call.from_user.id)
    await update_menu(
        bot=call.bot,
        chat_id=call.message.chat.id,
        user_id=call.from_user.id,
        message_id=call.message.message_id
    )


async def profiles_menu(message: Message, user_id: int):
    """
    Shows the main menu for user to manage profiles.
    Displays a list of all created profiles and provides buttons to edit, delete, or add a new profile.
    """
    config = await get_valid_config(user_id)
    profiles = config.get("PROFILES", [])

    # Form profile keyboard
    keyboard = []
    for idx, profile in enumerate(profiles):
        profile_name = f'Profile {idx + 1}' if  not profile.get('name') else profile['name']
        btns = [
            InlineKeyboardButton(
                text=f"✏️ {profile_name}", callback_data=f"profile_edit_{idx}"
            ),
            InlineKeyboardButton(
                text="🗑 Delete", callback_data=f"profile_delete_{idx}"
            ),
        ]
        keyboard.append(btns)
    # Add button (maximum 3 profiles)
    if len(profiles) < MAX_PROFILES:
        keyboard.append([InlineKeyboardButton(text="➕ Add", callback_data="profile_add")])
    # Back button
    keyboard.append([InlineKeyboardButton(text="☰ Menu", callback_data="profiles_main_menu")])

    profiles = config.get("PROFILES", [])

    lines = []
    for idx, profile in enumerate(profiles, 1):
        target_display = get_target_display(profile, user_id)
        profile_name = f'Profile {idx}' if  not profile.get('name') else profile['name']
        sender = '<code>Bot</code>' if profile.get('sender') == 'bot' else '<code>Userbot</code>'
        if idx == 1 and len(profiles) == 1: line = (f"🏷️ <b>{profile_name} {sender}</b> → {target_display}")
        elif idx == 1: line = (f"┌🏷️ <b>{profile_name} {sender}</b> → {target_display}")
        elif len(profiles) == idx: line = (f"└🏷️ <b>{profile_name} {sender}</b> → {target_display}")
        else: line = (f"├🏷️ <b>{profile_name} {sender}</b> → {target_display}")
        lines.append(line)
    text_profiles = "\n".join(lines)

    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer(f"📝 <b>Profile management (maximum 3):</b>\n\n"
                         f"{text_profiles}\n\n"
                         "👉 <b>Click</b> ✏️ to edit profile.\n", 
                         reply_markup=kb)


@wizard_router.callback_query(F.data == "profiles_menu")
async def on_profiles_menu(call: CallbackQuery):
    """
    Handles clicking on the "Profiles" button or navigating to the profile list.
    Opens the user's profile menu to edit or delete.
    """
    await profiles_menu(call.message, call.from_user.id)
    await call.answer()


def profile_text(profile, idx, user_id):
    """
    Forms a text description of profile parameters based on its data.
    Includes prices, limits, supply, recipient, and other basic information about the selected profile.
    Used for displaying information when editing a profile.
    """
    target_display = get_target_display(profile, user_id)
    profile_name = f'Profile {idx + 1}' if  not profile.get('name') else profile['name']
    sender = '<code>Bot</code>' if profile.get('sender') == 'bot' else '<code>Userbot</code>'
    return (f"✏️ <b>Editing {profile_name}</b>:\n\n"
            f"┌💰 <b>Price</b>: {profile.get('min_price', 0):,} – {profile.get('max_price', 0):,} ★\n"
            f"├📦 <b>Supply</b>: {profile.get('min_supply', 0):,} – {profile.get('max_supply', 0):,}\n"
            f"├🎁 <b>Bought</b>: {profile.get('bought', 0):,} / {profile.get('count', 0):,}\n"
            f"├⭐️ <b>Limit</b>: {profile.get('spent', 0):,} / {profile.get('limit', 0):,} ★\n"
            f"├👤 <b>Recipient</b>: {target_display}\n"
            f"└📤 <b>Sender</b>: {sender}")


def profile_edit_keyboard(idx):
    """
    Creates an inline keyboard for quickly editing the parameters of the selected profile.
    Each button is responsible for editing a separate field (price, supply, limit, etc.).
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💰 Price", callback_data=f"edit_profile_price_{idx}"),
                InlineKeyboardButton(text="📦 Supply", callback_data=f"edit_profile_supply_{idx}"),
            ],
            [
                InlineKeyboardButton(text="🎁 Quantity", callback_data=f"edit_profile_count_{idx}"),
                InlineKeyboardButton(text="⭐️ Limit", callback_data=f"edit_profile_limit_{idx}")
            ],
            [
                InlineKeyboardButton(text="👤 Recipient", callback_data=f"edit_profile_target_{idx}"),
                InlineKeyboardButton(text="📤 Sender", callback_data=f"edit_profile_sender_{idx}")
            ],
            [
                InlineKeyboardButton(text="🏷️ Name", callback_data=f"edit_profile_name_{idx}"),
                InlineKeyboardButton(text="⬅️ Back", callback_data=f"edit_profiles_menu_{idx}")
            ],
            [
                InlineKeyboardButton(text="☰ Menu", callback_data="profiles_main_menu")
            ]
        ]
    )


@wizard_router.callback_query(lambda c: c.data.startswith("profile_edit_"))
async def on_profile_edit(call: CallbackQuery, state: FSMContext):
    """
    Opens the detailed editing screen for a specific profile.
    Shows all profile parameters and inline buttons to select the appropriate parameter for editing.
    """
    idx = int(call.data.split("_")[-1])
    config = await get_valid_config(call.from_user.id)
    profile = config["PROFILES"][idx]
    await state.update_data(profile_index=idx)
    await state.update_data(message_id=call.message.message_id)
    await call.message.edit_text(
        profile_text(profile, idx, call.from_user.id),
        reply_markup=profile_edit_keyboard(idx)
    )
    await call.answer()


@wizard_router.message(ConfigWizard.edit_profile_name)
async def on_profile_name_entered(message: Message, state: FSMContext):
    """
    Handles input of a new profile name.
    """
    if await try_cancel(message, state):
        return
    
    if not message.text:
        await message.answer("🚫 Only text input is supported.\n\n/cancel — cancel")
        return
    
    name = message.text.strip()
    if not is_valid_profile_name(name):
        await message.answer("🚫 Name must contain only letters (Russian and Latin) and numbers, "
                             "and be no longer than 12 characters. Please try again.\n\n"
                             "/cancel — cancel")
        return

    data = await state.get_data()
    idx = data.get("profile_index")
    if idx is None:
        await message.answer("Error: profile not selected for renaming.")
        await state.clear()
        return

    config = await get_valid_config(message.from_user.id)
    profiles = config.get("PROFILES", [])
    if idx < 0 or idx >= len(profiles):
        await message.answer("Error: profile not found.")
        await state.clear()
        return

    profiles[idx]["name"] = name
    await save_config(config)
    await message.answer(f"✅ Profile name successfully changed to: <b>{name}</b>")

    # Return to profile menu (call your profile function)
    await profiles_menu(message, message.from_user.id)
    await state.clear()


@wizard_router.callback_query(lambda c: c.data.startswith("edit_profile_price_"))
async def edit_profile_min_price(call: CallbackQuery, state: FSMContext):
    """
    Handles clicking on the button to change the minimum price in the profile.
    Moves the user to the input of a new minimum price.
    """
    idx = int(call.data.split("_")[-1])
    await state.update_data(profile_index=idx)
    await state.update_data(message_id=call.message.message_id)
    config = await get_valid_config(call.from_user.id)
    profiles = config.get("PROFILES", [])
    profile = profiles[idx]
    profile_name = f'profile {idx+1}' if  not profile.get('name') else profile.get('name')
    await call.message.answer(f"✏️ <b>Editing {profile_name}:</b>\n\n"
                              "💰 Minimum gift price, for example: <code>5000</code>\n\n"
                              "/cancel — cancel")
    await state.set_state(ConfigWizard.edit_min_price)
    await call.answer()


@wizard_router.callback_query(lambda c: c.data.startswith("edit_profile_supply_"))
async def edit_profile_min_supply(call: CallbackQuery, state: FSMContext):
    """
    Handles clicking on the button to change the minimum supply for the profile.
    Moves the user to the input of a new minimum supply value.
    """
    idx = int(call.data.split("_")[-1])
    await state.update_data(profile_index=idx)
    await state.update_data(message_id=call.message.message_id)
    config = await get_valid_config(call.from_user.id)
    profiles = config.get("PROFILES", [])
    profile = profiles[idx]
    profile_name = f'profile {idx+1}' if  not profile.get('name') else profile.get('name')
    await call.message.answer(f"✏️ <b>Editing {profile_name}:</b>\n\n"
                              "📦 Minimum supply for gift, for example: <code>1000</code>\n\n"
                              "/cancel — cancel")
    await state.set_state(ConfigWizard.edit_min_supply)
    await call.answer()


@wizard_router.callback_query(lambda c: c.data.startswith("edit_profile_limit_"))
async def edit_profile_limit(call: CallbackQuery, state: FSMContext):
    """
    Handles clicking on the button to change the limit (maximum amount of spending) for the profile.
    Moves the user to the input of a new limit.
    """
    idx = int(call.data.split("_")[-1])
    await state.update_data(profile_index=idx)
    await state.update_data(message_id=call.message.message_id)
    config = await get_valid_config(call.from_user.id)
    profiles = config.get("PROFILES", [])
    profile = profiles[idx]
    profile_name = f'profile {idx+1}' if  not profile.get('name') else profile.get('name')
    await call.message.answer(f"✏️ <b>Editing {profile_name}:</b>\n\n"
                              "⭐️ Enter the number of stars for this profile (for example: <code>10000</code>)\n\n"
                              "/cancel — cancel")
    await state.set_state(ConfigWizard.edit_limit)
    await call.answer()


@wizard_router.callback_query(lambda c: c.data.startswith("edit_profile_count_"))
async def edit_profile_count(call: CallbackQuery, state: FSMContext):
    """
    Handles clicking on the button to change the number of gifts in the profile.
    Moves the user to the input of a new number.
    """
    idx = int(call.data.split("_")[-1])
    await state.update_data(profile_index=idx)
    await state.update_data(message_id=call.message.message_id)
    config = await get_valid_config(call.from_user.id)
    profiles = config.get("PROFILES", [])
    profile = profiles[idx]
    profile_name = f'profile {idx+1}' if  not profile.get('name') else profile.get('name')
    await call.message.answer(f"✏️ <b>Editing {profile_name}:</b>\n\n"
                              "🎁 Maximum number of gifts, for example: <code>5</code>\n\n"
                              "/cancel — cancel")
    await state.set_state(ConfigWizard.edit_count)
    await call.answer()


@wizard_router.callback_query(lambda c: c.data.startswith("edit_profile_target_"))
async def edit_profile_target(call: CallbackQuery, state: FSMContext):
    """
    Handles clicking on the button to change the recipient of gifts (user_id or @username).
    Moves the user to the input of a new recipient.
    """
    idx = int(call.data.split("_")[-1])
    await state.update_data(profile_index=idx)
    await state.update_data(message_id=call.message.message_id)
    config = await get_valid_config(call.from_user.id)
    profiles = config.get("PROFILES", [])
    profile = profiles[idx]
    profile_name = f'profile {idx+1}' if  not profile.get('name') else profile.get('name')
    message_text = (f"✏️ <b>Editing {profile_name}:</b>\n\n"
                    "📥 Enter <b>recipient</b> of the gift:\n\n"
                    "🤖 If <b>sender</b> <code>Bot</code> enter:\n"
                    f"➤ <b>User ID</b> (for example your: <code>{call.from_user.id}</code>)\n"
                    "➤ <b>channel username</b> (for example: <code>@mirvaId</code>)\n\n"
                    "👤 If <b>sender</b> <code>Userbot</code> enter:\n"
                    "➤ <b>username</b> of the user (for example: <code>@mirvaId</code>)\n"
                    "➤ <b>channel username</b> (for example: <code>@mirvaId</code>)\n\n"
                    "🔎 <b>Find user ID</b> here: @userinfobot\n\n"
                    "⚠️ In order for the <code>Userbot</code> account to send a gift to another account, there must be a conversation between accounts.\n\n"
                    "/cancel — cancel")
    await call.message.answer(message_text)
    await state.set_state(ConfigWizard.edit_user_id)
    await call.answer()


@wizard_router.callback_query(lambda c: c.data.startswith("edit_profile_name_"))
async def edit_profile_name(call: CallbackQuery, state: FSMContext):
    """
    Button "Rename profile". Saves the index and waits for a new name.
    """
    idx = int(call.data.split("_")[-1])
    await state.update_data(profile_index=idx)
    await call.message.answer(f"✏️ Enter a new name for profile {idx + 1}: (up to 12 characters)\n\n"
                              "/cancel — cancel")
    await state.set_state(ConfigWizard.edit_profile_name)
    await call.answer()


@wizard_router.callback_query(lambda c: c.data.startswith("edit_profile_sender_"))
async def edit_profile_sender(call: CallbackQuery, state: FSMContext):
    idx = int(call.data.removeprefix("edit_profile_sender_"))
    config = await get_valid_config(call.from_user.id)
    profiles = config.get("PROFILES", [])

    if idx >= len(profiles):
        await call.answer("Profile not found.", show_alert=True)
        return

    profile = profiles[idx]

    # Save profile in FSM (we'll edit it)
    await state.set_state(ConfigWizard.edit_gift_sender)
    await state.update_data(profile_data=profile, profile_index=idx)

    profile_name = f'profile {idx+1}' if  not profile.get('name') else profile.get('name')
    await call.message.edit_text(f"✏️ <b>Editing {profile_name}:</b>\n\n"
                                 "�� Select <b>sender</b> of gifts:\n\n"
                                 "🤖 <code>Bot</code> - purchases from bot balance\n"
                                 "👤 <code>Userbot</code> - purchases from userbot balance\n\n"
                                 "❗️ If sender <code>Userbot</code>, make sure he <b>enabled</b> 🔔\n\n"
                                 "/cancel — cancel",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🤖 Bot", callback_data="choose_sender_bot"),
                InlineKeyboardButton(text="👤 Userbot", callback_data="choose_sender_userbot")
            ]
        ])
    )
    await call.answer()


@wizard_router.message(ConfigWizard.gift_sender)
async def handle_gift_sender_input(message: Message, state: FSMContext):
    """
    Processes input on the sender selection step. Allows canceling with the /cancel command.
    """
    if await try_cancel(message, state):
        return

    await message.answer("❗ Please select a sender using the buttons.\n\n"
                         "/cancel — cancel")


@wizard_router.message(ConfigWizard.edit_gift_sender)
async def handle_gift_sender_input(message: Message, state: FSMContext):
    """
    Processes input on the sender selection step. Allows canceling with the /cancel command.
    """
    if await try_cancel(message, state):
        return

    await message.answer("❗ Please select a sender using the buttons.\n\n"
                         "/cancel — cancel")


@wizard_router.callback_query(lambda c: c.data.startswith("edit_profiles_menu_"))
async def edit_profiles_menu(call: CallbackQuery):
    """
    Handles returning from profile editing mode to the main profile menu.
    Opens the user's list of all profiles.
    """
    idx = int(call.data.split("_")[-1])
    config = await get_valid_config(call.from_user.id)
    profiles = config.get("PROFILES", [])
    profile = profiles[idx]
    profile_name = f'profile {idx+1}' if  not profile.get('name') else profile.get('name')
    await safe_edit_text(call.message, f"✅ Editing <b>{profile_name}</b> completed.", reply_markup=None)
    await profiles_menu(call.message, call.from_user.id)
    await call.answer()


@wizard_router.message(ConfigWizard.edit_min_price)
async def step_edit_min_price(message: Message, state: FSMContext):
    """
    Processes input from the user for a new minimum price for the profile.
    Checks validity, saves, and returns the user to the profile menu.
    """
    if await try_cancel(message, state):
        return
    
    if not message.text:
        await message.answer("🚫 Only text input is supported.\n\n/cancel — cancel")
        return
    
    data = await state.get_data()
    idx = data["profile_index"]
    
    try:
        value = int(message.text)
        if value <= 0:
            raise ValueError
        await state.update_data(MIN_PRICE=value)
        config = await get_valid_config(message.from_user.id)
        profiles = config.get("PROFILES", [])
        profile = profiles[idx]
        profile_name = f'profile {idx+1}' if  not profile.get('name') else profile.get('name')
        await message.answer(f"✏️ <b>Editing {profile_name}:</b>\n\n"
                             "💰 Maximum gift price, for example: <code>10000</code>\n\n"
                             "/cancel — cancel")
        await state.set_state(ConfigWizard.edit_max_price)
    except ValueError:
        await message.answer("🚫 Enter a positive number. Please try again.\n\n/cancel — cancel")


@wizard_router.message(ConfigWizard.edit_max_price)
async def step_edit_max_price(message: Message, state: FSMContext):
    """
    Processes input from the user for a new maximum price for the profile.
    Checks validity, saves, and returns the user to the profile menu.
    """
    if await try_cancel(message, state):
        return
    
    if not message.text:
        await message.answer("🚫 Only text input is supported.\n\n/cancel — cancel")
        return
    
    data = await state.get_data()
    idx = data["profile_index"]
    
    try:
        value = int(message.text)
        if value <= 0:
            raise ValueError

        data = await state.get_data()
        min_price = data.get("MIN_PRICE")
        if min_price and value < min_price:
            await message.answer("🚫 Maximum price cannot be less than minimum. Please try again.\n\n/cancel — cancel")
            return

        config = await get_valid_config(message.from_user.id)
        config["PROFILES"][idx]["MIN_PRICE"] = data["MIN_PRICE"]
        config["PROFILES"][idx]["MAX_PRICE"] = value
        await save_config(config)

        try:
            await message.bot.delete_message(message.chat.id, data["message_id"])
        except Exception as e:
            logger.warning(f"Failed to delete message: {e}")

        await message.answer(
            profile_text(config["PROFILES"][idx], idx, message.from_user.id),
            reply_markup=profile_edit_keyboard(idx)
        )
        await state.clear()
    except ValueError:
        await message.answer("🚫 Enter a positive number. Please try again.\n\n/cancel — cancel")


@wizard_router.message(ConfigWizard.edit_min_supply)
async def step_edit_min_supply(message: Message, state: FSMContext):
    """
    Processes input from the user for a new minimum supply for the profile.
    Checks validity, saves, and returns the user to the profile menu.
    """
    if await try_cancel(message, state):
        return
    
    if not message.text:
        await message.answer("🚫 Only text input is supported.\n\n/cancel — cancel")
        return
    
    data = await state.get_data()
    idx = data["profile_index"]
    
    try:
        value = int(message.text)
        if value <= 0:
            raise ValueError
        await state.update_data(MIN_SUPPLY=value)
        config = await get_valid_config(message.from_user.id)
        profiles = config.get("PROFILES", [])
        profile = profiles[idx]
        profile_name = f'profile {idx+1}' if  not profile.get('name') else profile.get('name')
        await message.answer(f"✏️ <b>Editing {profile_name}:</b>\n\n"
                             "📦 Maximum supply for gift, for example: <code>10000</code>\n\n"
                             "/cancel — cancel")
        await state.set_state(ConfigWizard.edit_max_supply)
    except ValueError:
        await message.answer("🚫 Enter a positive number. Please try again.\n\n/cancel — cancel")


@wizard_router.message(ConfigWizard.edit_max_supply)
async def step_edit_max_supply(message: Message, state: FSMContext):
    """
    Processes input from the user for a new maximum supply for the profile.
    Checks validity, saves, and returns the user to the profile menu.
    """
    if await try_cancel(message, state):
        return
    
    if not message.text:
        await message.answer("🚫 Only text input is supported.\n\n/cancel — cancel")
        return
    
    data = await state.get_data()
    idx = data["profile_index"]
    
    try:
        value = int(message.text)
        if value <= 0:
            raise ValueError

        data = await state.get_data()
        min_supply = data.get("MIN_SUPPLY")
        if min_supply and value < min_supply:
            await message.answer("🚫 Maximum supply cannot be less than minimum. Please try again.\n\n/cancel — cancel")
            return
        
        config = await get_valid_config(message.from_user.id)
        config["PROFILES"][idx]["MIN_SUPPLY"] = data["MIN_SUPPLY"]
        config["PROFILES"][idx]["MAX_SUPPLY"] = value
        await save_config(config)

        try:
            await message.bot.delete_message(message.chat.id, data["message_id"])
        except Exception as e:
            logger.warning(f"Failed to delete message: {e}")

        await message.answer(
            profile_text(config["PROFILES"][idx], idx, message.from_user.id),
            reply_markup=profile_edit_keyboard(idx)
        )
        await state.clear()
    except ValueError:
        await message.answer("🚫 Enter a positive number. Please try again.\n\n/cancel — cancel")


@wizard_router.message(ConfigWizard.edit_limit)
async def step_edit_limit(message: Message, state: FSMContext):
    """
    Processes input from the user for a new limit (maximum amount of spending) for the profile.
    Checks validity, saves, and returns the user to the profile menu.
    """
    if await try_cancel(message, state):
        return
    
    if not message.text:
        await message.answer("🚫 Only text input is supported.\n\n/cancel — cancel")
        return

    data = await state.get_data()
    idx = data["profile_index"]

    try:
        value = int(message.text)
        if value <= 0:
            raise ValueError
        
        config = await get_valid_config(message.from_user.id)
        config["PROFILES"][idx]["LIMIT"] = value
        await save_config(config)

        try:
            await message.bot.delete_message(message.chat.id, data["message_id"])
        except Exception as e:
            logger.warning(f"Failed to delete message: {e}")

        await message.answer(
            profile_text(config["PROFILES"][idx], idx, message.from_user.id),
            reply_markup=profile_edit_keyboard(idx)
        )
        await state.clear()
    except ValueError:
        await message.answer("🚫 Enter a positive number. Please try again.\n\n/cancel — cancel")


@wizard_router.message(ConfigWizard.edit_count)
async def step_edit_count(message: Message, state: FSMContext):
    """
    Processes input from the user for a new number of gifts for the profile.
    Checks validity, saves, and returns the user to the profile menu.
    """
    if await try_cancel(message, state):
        return
    
    if not message.text:
        await message.answer("🚫 Only text input is supported.\n\n/cancel — cancel")
        return
    
    data = await state.get_data()
    idx = data["profile_index"]

    try:
        value = int(message.text)
        if value <= 0:
            raise ValueError
        
        config = await get_valid_config(message.from_user.id)
        config["PROFILES"][idx]["COUNT"] = value
        await save_config(config)

        try:
            await message.bot.delete_message(message.chat.id, data["message_id"])
        except Exception as e:
            logger.warning(f"Failed to delete message: {e}")

        await message.answer(
            profile_text(config["PROFILES"][idx], idx, message.from_user.id),
            reply_markup=profile_edit_keyboard(idx)
        )
        await state.clear()
    except ValueError:
        await message.answer("🚫 Enter a positive number. Please try again.\n\n/cancel — cancel")


@wizard_router.message(ConfigWizard.edit_user_id)
async def step_edit_user_id(message: Message, state: FSMContext):
    """
    Processes input from the user for a new recipient (user_id or @username) for the profile.
    Checks correctness, saves, and returns the user to the profile menu.
    """
    if await try_cancel(message, state):
        return
    
    if not message.text:
        await message.answer("🚫 Only text input is supported.\n\n/cancel — cancel")
        return
    
    data = await state.get_data()
    idx = data["profile_index"]

    user_input = message.text.strip()
    if user_input.startswith("@"):
        chat_type = await get_chat_type(bot=message.bot, username=user_input)
        if chat_type == "channel":
            target_chat = user_input
            target_user = None
            target_type = "channel"
        elif chat_type == "unknown":
            target_chat = user_input
            target_user = None
            target_type = "username"
        else:
            await message.answer("🚫 You entered an incorrect <b>channel username</b>. Please try again.\n\n/cancel — cancel")
            return
    elif user_input.isdigit():
        target_chat = None
        target_user = int(user_input)
        target_type = "user_id"
    else:
        await message.answer("🚫 Enter ID or @username of the channel. Please try again.\n\n/cancel — cancel")
        return
    
    config = await get_valid_config(message.from_user.id)
    config["PROFILES"][idx]["TARGET_USER_ID"] = target_user
    config["PROFILES"][idx]["TARGET_CHAT_ID"] = target_chat
    config["PROFILES"][idx]["TARGET_TYPE"] = target_type
    await save_config(config)

    try:
        await message.bot.delete_message(message.chat.id, data["message_id"])
    except Exception as e:
        logger.warning(f"Failed to delete message: {e}")

    await message.answer(
            profile_text(config["PROFILES"][idx], idx, message.from_user.id),
            reply_markup=profile_edit_keyboard(idx)
        )
    await state.clear()


@wizard_router.callback_query(F.data == "choose_sender_bot")
async def choose_sender_bot(call: CallbackQuery, state: FSMContext):
    """
    Handles selecting "Bot" as the sender when placing an order.
    """
    await save_sender_and_finish(call, state, sender="bot")

@wizard_router.callback_query(F.data == "choose_sender_userbot")
async def choose_sender_userbot(call: CallbackQuery, state: FSMContext):
    """
    Handles selecting "Userbot" as the sender when placing an order.
    """
    await save_sender_and_finish(call, state, sender="userbot")

async def save_sender_and_finish(call: CallbackQuery, state: FSMContext, sender: str):
    """
    Saves the selected sender (bot or userbot) in the FSM 
    and finishes the process, returning the user to the main menu.
    """
    data = await state.get_data()
    profile_data = data.get("profile_data")
    idx = data.get("profile_index")  # None — new, number — editing

    if not profile_data:
        await call.message.answer("❌ Error: profile not found.")
        await state.clear()
        return
    
    profile_data["SENDER"] = sender

    config = await get_valid_config(call.from_user.id)

    if idx is None:
        await add_profile(config, profile_data)
        msg = "✅ <b>New profile</b> created."
        await call.message.edit_text(msg)
        await profiles_menu(call.message, call.from_user.id)
    else:
        await update_profile(config, idx, profile_data)
        msg = f"✅ <b>Profile {idx + 1}</b> updated."
        await call.message.edit_text(msg)
        await call.message.answer(
            profile_text(config["PROFILES"][idx], idx, call.from_user.id),
            reply_markup=profile_edit_keyboard(idx)
        )

    await state.clear()
    await call.answer()

@wizard_router.callback_query(F.data == "profile_add")
async def on_profile_add(call: CallbackQuery, state: FSMContext):
    """
    Starts the wizard for step-by-step creation of a new profile for gifts.
    Moves the user to the first step of inputting parameters for a new profile.
    """
    await state.update_data(profile_index=None)
    await call.message.answer("➕ Adding <b>new profile</b>.\n\n"
                              "💰 Minimum gift price, for example: <code>5000</code>\n\n"
                              "/cancel — cancel", reply_markup=None)
    await state.set_state(ConfigWizard.min_price)
    await call.answer()


@wizard_router.message(ConfigWizard.user_id)
async def step_user_id(message: Message, state: FSMContext):
    """
    Processes input of the recipient's address (user ID or username) and saves the profile.
    """
    if await try_cancel(message, state):
        return
    
    if not message.text:
        await message.answer("🚫 Only text input is supported.\n\n/cancel — cancel")
        return

    user_input = message.text.strip()
    if user_input.startswith("@"):
        chat_type = await get_chat_type(bot=message.bot, username=user_input)
        if chat_type == "channel":
            target_chat = user_input
            target_user = None
            target_type = "channel"
        elif chat_type == "unknown":
            target_chat = user_input
            target_user = None
            target_type = "username"
        else:
            await message.answer("🚫 You entered an incorrect <b>channel username</b>. Please try again.\n\n/cancel — cancel")
            return
    elif user_input.isdigit():
        target_chat = None
        target_user = int(user_input)
        target_type = "user_id"
    else:
        await message.answer("🚫 Enter ID or @username of the channel. Please try again.\n\n/cancel — cancel")
        return

    data = await state.get_data()
    profile_data = {
        "MIN_PRICE": data["MIN_PRICE"],
        "MAX_PRICE": data["MAX_PRICE"],
        "MIN_SUPPLY": data["MIN_SUPPLY"],
        "MAX_SUPPLY": data["MAX_SUPPLY"],
        "LIMIT": data["LIMIT"],
        "COUNT": data["COUNT"],
        "TARGET_USER_ID": target_user,
        "TARGET_CHAT_ID": target_chat,
        "TARGET_TYPE": target_type,
        "BOUGHT": 0,
        "SPENT": 0,
        "DONE": False,
    }

    await state.update_data(profile_data=profile_data)

    # Move to the step of selecting a sender
    await message.answer("📤 Select <b>sender</b> of gifts:\n\n"
                         "🤖 <code>Bot</code> - purchases from bot balance\n"
                         "👤 <code>Userbot</code> - purchases from userbot balance\n\n"
                         "/cancel — cancel",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🤖 Bot", callback_data="choose_sender_bot"),
                InlineKeyboardButton(text="👤 Userbot", callback_data="choose_sender_userbot")
            ]
        ])
    )
    await state.set_state(ConfigWizard.gift_sender)


@wizard_router.callback_query(F.data == "profiles_main_menu")
async def profiles_main_menu_callback(call: CallbackQuery, state: FSMContext):
    """
    Shows the main menu by clicking the "Menu" button.
    Clears all FSM states for the user.
    """
    await state.clear()
    await call.answer()
    await safe_edit_text(call.message, "✅ Profile editing completed.", reply_markup=None)
    await refresh_balance(call.bot, call.from_user.id)
    await update_menu(
        bot=call.bot,
        chat_id=call.message.chat.id,
        user_id=call.from_user.id,
        message_id=call.message.message_id
    )


@wizard_router.callback_query(lambda c: c.data.startswith("profile_delete_"))
async def on_profile_delete_confirm(call: CallbackQuery, state: FSMContext):
    """
    Requests confirmation of profile deletion.
    """
    idx = int(call.data.split("_")[-1])
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Yes", callback_data=f"confirm_delete_{idx}"),
                InlineKeyboardButton(text="❌ No", callback_data=f"cancel_delete_{idx}"),
            ]
        ]
    )
    config = await get_valid_config(call.from_user.id)
    profiles = config.get("PROFILES", [])
    profile = profiles[idx]
    target_display = get_target_display(profile, call.from_user.id)
    profile_name = f'Profile {idx + 1}' if  not profile.get('name') else profile.get('name')
    message = (f"┌🏷️ <b>{profile_name}</b> (bought {profile.get('BOUGHT'):,} from {profile.get('COUNT'):,})\n"
            f"├💰 <b>Price</b>: {profile.get('MIN_PRICE'):,} – {profile.get('MAX_PRICE'):,} ★\n"
            f"├📦 <b>Supply</b>: {profile.get('MIN_SUPPLY'):,} – {profile.get('MAX_SUPPLY'):,}\n"
            f"├⭐️ <b>Limit</b>: {profile.get('SPENT'):,} / {profile.get('LIMIT'):,} ★\n"
            f"├👤 <b>Recipient</b>: {target_display}\n"
            f"└📤 <b>Sender</b>: {sender}")
    await call.message.edit_text(
        f"⚠️ Are you sure you want to <b>delete</b> the profile?\n\n{message}",
        reply_markup=kb
    )
    await call.answer()


@wizard_router.callback_query(lambda c: c.data.startswith("confirm_delete_"))
async def on_profile_delete_final(call: CallbackQuery):
    """
    Deletes the profile permanently after confirmation.
    """
    idx = int(call.data.split("_")[-1])
    config = await get_valid_config(call.from_user.id)
    deafult_added = ("\n➕ <b>Added</b> default profile.\n"
                     "🚦 Status changed to 🔴 (inactive)." if len(config["PROFILES"]) == 1 else "")
    if len(config["PROFILES"]) == 1:
        config["ACTIVE"] = False
        await save_config(config)
    await remove_profile(config, idx, call.from_user.id)
    await call.message.edit_text(f"✅ <b>Profile {idx + 1}</b> deleted.{deafult_added}", reply_markup=None)
    await profiles_menu(call.message, call.from_user.id)
    await call.answer()


@wizard_router.callback_query(lambda c: c.data.startswith("cancel_delete_"))
async def on_profile_delete_cancel(call: CallbackQuery):
    """
    Cancels profile deletion.
    """
    idx = int(call.data.split("_")[-1])
    await call.message.edit_text(f"🚫 Deletion of <b>profile {idx + 1}</b> cancelled.", reply_markup=None)
    await profiles_menu(call.message, call.from_user.id)
    await call.answer()


async def safe_edit_text(message, text, reply_markup=None):
    """
    Safely edits the text of a message, ignoring errors "can't be edited" and "message not found".
    """
    try:
        await message.edit_text(text, reply_markup=reply_markup)
        return True
    except TelegramBadRequest as e:
        if "message can't be edited" in str(e) or "message to edit not found" in str(e):
            # Simply ignore — message outdated or deleted
            return False
        else:
            raise


@wizard_router.callback_query(F.data == "edit_config")
async def edit_config_handler(call: CallbackQuery, state: FSMContext):
    """
    Starts the configuration editing wizard.
    """
    await call.message.answer("💰 Minimum gift price, for example: <code>5000</code>\n\n/cancel — cancel")
    await state.set_state(ConfigWizard.min_price)
    await call.answer()


@wizard_router.message(ConfigWizard.min_price)
async def step_min_price(message: Message, state: FSMContext):
    """
    Processes input of the minimum gift price.
    """
    if await try_cancel(message, state):
        return
    
    if not message.text:
        await message.answer("🚫 Only text input is supported.\n\n/cancel — cancel")
        return
    
    try:
        value = int(message.text)
        if value <= 0:
            raise ValueError
        await state.update_data(MIN_PRICE=value)
        await message.answer("💰 Maximum gift price, for example: <code>10000</code>\n\n/cancel — cancel")
        await state.set_state(ConfigWizard.max_price)
    except ValueError:
        await message.answer("🚫 Enter a positive number. Please try again.\n\n/cancel — cancel")


@wizard_router.message(ConfigWizard.max_price)
async def step_max_price(message: Message, state: FSMContext):
    """
    Processes input of the maximum gift price and checks the validity of the range.
    """
    if await try_cancel(message, state):
        return
    
    if not message.text:
        await message.answer("🚫 Only text input is supported.\n\n/cancel — cancel")
        return
    
    try:
        value = int(message.text)
        if value <= 0:
            raise ValueError

        data = await state.get_data()
        min_price = data.get("MIN_PRICE")
        if min_price and value < min_price:
            await message.answer("🚫 Maximum price cannot be less than minimum. Please try again.\n\n/cancel — cancel")
            return

        await state.update_data(MAX_PRICE=value)
        await message.answer("📦 Minimum supply for gift, for example: <code>1000</code>\n\n/cancel — cancel")
        await state.set_state(ConfigWizard.min_supply)
    except ValueError:
        await message.answer("🚫 Enter a positive number. Please try again.\n\n/cancel — cancel")


@wizard_router.message(ConfigWizard.min_supply)
async def step_min_supply(message: Message, state: FSMContext):
    """
    Processes input of the minimum supply for the gift.
    """
    if await try_cancel(message, state):
        return
    
    if not message.text:
        await message.answer("🚫 Only text input is supported.\n\n/cancel — cancel")
        return
    
    try:
        value = int(message.text)
        if value <= 0:
            raise ValueError
        await state.update_data(MIN_SUPPLY=value)
        await message.answer("📦 Maximum supply for gift, for example: <code>10000</code>\n\n/cancel — cancel")
        await state.set_state(ConfigWizard.max_supply)
    except ValueError:
        await message.answer("🚫 Enter a positive number. Please try again.\n\n/cancel — cancel")


@wizard_router.message(ConfigWizard.max_supply)
async def step_max_supply(message: Message, state: FSMContext):
    """
    Processes input of the maximum supply for the gift, checks the range.
    """
    if await try_cancel(message, state):
        return
    
    if not message.text:
        await message.answer("🚫 Only text input is supported.\n\n/cancel — cancel")
        return
    
    try:
        value = int(message.text)
        if value <= 0:
            raise ValueError

        data = await state.get_data()
        min_supply = data.get("MIN_SUPPLY")
        if min_supply and value < min_supply:
            await message.answer("🚫 Maximum supply cannot be less than minimum. Please try again.\n\n/cancel — cancel")
            return

        await state.update_data(MAX_SUPPLY=value)
        await message.answer("🎁 Maximum number of gifts, for example: <code>5</code>\n\n/cancel — cancel")
        await state.set_state(ConfigWizard.count)
    except ValueError:
        await message.answer("🚫 Enter a positive number. Please try again.\n\n/cancel — cancel")


@wizard_router.message(ConfigWizard.count)
async def step_count(message: Message, state: FSMContext):
    """
    Processes input of the number of gifts.
    """
    if await try_cancel(message, state):
        return
    
    if not message.text:
        await message.answer("🚫 Only text input is supported.\n\n/cancel — cancel")
        return

    try:
        value = int(message.text)
        if value <= 0:
            raise ValueError
        await state.update_data(COUNT=value)
        await message.answer(
            "⭐️ Enter the number of stars for this profile (for example: <code>10000</code>)\n\n"
            "/cancel — cancel"
        )
        await state.set_state(ConfigWizard.limit)
    except ValueError:
        await message.answer("🚫 Enter a positive number. Please try again.\n\n/cancel — cancel")


@wizard_router.message(ConfigWizard.limit)
async def step_limit(message: Message, state: FSMContext):
    """
    Processes input of the number of stars for an order.
    """
    if await try_cancel(message, state):
        return
    
    if not message.text:
        await message.answer("🚫 Only text input is supported.\n\n/cancel — cancel")
        return

    try:
        value = int(message.text)
        if value <= 0:
            raise ValueError
        await state.update_data(LIMIT=value)
        message_text = ("📥 Enter <b>recipient</b> of the gift:\n\n"
                        "🤖 If <b>sender</b> <code>Bot</code> enter:\n"
                        f"➤ <b>User ID</b> (for example your: <code>{message.from_user.id}</code>)\n"
                        "➤ <b>channel username</b> (for example: <code>@mirvaId</code>)\n\n"
                        "👤 If <b>sender</b> <code>Userbot</code> enter:\n"
                        "➤ <b>username</b> of the user (for example: <code>@mirvaId</code>)\n"
                        "➤ <b>channel username</b> (for example: <code>@mirvaId</code>)\n\n"
                        "🔎 <b>Find user ID</b> here: @userinfobot\n\n"
                        "⚠️ In order for the <code>Userbot</code> account to send a gift to another account, there must be a conversation between accounts.\n\n"
                        "/cancel — cancel")
        await message.answer(message_text)
        await state.set_state(ConfigWizard.user_id)
    except ValueError:
        await message.answer("🚫 Enter a positive number. Please try again.\n\n/cancel — cancel")


@wizard_router.callback_query(F.data == "deposit_menu")
async def deposit_menu(call: CallbackQuery, state: FSMContext):
    """
    Moves to the step of topping up the balance.
    """
    await call.message.answer("💰 Enter the amount to top up, for example: <code>5000</code>\n\n/cancel — cancel")
    await state.set_state(ConfigWizard.deposit_amount)
    await call.answer()


@wizard_router.message(ConfigWizard.deposit_amount)
async def deposit_amount_input(message: Message, state: FSMContext):
    """
    Processes the amount for topping up and sends an invoice for payment.
    """
    if await try_cancel(message, state):
        return
    
    if not message.text:
        await message.answer("🚫 Only text input is supported.\n\n/cancel — cancel")
        return

    try:
        amount = int(message.text)
        if amount < 1 or amount > 10000:
            raise ValueError
        prices = [LabeledPrice(label=CURRENCY, amount=amount)]
        await message.answer_invoice(
            title="Bot for gifts",
            description="Topping up balance",
            prices=prices,
            provider_token="",  # Use your token
            payload="stars_deposit",
            currency=CURRENCY,
            start_parameter="deposit",
            reply_markup=payment_keyboard(amount=amount),
        )
        await state.clear()
    except ValueError:
        await message.answer("🚫 Enter a number between 1 and 10000. Please try again.\n\n/cancel — cancel")


@wizard_router.callback_query(F.data == "refund_menu")
async def refund_menu(call: CallbackQuery, state: FSMContext):
    """
    Moves to the step of returning stars (by transaction ID).
    """
    await call.message.answer("↩️ <b>Withdraw stars from</b> <code>Bot</code>.\n\n"
                              "📤 Send the next message <b>transaction ID</b>.\n\n"
                              "🛠 Additional features:\n\n"
                              "/withdraw_all — withdraw all balance.\n\n"
                              "/refund + <code>[user_id]</code> + <code>[transaction_id]</code> — return stars to a specific user by <b>transaction ID</b>. For example: <code>/refund 12345678 abCdEF1g23hkL</code>\n\n"
                              "🚫 You cannot withdraw stars from <code>Userbot</code>.\n\n"
                              "/cancel — cancel")
    await state.set_state(ConfigWizard.refund_id)
    await call.answer()


@wizard_router.message(ConfigWizard.refund_id)
async def refund_input(message: Message, state: FSMContext):
    """
    Processes return by transaction ID. Also supports the /withdraw_all command.
    """
    if not message.text:
        await message.answer("🚫 Only text input is supported.\n\n/cancel — cancel")
        return
    
    if message.text and message.text.strip().lower() == "/withdraw_all":
        await state.clear()
        await withdraw_all_handler(message)
        return
    
    if message.text and message.text.strip().lower() == "/refund":
        await state.clear()
        await refund_handler(message)
        return
    
    if await try_cancel(message, state):
        return

    txn_id = message.text.strip()
    try:
        await message.bot.refund_star_payment(
            user_id=message.from_user.id,
            telegram_payment_charge_id=txn_id
        )
        await message.answer("✅ Refund completed successfully.")
        balance = await refresh_balance(message.bot)
        await update_menu(bot=message.bot, chat_id=message.chat.id, user_id=message.from_user.id, message_id=message.message_id)
    except Exception as e:
        await message.answer(f"🚫 Error when refunding:\n<code>{e}</code>")
    await state.clear()


@wizard_router.callback_query(F.data == "guest_deposit_menu")
async def guest_deposit_menu(call: CallbackQuery, state: FSMContext):
    """
    Moves to the step of topping up the balance for guests.
    """
    await call.message.answer("💰 Enter the amount to top up, for example: <code>5000</code>")
    await state.set_state(ConfigWizard.guest_deposit_amount)
    await call.answer()


@wizard_router.message(ConfigWizard.guest_deposit_amount)
async def guest_deposit_amount_input(message: Message, state: FSMContext):
    """
    Processes the amount for topping up and sends an invoice for payment for guests.
    """
    if await try_cancel(message, state):
        return
    
    if not message.text:
        await message.answer("🚫 Only text input is supported.\n\n⚠️ Operation completed, please try again.")
        return

    try:
        amount = int(message.text)
        if amount < 1 or amount > 10000:
            raise ValueError
        prices = [LabeledPrice(label=CURRENCY, amount=amount)]
        await message.answer_invoice(
            title="Bot for gifts",
            description="Topping up balance",
            prices=prices,
            provider_token="",  # Use your token
            payload="stars_deposit",
            currency=CURRENCY,
            start_parameter="deposit",
            reply_markup=payment_keyboard(amount=amount),
        )
        await state.clear()
    except ValueError:
        await state.clear()
        await message.answer("🚫 Expected a number between 1 and 10000.\n\n⚠️ Operation completed, please try again.")
        

@wizard_router.message(Command("withdraw_all"))
async def withdraw_all_handler(message: Message):
    """
    Command to withdraw all stars from the bot's balance.
    """
    # В публичном режиме разрешаем всем пользователям
    user_id = message.from_user.id
    config = await get_valid_config(user_id)
    balance = config.get("BALANCE", 0)

    if balance <= 0:
        await message.answer("⚠️ <b>No stars</b> on the balance.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Yes", callback_data="withdraw_all_confirm"),
            InlineKeyboardButton(text="❌ No", callback_data="withdraw_all_cancel")
        ]
    ])
    await message.answer(
        f"⚠️ <b>Withdraw all stars</b> ({balance:,} ★)?",
        reply_markup=kb
    )


@wizard_router.callback_query(lambda c: c.data == "withdraw_all_confirm")
async def withdraw_all_confirmed(call: CallbackQuery):
    """
    Confirms and starts the process of returning all stars. Displays a report to the user.
    """
    await call.message.edit_text("⏳ Withdrawing stars...")  # can add output/report here

    async def send_status(msg):
        await call.message.answer(msg)

    await call.answer()

    result = await refund_all_star_payments(
        bot=call.bot,
        user_id=call.from_user.id,
        username=call.from_user.username,
        message_func=send_status,
    )
    if result["count"] > 0:
        msg = f"✅ Refunded: ★{result['refunded']}\n🔄 Transactions: {result['count']}"
        if result["left"] > 0:
            msg += f"\n💰 Remaining stars: {result['left']}"
            dep = result.get("next_deposit")
            if dep:
                need = dep['amount'] - result['left']
                msg += (
                    f"\n➕ Top up balance by at least ★{need} (or total up to ★{dep['amount']})."
                )
        await call.message.answer(msg)
    else:
        await call.message.answer("🚫 No stars found for refund.")

    balance = await refresh_balance(call.bot, call.from_user.id)
    await update_menu(bot=call.bot, chat_id=call.message.chat.id, user_id=call.from_user.id, message_id=call.message.message_id)


@wizard_router.callback_query(lambda c: c.data == "withdraw_all_cancel")
async def withdraw_all_cancel(call: CallbackQuery):
    """
    Handles cancellation of returning all stars.
    """
    await call.message.edit_text("🚫 Action cancelled.")
    await call.answer()
    await update_menu(bot=call.bot, chat_id=call.message.chat.id, user_id=call.from_user.id, message_id=call.message.message_id)


@wizard_router.message(Command("refund"))
async def refund_handler(message: Message):
    """
    Command for returning stars by transaction ID.
    Format: /refund USER_ID TRANSACTION_ID
    """
    # В публичном режиме разрешаем всем пользователям
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer(
            "⚠️ <b>Invalid format.</b>\n\n"
            "Format: <code>/refund USER_ID TRANSACTION_ID</code>\n\n"
            "Example: <code>/refund 123456789 12345678901234567890_123456789_external</code>"
        )
        return

    try:
        target_user_id = int(parts[1])
        transaction_id = parts[2]
    except ValueError:
        await message.answer("⚠️ <b>Invalid USER_ID.</b> It must be a number.")
        return

    try:
        await message.bot.refund_star_payment(
            user_id=target_user_id,
            telegram_payment_charge_id=transaction_id
        )
        await message.answer(f"✅ Refund completed for transaction <code>{transaction_id}</code> for user <code>{target_user_id}</code>.")
        await update_menu(bot=message.bot, chat_id=message.chat.id, user_id=message.from_user.id, message_id=message.message_id)
    except Exception as e:
        error_text = str(e)
        short_error = error_text.split(":")[-1].strip()
        await message.answer(f"🚫 Error when refunding transaction <code>{transaction_id}</code>:\n\n<code>{short_error}</code>")
        await update_menu(bot=message.bot, chat_id=message.chat.id, user_id=message.from_user.id, message_id=message.message_id)


# ------------- Additional functions ---------------------


async def try_cancel(message: Message, state: FSMContext) -> bool:
    """
    Checks if the user entered /cancel, and cancels the wizard if so.
    """
    if message.text and message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("🚫 Action cancelled.")
        await update_menu(bot=message.bot, chat_id=message.chat.id, user_id=message.from_user.id, message_id=message.message_id)
        return True
    return False


async def get_chat_type(bot: Bot, username: str):
    """
    Determines the type of Telegram object based on username for channels.
    """
    if not username.startswith("@"):
        username = "@" + username
    try:
        chat = await bot.get_chat(username)
        if chat.type == "private":
            if getattr(chat, "is_bot", False):
                return "bot"
            else:
                return "user"
        elif chat.type == "channel":
            return "channel"
        elif chat.type in ("group", "supergroup"):
            return "group"
        else:
            return chat.type  # just in case
    except TelegramAPIError as e:
        logger.error(f"TelegramAPIError when getting channel username: {e}")
        return "unknown"
    except Exception as e:
        logger.error(f"Error when getting channel username: {e}")
        return "unknown"
    

def register_wizard_handlers(dp):
    """
    Registers wizard_router in the dispatcher (Dispatcher).
    """
    dp.include_router(wizard_router)
