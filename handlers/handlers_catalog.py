# --- Standard libraries ---
import asyncio

# --- Third-party libraries ---
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest

# --- Internal modules ---
from services.config import get_target_display_local, PURCHASE_COOLDOWN
from services.menu import update_menu
from services.gifts_bot import get_filtered_gifts
from services.buy_bot import buy_gift
from services.buy_userbot import buy_gift_userbot
from services.balance import refresh_balance

wizard_router = Router()

class CatalogFSM(StatesGroup):
    """
    States for the FSM Gift Catalog.
    """
    waiting_gift = State()
    waiting_quantity = State()
    waiting_recipient = State()
    waiting_sender = State()
    waiting_confirm = State()


def gifts_catalog_keyboard(gifts):
    """
    Generates a keyboard for the gift catalog. 
    Each gift is a separate button, plus a button to return to the main menu.
    """
    keyboard = []
    for gift in gifts:
        if gift['supply'] == None:
            btn = InlineKeyboardButton(
                text=f"{gift['emoji']} — ★{gift['price']:,}",
                callback_data=f"catalog_gift_{gift['id']}"
            )
        else:
            btn = InlineKeyboardButton(
                text=f"{gift['left']:,} out of {gift['supply']:,} — ★{gift['price']:,}",
                callback_data=f"catalog_gift_{gift['id']}"
            )
        keyboard.append([btn])

    # Button to return to the main menu
    keyboard.append([
        InlineKeyboardButton(
            text="☰ Menu", 
            callback_data="catalog_main_menu"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@wizard_router.callback_query(F.data == "catalog")
async def catalog(call: CallbackQuery, state: FSMContext):
    """
    Processing the opening of the catalog. Receives a list of gifts and generates a message with a keyboard.
    """
    gifts = await get_filtered_gifts(
        bot=call.bot,
        min_price=0,
        max_price=1000000,
        min_supply=0,
        max_supply=100000000,
        unlimited = True
    )

    # Save the current catalog in FSM — needed for subsequent steps
    await state.update_data(gifts_catalog=gifts)

    gifts_limited = [g for g in gifts if g['supply'] != None]
    gifts_unlimited = [g for g in gifts if g['supply'] == None]

    await call.message.answer(
        f"🧸 Ordinary gifts: <b>{len(gifts_unlimited)}</b>\n"
        f"👜 Unique gifts: <b>{len(gifts_limited)}</b>\n",
        reply_markup=gifts_catalog_keyboard(gifts)
    )

    await call.answer()


@wizard_router.callback_query(F.data == "catalog_main_menu")
async def start_callback(call: CallbackQuery, state: FSMContext):
    """
    Shows the main menu by clicking the "Menu" button.
    Clears all FSM states for the user.
    """
    await state.clear()
    await call.answer()
    await safe_edit_text(call.message, "🚫 Catalog closed.", reply_markup=None)
    await refresh_balance(call.bot)
    await update_menu(
        bot=call.bot,
        chat_id=call.message.chat.id,
        user_id=call.from_user.id,
        message_id=call.message.message_id
    )


@wizard_router.callback_query(F.data.startswith("catalog_gift_"))
async def on_gift_selected(call: CallbackQuery, state: FSMContext):
    """
    Handler for selecting a gift from the catalog. Requests the number of gifts to purchase from the user.
    """
    gift_id = call.data.split("_")[-1]
    data = await state.get_data()
    gifts = data.get("gifts_catalog", [])
    if not gifts:
        await call.answer("🚫 Catalog is outdated. Open again.", show_alert=True)
        await safe_edit_text(call.message, "🚫 Catalog is outdated. Open again.", reply_markup=None)
        return
    gift = next((g for g in gifts if str(g['id']) == gift_id), None)

    gift_display = f"{gift['left']:,} out of {gift['supply']:,}" if gift.get("supply") != None else gift.get("emoji")

    await state.update_data(selected_gift=gift)
    await call.message.edit_text(
        f"🎯 You selected: <b>{gift_display}</b> for ★{gift['price']}\n"
        f"🎁 Enter <b>quantity</b> to purchase:\n\n"
        f"/cancel - to cancel",
        reply_markup=None
    )
    await state.set_state(CatalogFSM.waiting_quantity)
    await call.answer()


@wizard_router.message(CatalogFSM.waiting_quantity)
async def on_quantity_entered(message: Message, state: FSMContext):
    """
    Handler for processing the input of the number of gifts to purchase for the selected gift.
    Now we go to the step of entering the recipient.
    """
    if await try_cancel(message, state):
        return
    
    if not message.text:
        await message.answer("🚫 Only text input is supported.\n\n/cancel — cancel")
        return
    
    try:
        qty = int(message.text)
        if qty <= 0:
            raise ValueError
    except Exception:
        await message.answer("🚫 Enter a positive integer!\n\n/cancel — cancel")
        return
    
    await state.update_data(selected_qty=qty)

    message_text = ("📥 Enter the <b>recipient</b> of the gift:\n\n"
                    "🤖 If the <b>sender</b> is <code>Bot</code> enter:\n"
                    f"➤ <b>User ID</b> (e.g. your: <code>{message.from_user.id}</code>)\n"
                    "➤ <b>channel username</b> (e.g. <code>@mirvaId</code>)\n\n"
                    "👤 If the <b>sender</b> is <code>Userbot</code> enter:\n"
                    "➤ <b>username</b> of the user (e.g. <code>@mirvaId</code>)\n"
                    "➤ <b>username</b> of the channel (e.g. <code>@mirvaId</code>)\n\n"
                    "🔎 <b>Get User ID</b> here: @userinfobot\n"
                    "⚠️ To send a gift to another account, there must be a conversation between accounts.\n\n"
                    "/cancel — cancel")
    await message.answer(message_text)
    await state.set_state(CatalogFSM.waiting_recipient)


@wizard_router.message(CatalogFSM.waiting_recipient)
async def on_recipient_entered(message: Message, state: FSMContext):
    """
    Processes the input of the recipient — ID or username.
    """
    if await try_cancel(message, state):
        return
    
    if not message.text:
        await message.answer("🚫 Only text input is supported.\n\n/cancel — cancel")
        return

    user_input = message.text.strip()
    if user_input.startswith("@"):
        target_chat_id = user_input
        target_user_id = None
    elif user_input.isdigit():
        target_chat_id = None
        target_user_id = int(user_input)
    else:
        await message.answer(
            "🚫 If the recipient is an account, enter the ID, if the channel — username with @. Try again."
        )
        return

    await state.update_data(
        target_user_id=target_user_id,
        target_chat_id=target_chat_id
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🤖 Bot", callback_data="catalog_sender_bot"),
                InlineKeyboardButton(text="👤 Userbot", callback_data="catalog_sender_userbot"),
            ],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_purchase")]
        ]
    )
    message_text = ("📤 Select the <b>sender</b> of the gifts:\n\n"
                    "🤖 <code>Bot</code> - purchases from the bot's balance\n"
                    "👤 <code>Userbot</code> - purchases from the userbot's balance\n\n"
                    "/cancel — cancel")
    await message.answer(message_text, reply_markup=kb)
    await state.set_state(CatalogFSM.waiting_sender)


@wizard_router.callback_query(F.data.startswith("catalog_sender_"))
async def on_catalog_sender_selected(call: CallbackQuery, state: FSMContext):
    """
    Processes the selection of the sender (bot or userbot).
    """
    sender = call.data.replace("catalog_sender_", "")
    await state.update_data(sender=sender)
    await call.answer("✅ Sender selected.")

    data = await state.get_data()
    gift = data["selected_gift"]
    qty = data["selected_qty"]
    price = gift.get("price")
    total = price * qty
    target_user_id = data.get("target_user_id")
    target_chat_id = data.get("target_chat_id")

    gift_display = f"{gift['left']:,} out of {gift['supply']:,}" if gift.get("supply") is not None else gift.get("emoji")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Confirm", callback_data="confirm_purchase"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_purchase"),
            ]
        ]
    )

    recipient_display = get_target_display_local(target_user_id, target_chat_id, call.from_user.id)

    await call.message.edit_text(
        f"📦 Gift: <b>{gift_display}</b>\n"
        f"🎁 Quantity: <b>{qty}</b>\n"
        f"💵 Gift price: <b>★{price:,}</b>\n"
        f"💰 Total amount: <b>★{total:,}</b>\n"
        f"👤 Recipient: {recipient_display}\n"
        f"📤 Sender: {'🤖 Bot' if sender == 'bot' else '👤 Userbot'}",
        reply_markup=kb
    )

    await state.set_state(CatalogFSM.waiting_confirm)


