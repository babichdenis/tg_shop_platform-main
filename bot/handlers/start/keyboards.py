# bot/handlers/start/keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.handlers.start.subscriptions import check_subscriptions
from bot.core.config import SUBSCRIPTION_CHANNEL_ID, SUBSCRIPTION_GROUP_ID

async def main_menu_keyboard(bot, user_id):
    """Формирует клавиатуру главного меню с учётом подписки."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    # Проверяем подписку
    has_subscription = True
    if SUBSCRIPTION_CHANNEL_ID or SUBSCRIPTION_GROUP_ID:
        subscription_result, _ = await check_subscriptions(bot, user_id)
        has_subscription = subscription_result

    # Если пользователь подписан, показываем все кнопки
    if has_subscription:
        keyboard.inline_keyboard.extend([
            [
                InlineKeyboardButton(text="🛍 Каталог", callback_data="catalog"),
                InlineKeyboardButton(text="📋 Прайс-лист", callback_data="price_list_1"),  # Начинаем с первой страницы
            ],
            [
                InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
                InlineKeyboardButton(text="❓ FAQ", callback_data="faq"),
            ],
        ])

        # Добавляем кнопку корзины, если есть товары
        from bot.handlers.cart.models import get_cart_quantity
        cart_quantity = await get_cart_quantity(user_id)
        if cart_quantity > 0:
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"🛒 Корзина: {cart_quantity} шт.",
                    callback_data="cart"
                )
            ])
        else:
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="🛒 Корзина", callback_data="cart")
            ])

    # Если не подписан, показываем только кнопки, не требующие подписки
    else:
        keyboard.inline_keyboard.extend([
            [
                InlineKeyboardButton(text="❓ FAQ", callback_data="faq"),
                InlineKeyboardButton(text="ℹ️ О боте", callback_data="about"),
            ]
        ])

    return keyboard

async def profile_keyboard(user):
    """Формирует клавиатуру профиля."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="main_menu")]
    ])
    return keyboard

async def price_list_keyboard(user, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Формирует клавиатуру для пагинации прайс-листа."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    # Пагинация
    pagination = []
    if page > 1:
        pagination.append(InlineKeyboardButton(text="⬅️", callback_data=f"price_list_{page - 1}"))
    pagination.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        pagination.append(InlineKeyboardButton(text="➡️", callback_data=f"price_list_{page + 1}"))
    if pagination:
        keyboard.inline_keyboard.append(pagination)

    # Кнопка "Назад"
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="⬅️ В меню", callback_data="main_menu")
    ])

    return keyboard
