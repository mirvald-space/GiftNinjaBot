# --- Standard libraries ---
import asyncio
import logging
import random

# --- Internal modules ---
from services.config import get_valid_config, save_config, DEV_MODE
from services.balance import change_balance_userbot
from services.userbot import get_userbot_client

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import (
    FloodWait,
    BadRequest,
    Forbidden,
    RPCError,
    AuthKeyUnregistered
)

logger = logging.getLogger(__name__)

async def buy_gift_userbot(
    session_user_id: int,
    gift_id: int,
    target_user_id: int,
    target_chat_id: str,
    gift_price: int,
    file_id=None,
    retries: int = 3,
    add_test_purchases: bool = False
) -> bool:
    """
    Buys a gift through Pyrogram userbot.

    :param session_user_id: Userbot session ID
    :param gift_id: Gift ID
    :param target_user_id: Recipient user ID (or None)
    :param target_chat_id: Recipient chat ID (or None)
    :param gift_price: Gift price in stars
    :param file_id: Not used (reserved)
    :param retries: Number of attempts
    :param add_test_purchases: Enables random purchases in development mode
    :return: True if purchase is successful
    """
    if add_test_purchases or DEV_MODE:
        result = random.choice([True, True, True, False])
        logger.info(f"[TEST] ({result}) Purchase of gift {gift_id} for {gift_price} (userbot, simulation)")
        return result

    config = await get_valid_config(session_user_id)
    userbot_config = config.get("USERBOT", {})
    userbot_balance = userbot_config.get("BALANCE", 0)

    if userbot_balance < gift_price:
        logger.error(f"Not enough stars to buy gift {gift_id} (required: {gift_price}, available: {userbot_balance})")
        
        config = await get_valid_config(session_user_id)
        config["USERBOT"]["ENABLED"] = False
        await save_config(config)

        return False

    client: Client = await get_userbot_client(session_user_id)
    if not client:
        logger.error("Failed to get userbot client object.")
        return False

    for attempt in range(1, retries + 1):
        try:
            logger.debug(f"Attempt {attempt}/{retries} to buy gift with userbot...")

            if target_user_id and not target_chat_id:
                result_send: Message = await client.send_gift(gift_id=int(gift_id), 
                                                         chat_id=int(target_user_id), 
                                                         is_private=True)
            elif target_chat_id and not target_user_id:
                result_send: Message = await client.send_gift(gift_id=int(gift_id), 
                                                         chat_id=target_chat_id, 
                                                         is_private=True)
            else:
                logger.warning("Both parameters specified - target_user_id and target_chat_id. Aborting.")
                break

            new_balance = await change_balance_userbot(-gift_price)
            logger.info(f"Successful purchase of gift {gift_id} for {gift_price} stars. Remaining: {new_balance}")
            return True
        
        except FloodWait as e:
            logger.error(f"Flood wait: waiting for {e.retry_after} seconds")
            await asyncio.sleep(e.value)

        except BadRequest as e:
            if "BALANCE_TOO_LOW" in str(e) or "not enough" in str(e).lower():
                logger.error(f"Not enough stars: {e}")
                return False
            logger.error(f"(BadRequest) Critical error: {e}")
            return False

        except Forbidden as e:
            logger.error(f"(Forbidden) Critical error: {e}")
            return False
        
        except AuthKeyUnregistered as e:
            logger.error(f"(AuthKeyUnregistered) Critical error: {e}")
            return False

        except RPCError as e:
            logger.error(f"RPC error: {e}")
            await asyncio.sleep(2 ** attempt)

        except Exception as e:
            delay = 2 ** attempt
            logger.error(f"[{attempt}/{retries}] Userbot error during purchase: {e}. Retrying in {delay} sec...")
            await asyncio.sleep(delay)

    logger.error(f"Failed to buy gift {gift_id} after {retries} attempts.")
    return False
