# --- Standard libraries ---
import time
import random
import asyncio
import logging

# --- Internal modules ---
from services.config import USERBOT_UPDATE_COOLDOWN
from services.gifts_bot import get_filtered_gifts
from services.gifts_userbot import get_userbot_filtered_gifts

logger = logging.getLogger(__name__)

userbot_all_gifts: list[dict] = []
last_update_userbot: float = 0

async def userbot_gifts_updater(user_id: int, base_interval: int = USERBOT_UPDATE_COOLDOWN):
    """
    Starts a background task for regular updating of the userbot gifts cache.

    :param user_id: Telegram ID of the userbot session owner
    :param base_interval: Minimum update interval (in seconds);
                          actual pause will be from base_interval to base_interval + 10
    """
    global userbot_all_gifts, last_update_userbot
    while True:
        try:
            userbot_all_gifts = await get_userbot_filtered_gifts(
                user_id,
                min_price=1,
                max_price=10000000,
                min_supply=1,
                max_supply=100000000,
                unlimited=False
            )
            last_update_userbot = time.time()
        except Exception as e:
            logger.error(f"Error in userbot_gifts_updater: {e}")
        delay = random.randint(base_interval, base_interval + 10)
        await asyncio.sleep(delay)


def is_userbot_cache_fresh(max_age: int = USERBOT_UPDATE_COOLDOWN + 10) -> bool:
    """
    Checks if the userbot cache is up-to-date.

    :param max_age: Maximum allowed time since the last update (in seconds)
    :return: True if the cache is fresh
    """
    return time.time() - last_update_userbot < max_age


def filter_gifts_by_profile(gifts: list[dict], profile: dict) -> list[dict]:
    """
    Filters the list of gifts according to the parameters of a specific profile.

    :param gifts: List of all available gifts (dictionaries)
    :param profile: Dictionary with profile parameters (price range, limits)
    :return: Filtered list of gifts suitable for the profile
    """
    min_price = profile.get("min_price", profile.get("MIN_PRICE", 0))
    max_price = profile.get("max_price", profile.get("MAX_PRICE", 10000))
    min_supply = profile.get("min_supply", profile.get("MIN_SUPPLY", 0))
    max_supply = profile.get("max_supply", profile.get("MAX_SUPPLY", 10000))
    
    return [
        g for g in gifts
        if min_price <= g.get("price", 0) <= max_price
        and min_supply <= g.get("supply", 0) <= max_supply
    ]


async def get_best_gift_list(bot, profile: dict) -> list[dict]:
    """
    Returns the most complete list of gifts - either from the bot or from the userbot,
    depending on where there are more gifts, subject to filtering by profile.

    :param bot: aiogram bot object
    :param profile: Dictionary with profile parameters (filtering by price, quantity, etc.)
    :return: Filtered list of gifts (as list[dict])
    """
    global userbot_all_gifts

    min_price = profile.get("min_price", profile.get("MIN_PRICE", 0))
    max_price = profile.get("max_price", profile.get("MAX_PRICE", 10000))
    min_supply = profile.get("min_supply", profile.get("MIN_SUPPLY", 0))
    max_supply = profile.get("max_supply", profile.get("MAX_SUPPLY", 10000))

    try:
        gifts_bot = await get_filtered_gifts(
            bot,
            min_price,
            max_price,
            min_supply,
            max_supply
        )
    except Exception as e:
        logger.error(f"Error getting gift list from bot: {e}")
        gifts_bot = []

    gifts_userbot = filter_gifts_by_profile(userbot_all_gifts, profile)

    if is_userbot_cache_fresh() and len(gifts_userbot) > len(gifts_bot):
        return gifts_userbot
    
    return gifts_bot
