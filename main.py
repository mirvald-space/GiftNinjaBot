# --- Standard libraries ---
import asyncio
import logging
import os
import sys

# --- Third-party libraries ---
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

# --- Internal modules ---
from services.config import (
    ensure_config,
    save_config,
    get_valid_config,
    get_target_display,
    migrate_config_if_needed,
    add_allowed_user,
    DEFAULT_CONFIG,
    VERSION,
    PURCHASE_COOLDOWN
)
from services.menu import update_menu
from services.balance import refresh_balance
from services.gifts_manager import get_best_gift_list, userbot_gifts_updater
from services.buy_bot import buy_gift
from services.buy_userbot import buy_gift_userbot
from services.userbot import try_start_userbot_from_config
from handlers.handlers_wizard import register_wizard_handlers
from handlers.handlers_catalog import register_catalog_handlers
from handlers.handlers_main import register_main_handlers
from utils.logging import setup_logging
from utils.proxy import get_aiohttp_session
from middlewares.access_control import AccessControlMiddleware
from middlewares.rate_limit import RateLimitMiddleware

load_dotenv(override=False)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
USER_ID = int(os.getenv("TELEGRAM_USER_ID"))
default_config = DEFAULT_CONFIG(USER_ID)
ALLOWED_USER_IDS = []
ALLOWED_USER_IDS.append(USER_ID)
add_allowed_user(USER_ID)

setup_logging()
logger = logging.getLogger(__name__)