@wizard_router.callback_query(F.data == "confirm_purchase")
async def confirm_purchase(call: CallbackQuery, state: FSMContext):
    """
    Confirmation and launch of the purchase of the selected gift in the specified number for the selected recipient.
    """
    data = await state.get_data()
    sender = data["sender"]
    gift = data["selected_gift"]
    if not gift:
        await call.answer("🚫 The purchase request is not valid. Please try again.", show_alert=True)
        await safe_edit_text(call.message, "🚫 The purchase request is not valid. Please try again.", reply_markup=None)
        return
    await call.message.edit_text(text="⏳ Performing the purchase of gifts...", reply_markup=None)
    gift_id = gift.get("id")
    gift_price = gift.get("price")
    qty = data["selected_qty"]
    data_target_user_id=data.get("target_user_id")
    data_target_chat_id=data.get("target_chat_id")
    gift_display = f"{gift['left']:,} out of {gift['supply']:,}" if gift.get("supply") != None else gift.get("emoji")

    bought = 0
    while bought < qty:
        if sender == 'bot':
            success = await buy_gift(
                bot=call.bot,
                env_user_id=call.from_user.id,
                gift_id=gift_id,
                user_id=data_target_user_id,
                chat_id=data_target_chat_id,
                gift_price=gift_price,
                file_id=None
            )
        elif sender == 'userbot':
            success = await buy_gift_userbot(
                session_user_id=call.from_user.id,
                gift_id=gift_id,
                target_user_id=data_target_user_id,
                target_chat_id=data_target_chat_id,
                gift_price=gift_price,
                file_id=None
            )
        else:
            success = False

        if not success:
            break

        bought += 1
        await asyncio.sleep(PURCHASE_COOLDOWN)

    if bought == qty:
        await call.message.answer(f"✅ Purchase of <b>{gift_display}</b> completed successfully!\n"
                                  f"🎁 Purchased gifts: <b>{bought}</b> of <b>{qty}</b>\n"
                                  f"👤 Recipient: {get_target_display_local(data_target_user_id, data_target_chat_id, call.from_user.id)}")
    else:
        await call.message.answer(f"⚠️ Purchase of <b>{gift_display}</b> stopped.\n"
                                  f"🎁 Purchased gifts: <b>{bought}</b> of <b>{qty}</b>\n"
                                  f"👤 Recipient: {get_target_display_local(data_target_user_id, data_target_chat_id, call.from_user.id)}\n"
                                  f"💰 Top up the balance! Check the recipient's address!\n"
                                  f"📦 Check the availability of the gift!\n"
                                  f"🚦 Status changed to 🔴 (inactive).")
    
    await state.clear()
    await call.answer()
    await update_menu(bot=call.bot, chat_id=call.message.chat.id, user_id=call.from_user.id, message_id=call.message.message_id)


