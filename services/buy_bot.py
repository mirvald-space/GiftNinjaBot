# --- Standard libraries ---
import asyncio
import logging
import random

# --- Third-party libraries ---
from aiogram.exceptions import TelegramAPIError, TelegramNetworkError, TelegramRetryAfter

# --- Internal modules ---
from services.config import get_valid_config, save_config, DEV_MODE
from services.balance import change_balance

logger = logging.getLogger(__name__)

async def buy_gift(
    bot,
    env_user_id,
    gift_id,
    user_id,
    chat_id,
    gift_price,
    file_id,
    retries=3,
    add_test_purchases=False
):
    """
    Buys a gift with specified parameters and number of attempts.
    
    Arguments:
        bot: Bot instance.
        env_user_id: User ID from environment (config).
        gift_id: Gift ID.
        user_id: Recipient user ID (can be None).
        chat_id: Recipient chat ID (can be None).
        gift_price: Gift price.
        file_id: File ID (not used in this bot version).
        retries: Number of attempts on errors.

    Returns:
        True if purchase is successful, otherwise False.
    """
    # Test logic
    if add_test_purchases or DEV_MODE:
        result = random.choice([True, True, True, False])
        logger.info(f"[TEST] ({result}) Purchase of gift {gift_id} for {gift_price} (simulation, not touching balance)")
        return result
    
    # Normal logic
    config = await get_valid_config(env_user_id)
    balance = config["BALANCE"]
    if balance < gift_price:
        logger.error(f"Not enough stars to buy gift {gift_id} (required: {gift_price}, available: {balance})")
        
        config = await get_valid_config(env_user_id)
        config["ACTIVE"] = False
        await save_config(config)

        return False
    
    for attempt in range(1, retries + 1):
        try:
            if user_id is not None and chat_id is None:
                result = await bot.send_gift(gift_id=gift_id, user_id=user_id)
            elif user_id is None and chat_id is not None:
                result = await bot.send_gift(gift_id=gift_id, chat_id=chat_id)
            else:
                logger.warning("Both parameters specified - user_id and chat_id. Aborting.")
                break

            if result:
                new_balance = await change_balance(int(-gift_price))
                logger.info(f"Successful purchase of gift {gift_id} for {gift_price} stars. Remaining: {new_balance}")
                return True
            
            logger.error(f"Attempt {attempt}/{retries}: Failed to buy gift {gift_id}. Retrying...")

        except TelegramRetryAfter as e:
            logger.error(f"Flood wait: waiting for {e.retry_after} seconds")
            await asyncio.sleep(e.retry_after)

        except TelegramNetworkError as e:
            logger.error(f"Attempt {attempt}/{retries}: Network error: {e}. Retrying in {2**attempt} seconds...")
            await asyncio.sleep(2**attempt)

        except TelegramAPIError as e:
            logger.error(f"Telegram API error: {e}")
            break

    logger.error(f"Failed to buy gift {gift_id} after {retries} attempts.")
    return False