async def gift_purchase_worker(bot):
    """
    Background worker for purchasing gifts by profiles.
    Now takes into account the LIMIT parameter - the maximum amount of stars that can be spent on a profile.
    If the limit is exhausted - the profile is considered completed and the worker moves to the next one.
    """
    await refresh_balance(bot)
    while True:
        try:
            config = await get_valid_config(USER_ID)

            if not config["ACTIVE"]:
                await asyncio.sleep(1)
                continue

            message = None
            report_message_lines = []
            progress_made = False  # Was there progress on profiles in this run
            any_success = True

            for profile_index, profile in enumerate(config["PROFILES"]):
                # Skip completed profiles
                if profile.get("DONE"):
                    continue
                # Skip profiles with disabled userbot
                sender = profile.get("SENDER", "bot")
                if sender == "userbot":
                    userbot_config = config.get("USERBOT", {})
                    if not userbot_config.get("ENABLED", False):
                        continue

                COUNT = profile["COUNT"]
                LIMIT = profile.get("LIMIT", 0)
                TARGET_USER_ID = profile["TARGET_USER_ID"]
                TARGET_CHAT_ID = profile["TARGET_CHAT_ID"]

                filtered_gifts = await get_best_gift_list(bot, profile)

                if not filtered_gifts:
                    continue

                purchases = []
                before_bought = profile["BOUGHT"]
                before_spent = profile["SPENT"]

                for gift in filtered_gifts:
                    gift_id = gift["id"]
                    gift_price = gift["price"]
                    gift_total_count = gift["supply"]
                    sticker_file_id = gift["sticker_file_id"]

                    # Check the limit before each purchase
                    while (profile["BOUGHT"] < COUNT and
                           profile["SPENT"] + gift_price <= LIMIT):

                        sender = profile.get("SENDER", "bot")
                        if sender == "bot":
                            success = await buy_gift(
                                bot=bot,
                                env_user_id=USER_ID,
                                gift_id=gift_id,
                                user_id=TARGET_USER_ID,
                                chat_id=TARGET_CHAT_ID,
                                gift_price=gift_price,
                                file_id=sticker_file_id
                            )
                        elif sender == "userbot":
                            userbot_config = config.get("USERBOT", {})
                            success = await buy_gift_userbot(
                                session_user_id=USER_ID,
                                gift_id=gift_id,
                                target_user_id=TARGET_USER_ID,
                                target_chat_id=TARGET_CHAT_ID,
                                gift_price=gift_price,
                                file_id=sticker_file_id
                            )
                        else:
                            logger.warning(f"Unknown sender SENDER={sender} in profile {profile_index}")
                            success = False

                        if not success:
                            any_success = False
                            break  # Failed to buy - try the next gift

                        config = await get_valid_config(USER_ID)
                        profile = config["PROFILES"][profile_index]
                        profile["BOUGHT"] += 1
                        profile["SPENT"] += gift_price
                        purchases.append({"id": gift_id, "price": gift_price})
                        await save_config(config)
                        await asyncio.sleep(PURCHASE_COOLDOWN)

                        # Check: have we reached the limit after the purchase
                        if profile["SPENT"] >= LIMIT:
                            break

                    if profile["BOUGHT"] >= COUNT or profile["SPENT"] >= LIMIT:
                        break  # Reached the limit either by quantity or by amount

                after_bought = profile["BOUGHT"]
                after_spent = profile["SPENT"]
                made_local_progress = (after_bought > before_bought) or (after_spent > before_spent)

                # Profile is fully completed: either by quantity or by limit
                if (profile["BOUGHT"] >= COUNT or profile["SPENT"] >= LIMIT) and not profile["DONE"]:
                    config = await get_valid_config(USER_ID)
                    profile = config["PROFILES"][profile_index]
                    profile["DONE"] = True
                    await save_config(config)

                    target_display = get_target_display(profile, USER_ID)
                    summary_lines = [
                        f"\n┌✅ <b>Profile {profile_index+1}</b>\n"
                        f"├👤 <b>Recipient:</b> {target_display}\n"
                        f"├💸 <b>Spent:</b> {profile['SPENT']:,} / {LIMIT:,} ★\n"
                        f"└🎁 <b>Purchased </b>{profile['BOUGHT']} of {COUNT}:"
                    ]
                    gift_summary = {}
                    for p in purchases:
                        key = p["id"]
                        if key not in gift_summary:
                            gift_summary[key] = {"price": p["price"], "count": 0}
                        gift_summary[key]["count"] += 1

                    gift_items = list(gift_summary.items())
                    for idx, (gid, data) in enumerate(gift_items):
                        prefix = "   └" if idx == len(gift_items) - 1 else "   ├"
                        summary_lines.append(
                            f"{prefix} {data['price']:,} ★ × {data['count']}"
                        )
                    report_message_lines += summary_lines

                    logger.info(f"Profile #{profile_index+1} completed")
                    progress_made = True
                    await refresh_balance(bot)
                    continue  # To the next profile

                # If nothing was bought - balance/limit/gifts ran out
                if (profile["BOUGHT"] < COUNT or profile["SPENT"] < LIMIT) and not profile["DONE"] and made_local_progress:
                    target_display = get_target_display(profile, USER_ID)
                    summary_lines = [
                        f"\n┌⚠️ <b>Profile {profile_index+1}</b> (partially)\n"
                        f"├👤 <b>Recipient:</b> {target_display}\n"
                        f"├💸 <b>Spent:</b> {profile['SPENT']:,} / {LIMIT:,} ★\n"
                        f"└🎁 <b>Purchased </b>{profile['BOUGHT']} of {COUNT}:"
                    ]
                    gift_summary = {}
                    for p in purchases:
                        key = p["id"]
                        if key not in gift_summary:
                            gift_summary[key] = {"price": p["price"], "count": 0}
                        gift_summary[key]["count"] += 1

                    gift_items = list(gift_summary.items())
                    for idx, (gid, data) in enumerate(gift_items):
                        prefix = "   └" if idx == len(gift_items) - 1 else "   ├"
                        summary_lines.append(
                            f"{prefix} {data['price']:,} ★ × {data['count']}"
                        )
                    report_message_lines += summary_lines

                    logger.warning(f"Profile #{profile_index+1} not completed")
                    progress_made = True
                    await refresh_balance(bot)
                    continue  # To the next profile

            if not any_success and not progress_made:
                logger.warning(
                    f"Could not buy a single gift in any profile (all buy_gift attempts were unsuccessful)"
                )
                config["ACTIVE"] = False
                await save_config(config)
                text = ("⚠️ Suitable gifts found, but <b>failed</b> to buy."
                        "\n💰 Top up your balance! Check the recipient's address!"
                        "\n🚦 Status changed to 🔴 (inactive).")
                message = await bot.send_message(chat_id=USER_ID, text=text)
                await update_menu(
                    bot=bot, chat_id=USER_ID, user_id=USER_ID, message_id=message.message_id
                )            

            # After processing all profiles:
            if progress_made:
                config["ACTIVE"] = not all(p.get("DONE") for p in config["PROFILES"])
                await save_config(config)
                logger.info("Report: at least one profile processed, sending summary.")
                text = "🍀 <b>Profile report:</b>\n"
                text += "\n".join(report_message_lines) if report_message_lines else "⚠️ No purchases made."
                message = await bot.send_message(chat_id=USER_ID, text=text)
                await update_menu(
                    bot=bot, chat_id=USER_ID, user_id=USER_ID, message_id=message.message_id
                )

            if all(p.get("DONE") for p in config["PROFILES"]) and config["ACTIVE"]:
                config["ACTIVE"] = False
                await save_config(config)
                text = "✅ All profiles <b>completed</b>!\n⚠️ Click ♻️ <b>Reset</b> or ✏️ <b>Edit</b>!"
                message = await bot.send_message(chat_id=USER_ID, text=text)
                await update_menu(
                    bot=bot, chat_id=USER_ID, user_id=USER_ID, message_id=message.message_id
                )

        except Exception as e:
            logger.error(f"Error in gift_purchase_worker: {e}", exc_info=True)
            await asyncio.sleep(5)


async def main() -> None:
    """
    Main function that initializes the bot, dispatcher, and starts polling.
    """
    logger.info("Bot started!")
    await migrate_config_if_needed(USER_ID)
    await ensure_config(USER_ID)

    session = await get_aiohttp_session(USER_ID)
    bot = Bot(token=TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(RateLimitMiddleware(
        commands_limits={"/start": 10, "/withdraw_all": 10, "/refund": 10}, 
        allowed_user_ids=ALLOWED_USER_IDS
    ))
    dp.callback_query.middleware(RateLimitMiddleware(
        commands_limits={"guest_deposit_menu": 10},
        allowed_user_ids=ALLOWED_USER_IDS
    ))
    dp.message.middleware(AccessControlMiddleware(ALLOWED_USER_IDS))
    dp.callback_query.middleware(AccessControlMiddleware(ALLOWED_USER_IDS))

    register_wizard_handlers(dp)
    register_catalog_handlers(dp)
    register_main_handlers(
        dp=dp,
        bot=bot,
        version=VERSION
    )

    # Start userbot if configured
    await try_start_userbot_from_config(USER_ID)

    # Create tasks
    purchase_task = asyncio.create_task(gift_purchase_worker(bot))
    userbot_updater_task = asyncio.create_task(userbot_gifts_updater(USER_ID))

    # Start polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot stopped due to error: {e}", exc_info=True)
        sys.exit(1)
