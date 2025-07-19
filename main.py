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
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# --- Internal modules ---
from services.config import (
    VERSION,
    PURCHASE_COOLDOWN
)
from services.database import get_user_data, update_user_data, get_user_profiles
from services.menu import update_menu
from services.balance import refresh_balance
from services.gifts_manager import get_best_gift_list, userbot_gifts_updater
from services.buy_bot import buy_gift
from services.buy_userbot import buy_gift_userbot
from services.userbot import try_start_userbot_from_config
from services.config import get_target_display
from handlers.handlers_wizard import register_wizard_handlers
from handlers.handlers_catalog import register_catalog_handlers
from handlers.handlers_main import register_main_handlers
from utils.logging import setup_logging
from utils.proxy import get_aiohttp_session
from middlewares.access_control import AccessControlMiddleware
from middlewares.rate_limit import RateLimitMiddleware

load_dotenv(override=False)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set in .env file")
    
USER_ID = int(os.getenv("TELEGRAM_USER_ID", "0"))
if USER_ID == 0:
    raise ValueError("TELEGRAM_USER_ID is not set in .env file")
    
# Webhook settings
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "")  # Domain or public IP
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
# Webserver settings
WEBAPP_HOST = os.getenv("WEBAPP_HOST", "0.0.0.0")
WEBAPP_PORT = int(os.getenv("WEBAPP_PORT", "10000"))

setup_logging()
logger = logging.getLogger(__name__)


