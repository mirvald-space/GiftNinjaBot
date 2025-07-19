# --- Standard libraries ---
from itertools import combinations
import logging

# --- Internal modules ---
from services.database import get_user_balance, update_user_balance, get_user_userbot_balance, update_user_userbot_balance, update_user_data
from services.userbot import get_userbot_stars_balance

# --- Third-party libraries ---
from aiogram.types.star_amount import StarAmount

logger = logging.getLogger(__name__)

async def get_stars_balance(bot) -> int:
    """
    Gets the star balance through the bot API (current method).
    """
    try:
        star_amount: StarAmount = await bot.get_my_star_balance()
        balance = star_amount.amount
        logger.info(f"Retrieved bot balance: {balance} stars")
        return balance
    except Exception as e:
        logger.error(f"Failed to get bot balance: {e}")
        return 0


async def get_stars_balance_by_transactions(bot) -> int:
    """
    Gets the total star balance from all user transactions through the bot API (deprecated method).
    """
    offset = 0
    limit = 100
    balance = 0

    while True:
        get_transactions = await bot.get_star_transactions(offset=offset, limit=limit)
        transactions = get_transactions.transactions

        if not transactions:
            break

        for transaction in transactions:
            source = transaction.source
            amount = transaction.amount
            if source is not None:
                balance += amount
            else:
                balance -= amount

        offset += limit

    return balance


async def refresh_balance(bot, user_id) -> int:
    """
    Updates and saves the star balance, returns the current value.
    
    Args:
        bot: Bot instance
        user_id: User ID
    """
    try:
        # Получаем баланс бота
        balance = await get_stars_balance(bot)
        logger.info(f"Refreshing balance for user {user_id}: {balance} stars")
        
        # Обновляем баланс пользователя напрямую
        await update_user_data(user_id, {"balance": balance})
        logger.info(f"Updated user {user_id} balance in database: {balance} stars")
        
        # Обновляем баланс юзербота (если есть)
        try:
            userbot_balance = await get_userbot_stars_balance()
            await update_user_data(user_id, {"userbot_balance": userbot_balance})
            logger.info(f"Updated userbot balance for user {user_id}: {userbot_balance} stars")
        except Exception as e:
            logger.error(f"Failed to get userbot balance for user {user_id}: {e}")
        
        return balance
    except Exception as e:
        logger.error(f"Failed to refresh balance for user {user_id}: {e}")
        return 0


async def change_balance(delta: int, user_id) -> int:
    """
    Changes the star balance by the specified delta value, not allowing negative values.
    
    Args:
        delta: Change in balance
        user_id: User ID
    """
    return await update_user_balance(user_id, delta)


async def change_balance_userbot(delta: int, user_id) -> int:
    """
    Changes the userbot's star balance by the specified delta value, not allowing negative values.
    
    Args:
        delta: Change in balance
        user_id: User ID
    """
    return await update_user_userbot_balance(user_id, delta)


async def refund_all_star_payments(bot, username, user_id, message_func=None):
    """
    Returns stars only for deposits without refunds made by the specified username.
    Selects the optimal combination to withdraw the maximum possible amount.
    If necessary, informs the user about further actions.
    """
    balance = await refresh_balance(bot, user_id)
    if balance <= 0:
        return {"refunded": 0, "count": 0, "txn_ids": [], "left": 0}

    # Get all transactions
    offset = 0
    limit = 100
    all_txns = []
    while True:
        res = await bot.get_star_transactions(offset=offset, limit=limit)
        txns = res.transactions
        if not txns:
            break
        all_txns.extend(txns)
        offset += limit

    # Filter deposits without refunds and only with the required username
    deposits = [
        t for t in all_txns
        if t.source is not None
        and getattr(t.source, "user", None)
        and getattr(t.source.user, "username", None) == username
    ]
    refunded_ids = {t.id for t in all_txns if t.source is None}
    unrefunded_deposits = [t for t in deposits if t.id not in refunded_ids]

    n = len(unrefunded_deposits)
    best_combo = []
    best_sum = 0

    # Find the ideal combination or greedy
    if n <= 18:
        for r in range(1, n+1):
            for combo in combinations(unrefunded_deposits, r):
                s = sum(t.amount for t in combo)
                if s <= balance and s > best_sum:
                    best_combo = combo
                    best_sum = s
                if best_sum == balance:
                    break
            if best_sum == balance:
                break
    else:
        unrefunded_deposits.sort(key=lambda t: t.amount, reverse=True)
        curr_sum = 0
        best_combo = []
        for t in unrefunded_deposits:
            if curr_sum + t.amount <= balance:
                best_combo.append(t)
                curr_sum += t.amount
        best_sum = curr_sum

    if not best_combo:
        return {"refunded": 0, "count": 0, "txn_ids": [], "left": balance}

    # Make refunds only for selected transactions
    total_refunded = 0
    refund_ids = []
    for txn in best_combo:
        txn_id = getattr(txn, "id", None)
        if not txn_id:
            continue
        try:
            await bot.refund_star_payment(
                user_id=user_id,
                telegram_payment_charge_id=txn_id
            )
            total_refunded += txn.amount
            refund_ids.append(txn_id)
        except Exception as e:
            if message_func:
                await message_func(f"🚫 Error when refunding ★{txn.amount}")

    left = balance - best_sum

    # Find a transaction that is enough to cover the remainder
    # Take the minimum amount among transactions where amount > min_needed
    def find_next_possible_deposit(unused_deposits, min_needed):
        bigger = [t for t in unused_deposits if t.amount > min_needed]
        if not bigger:
            return None
        best = min(bigger, key=lambda t: t.amount)
        return {"amount": best.amount, "id": getattr(best, "id", None)}

    unused_deposits = [t for t in unrefunded_deposits if t not in best_combo]
    next_possible = None
    if left > 0 and unused_deposits:
        next_possible = find_next_possible_deposit(unused_deposits, left)

    return {
        "refunded": total_refunded,
        "count": len(best_combo),
        "txn_ids": refund_ids,
        "left": left,
        "next_possible": next_possible
    }


async def get_userbot_balance() -> int:
    """
    Получает баланс stars юзербота.
    """
    return await get_userbot_stars_balance()
