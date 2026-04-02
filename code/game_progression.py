import random
from collections import Counter


def count_spell(spells, spell_name):
    return Counter(spells).get(spell_name, 0)


def update_level_from_xp(xp, level_xp):
    level = 1
    for threshold in level_xp:
        if xp >= threshold:
            level += 1
        else:
            break
    return level


def grant_next_spell(spells, next_spell_unlock_index, magic_spells, reason, push_log):
    if next_spell_unlock_index >= len(magic_spells):
        push_log("All magic spells unlocked.")
        return next_spell_unlock_index, False

    spell_name = magic_spells[next_spell_unlock_index]
    spells.append(spell_name)
    next_spell_unlock_index += 1
    push_log(f"Learned {spell_name} ({reason}).")
    return next_spell_unlock_index, True


def issue_daily_order(spells, current_daily_order, push_log):
    order_pool = list(set(spells))
    if not order_pool:
        order_pool = ["Fireball"]

    if len(order_pool) > 1 and current_daily_order in order_pool:
        order_pool.remove(current_daily_order)

    new_order = random.choice(order_pool)
    push_log(f"Daily order: Sell 1x {new_order}.")
    return new_order, False


def generate_random_spell_offer(spells, push_log):
    if not spells:
        push_log("No spells to offer today.")
        return None, 0, 0, 0

    unique_owned_spells = list(set(spells))
    offer_spell = random.choice(unique_owned_spells)
    offer_amount = 1
    offer_xp = random.randint(5, 20)
    offer_coin = random.randint(10, 25)
    push_log(f"Random offer: {offer_amount}x {offer_spell} = +{offer_coin} coins, +{offer_xp} XP.")
    return offer_spell, offer_amount, offer_xp, offer_coin


def sell_daily_order_spell(spells, current_daily_order, order_completed_today, coins, xp, coin_per_sale, xp_per_sale, push_log):
    if current_daily_order is None:
        push_log("No active order today.")
        return coins, xp, order_completed_today

    if order_completed_today:
        push_log("Daily order already completed.")
        return coins, xp, order_completed_today

    if current_daily_order in spells:
        spells.remove(current_daily_order)
        coins += coin_per_sale
        xp += xp_per_sale
        order_completed_today = True
        push_log(f"Sold {current_daily_order}: +{coin_per_sale} coins, +{xp_per_sale} XP.")
    else:
        push_log(f"You do not own {current_daily_order}.")

    return coins, xp, order_completed_today