@wizard_router.callback_query(lambda c: c.data == "cancel_purchase")
async def cancel_callback(call: CallbackQuery, state: FSMContext):
    """
        Cancellation of the purchase of a gift at the confirmation stage.
    """
    await state.clear()
    await call.answer()
    await safe_edit_text(call.message, "🚫 Action cancelled.", reply_markup=None)
    await update_menu(bot=call.bot, chat_id=call.message.chat.id, user_id=call.from_user.id, message_id=call.message.message_id)


async def try_cancel(message: Message, state: FSMContext) -> bool:
    """
    Universal function for processing the cancellation of any step using /cancel.
    Clears the state, returns True if the cancellation was made.
    """
    if message.text and message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("🚫 Action cancelled.")
        await update_menu(bot=message.bot, chat_id=message.chat.id, user_id=message.from_user.id, message_id=message.message_id)
        return True
    return False


async def safe_edit_text(message, text, reply_markup=None):
    """
    Safely edits the message text, ignoring the "cannot be edited" and "message not found" errors.
    """
    try:
        await message.edit_text(text, reply_markup=reply_markup)
        return True
    except TelegramBadRequest as e:
        if "message can't be edited" in str(e) or "message to edit not found" in str(e):
            # Simply ignore — the message is outdated or deleted
            return False
        else:
            raise


def register_catalog_handlers(dp):
    """
    Registers all handlers related to the gift catalog.
    """
    dp.include_router(wizard_router)