async def gift_purchase_worker(bot):
    """
    Background worker for purchasing gifts by profiles.
    Now takes into account the LIMIT parameter - the maximum amount of stars that can be spent on a profile.
    If the limit is exhausted - the profile is considered completed and the worker moves to the next one.
    """
    await refresh_balance(bot, USER_ID)
    while True:
        try:
            # Получаем данные пользователя из Supabase
            user_data = await get_user_data(USER_ID)
            active = user_data.get("active", False)
            
            # Если пользователь неактивен, пропускаем
            if not active:
                await asyncio.sleep(1)
                continue
                
            # Получаем профили пользователя из Supabase
            profiles = await get_user_profiles(USER_ID)
            
            # Получаем данные юзербота из отдельной таблицы
            from services.database import get_user_userbot_data
            userbot_data = await get_user_userbot_data(USER_ID)
            userbot_enabled = userbot_data.get("enabled", False) if userbot_data else False
            
            message = None
            report_message_lines = []
            progress_made = False  # Was there progress on profiles in this run
            any_success = True
            
            for profile_index, profile in enumerate(profiles):
                # Skip completed profiles
                if profile.get("done"):
                    continue
                # Skip profiles with disabled userbot
                sender = profile.get("sender", "bot")
                if sender == "userbot":
                    if not userbot_enabled:
                        continue

                COUNT = profile["count"]
                LIMIT = profile.get("limit", 0)
                TARGET_USER_ID = profile["target_user_id"]
                TARGET_CHAT_ID = profile["target_chat_id"]

                filtered_gifts = await get_best_gift_list(bot, profile)

                if not filtered_gifts:
                    continue

                purchases = []
                before_bought = profile["bought"]
                before_spent = profile["spent"]

                for gift in filtered_gifts:
                    gift_id = gift["id"]
                    gift_price = gift["price"]
                    gift_total_count = gift["supply"]
                    sticker_file_id = gift["sticker_file_id"]

                    # Check the limit before each purchase
                    while (profile["bought"] < COUNT and
                           profile["spent"] + gift_price <= LIMIT):

                        sender = profile.get("sender", "bot")
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

                        # Обновляем данные профиля в Supabase
                        profile["bought"] += 1
                        profile["spent"] += gift_price
                        purchases.append({"id": gift_id, "price": gift_price})
                        
                        # Обновляем профиль в таблице profiles
                        from services.database import update_user_profile
                        await update_user_profile(profile["id"], profile)
                        
                        await asyncio.sleep(PURCHASE_COOLDOWN)

                        # Check: have we reached the limit after the purchase
                        if profile["spent"] >= LIMIT:
                            break

                    if profile["bought"] >= COUNT or profile["spent"] >= LIMIT:
                        break  # Reached the limit either by quantity or by amount

                after_bought = profile["bought"]
                after_spent = profile["spent"]
                made_local_progress = (after_bought > before_bought) or (after_spent > before_spent)

                # Profile is fully completed: either by quantity or by limit
                if (profile["bought"] >= COUNT or profile["spent"] >= LIMIT) and not profile["done"]:
                    # Обновляем статус профиля в Supabase
                    profile["done"] = True
                    from services.database import update_user_profile
                    await update_user_profile(profile["id"], profile)

                    target_display = get_target_display(profile, USER_ID)
                    summary_lines = [
                        f"\n┌✅ <b>Profile {profile_index+1}</b>\n"
                        f"├👤 <b>Recipient:</b> {target_display}\n"
                        f"├💸 <b>Spent:</b> {profile['spent']:,} / {LIMIT:,} ★\n"
                        f"└🎁 <b>Purchased </b>{profile['bought']} of {COUNT}:"
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
                    await refresh_balance(bot, USER_ID)
                    continue  # To the next profile

                # If nothing was bought - balance/limit/gifts ran out
                if (profile["bought"] < COUNT or profile["spent"] < LIMIT) and not profile["done"] and made_local_progress:
                    target_display = get_target_display(profile, USER_ID)
                    summary_lines = [
                        f"\n┌⚠️ <b>Profile {profile_index+1}</b> (partially)\n"
                        f"├👤 <b>Recipient:</b> {target_display}\n"
                        f"├💸 <b>Spent:</b> {profile['spent']:,} / {LIMIT:,} ★\n"
                        f"└🎁 <b>Purchased </b>{profile['bought']} of {COUNT}:"
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
                    await refresh_balance(bot, USER_ID)
                    continue  # To the next profile

            if not any_success and not progress_made:
                logger.warning(
                    f"Could not buy a single gift in any profile (all buy_gift attempts were unsuccessful)"
                )
                # Обновляем статус пользователя в Supabase
                await update_user_data(USER_ID, {"active": False})
                logger.warning("Status changed to inactive")

            await asyncio.sleep(1.5)

        except Exception as e:
            logger.error(f"Error in gift_purchase_worker: {e}")
            await asyncio.sleep(5)


async def main() -> None:
    # Remove old config file if exists - we've migrated to Supabase
    if os.path.exists("config.json"):
        try:
            os.remove("config.json")
            logger.info("Removed old config.json file as we've migrated to Supabase")
        except Exception as e:
            logger.error(f"Failed to remove config.json: {e}")

    # Парсим аргументы командной строки
    webhook_mode = "--webhook" in sys.argv

    # Configure the Bot
    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=await get_aiohttp_session(USER_ID)
    )

    # Get and update the bot's balance
    await refresh_balance(bot, USER_ID)

    try:
        # Запускаем юзербот, если он есть в конфиге
        await try_start_userbot_from_config(USER_ID)
    except Exception as e:
        logger.error(f"Failed to start userbot: {e}")

    # Initialize dispatcher
    dp = Dispatcher(storage=MemoryStorage())

    # Register middlewares
    dp.message.middleware(AccessControlMiddleware())
    dp.message.middleware(RateLimitMiddleware())

    # Register handlers
    register_wizard_handlers(dp)
    register_catalog_handlers(dp)
    register_main_handlers(dp, bot, VERSION)

    # Background tasks
    asyncio.create_task(gift_purchase_worker(bot))
    asyncio.create_task(userbot_gifts_updater(USER_ID))

    # Clear webhooks
    await bot.delete_webhook(drop_pending_updates=True)

    if webhook_mode:
        # Webhook mode
        logger.info(f"Starting in webhook mode on {WEBHOOK_URL}")
        
        # Create aiohttp application
        app = web.Application()
        
        # Setup webhook
        await bot.set_webhook(
            url=WEBHOOK_URL,
            secret_token=TOKEN
        )
        
        # Process webhook calls
        SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
        ).register(app, path=WEBHOOK_PATH)
        
        # Setup application
        setup_application(app, dp, bot=bot)
        
        # Start application
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, WEBAPP_HOST, WEBAPP_PORT)
        await site.start()
        
        logger.info(f"Webhook started on {WEBAPP_HOST}:{WEBAPP_PORT}")
        
        # Wait indefinitely
        try:
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()
    else:
        # Polling mode
        logger.info("Starting in polling mode")
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
