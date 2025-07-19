# --- Internal modules ---
from utils.mockdata import generate_test_gifts
from services.config import DEV_MODE

def normalize_gift(gift) -> dict:
    """
    Converts a Gift object to a dictionary with the main characteristics of the gift.

    :param gift: Gift object.
    :return: Dictionary with gift parameters.
    """
    return {
        "id": getattr(gift, "id", None),
        "price": getattr(gift, "star_count", 0),
        "supply": getattr(gift, "total_count", 0),
        "left": getattr(gift, "remaining_count", 0),
        "sticker_file_id": getattr(getattr(gift, "sticker", None), "file_id", None),
        "emoji": getattr(getattr(gift, "sticker", None), "emoji", None),
    }


async def get_filtered_gifts(
    bot, 
    min_price, 
    max_price, 
    min_supply, 
    max_supply, 
    unlimited=False,
    add_test_gifts=False,
    test_gifts_count=5
):
    """
    Gets and filters the list of gifts from the API, returns them in normalized form.
    
    :param bot: aiogram bot instance.
    :param min_price: Minimum gift price.
    :param max_price: Maximum gift price.
    :param min_supply: Minimum gift supply.
    :param max_supply: Maximum gift supply.
    :param unlimited: If True - ignore supply when filtering.
    :param add_test_gifts: Add test gifts to the end of the list.
    :param test_gifts_count: Number of test gifts.
    :return: List of dictionaries with gift parameters, sorted by price in descending order.
    """
    # Get, normalize and filter gifts from the market
    api_gifts = await bot.get_available_gifts()
    filtered = []
    for gift in api_gifts.gifts:
        price_ok = min_price <= gift.star_count <= max_price
        # Logic for unlimited
        if unlimited:
            supply_ok = True
        else:
            supply = gift.total_count or 0
            supply_ok = min_supply <= supply <= max_supply
        if price_ok and supply_ok:
            filtered.append(gift)
    normalized = [normalize_gift(gift) for gift in filtered]

    # Get and filter test gifts separately
    test_gifts = []
    if add_test_gifts or DEV_MODE:
        test_gifts = generate_test_gifts(test_gifts_count)
        test_gifts = [
            gift for gift in test_gifts
            if min_price <= gift["price"] <= max_price and (
                unlimited or min_supply <= gift["supply"] <= max_supply
            )
        ]

    all_gifts = normalized + test_gifts
    all_gifts .sort(key=lambda g: g["price"], reverse=True)
    return all_gifts 
