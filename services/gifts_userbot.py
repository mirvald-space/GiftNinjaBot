# --- Standard libraries ---
import logging

# --- Third-party libraries ---
from pyrogram.types import Gift

# --- Internal modules ---
from utils.mockdata import generate_test_gifts
from services.config import DEV_MODE, get_valid_config
from services.userbot import get_userbot_client, is_userbot_active

logger = logging.getLogger(__name__)

def normalize_gift(gift: Gift) -> dict:
    """
    Converts a Gift object from Pyrogram to a dictionary with key gift characteristics.
    """
    return {
        "id": gift.id,
        "price": gift.price or 0,
        "supply": gift.total_amount or 0,
        "left": gift.available_amount or 0,
        "sticker_file_id": getattr(gift.sticker, "file_id", None),
        "emoji": getattr(gift.sticker, "emoji", None)
    }


async def get_userbot_filtered_gifts(
    user_id: int = None,
    min_price: int = 1,
    max_price: int = 1000000,
    min_supply: int = 1,
    max_supply: int = 100000000,
    unlimited: bool = False,
    add_test_gifts: bool = False,
    test_gifts_count: int = 5
) -> list[dict]:
    """
    Gets a list of gifts through Pyrogram userbot and filters them by specified parameters.
    Returns an empty list if the session is not active or disabled in the config.
    """
    if not is_userbot_active(user_id):
        return []

    try:
        config = await get_valid_config(user_id)
        userbot_config = config.get("USERBOT", {})
        if not (userbot_config.get("API_ID") and userbot_config.get("API_HASH") and userbot_config.get("PHONE")):
            return []
        if not userbot_config.get("ENABLED", False):
            return []
        
        userbot = await get_userbot_client(user_id)
        gifts: list[Gift] = await userbot.get_available_gifts()
    except Exception as e:
        logger.error(f"Error getting gifts from userbot: {e}")
        return []
    
    filtered = []
    for gift in gifts:
        price = gift.price or 0
        supply = gift.total_amount or 0

        if gift.is_sold_out: continue

        price_ok = min_price <= price <= max_price
        supply_ok = min_supply <= supply <= max_supply

        if unlimited and gift.is_limited == False:
            supply_ok = True

        if price_ok and supply_ok:
            filtered.append(normalize_gift(gift))

    if add_test_gifts or DEV_MODE:
        test_gifts = generate_test_gifts(test_gifts_count)
        test_filtered = [
            g for g in test_gifts
            if min_price <= g["price"] <= max_price and (
                unlimited or min_supply <= g["supply"] <= max_supply
            )
        ]
        filtered += test_filtered

    filtered.sort(key=lambda g: g["price"], reverse=True)
    return filtered