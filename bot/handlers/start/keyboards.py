from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.handlers.cart import get_cart_quantity, get_cart_total
from django_app.shop.models import TelegramUser

async def main_menu_keyboard(user: TelegramUser) -> InlineKeyboardMarkup:
    """Основное меню"""
    cart_quantity = await get_cart_quantity(user)
    cart_total = await get_cart_total(user)
    
    buttons = [
        [
            InlineKeyboardButton(text="🛍️ Каталог", callback_data="cat_page_root_1"),
            InlineKeyboardButton(text="📋 Прайс-лист", callback_data="price_list_1")
        ],
        [
            InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
            InlineKeyboardButton(text="❓ FAQ", callback_data="faq")
        ],
        [
            InlineKeyboardButton(
                text=f"🛒 Корзина: {cart_total} ₽ ({cart_quantity} шт.)" if cart_quantity > 0 else "🛒 Корзина: пуста",
                callback_data="cart"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def profile_keyboard(user: TelegramUser) -> InlineKeyboardMarkup:
    """Клавиатура профиля"""
    from .messages import get_pending_orders
    cart_quantity = await get_cart_quantity(user)
    cart_total = await get_cart_total(user)
    pending_orders = await get_pending_orders(user)
    
    buttons = []
    for order in pending_orders:
        if not getattr(order, 'is_paid', False) and order.status != "Доставлен":
            buttons.append([
                InlineKeyboardButton(
                    text=f"💳 Оплатить заказ #{order.id} ({order.total} ₽)",
                    callback_data=f"pay_order_{order.id}"
                )
            ])
    
    buttons.extend([
        [
            InlineKeyboardButton(text="🛍️ Каталог", callback_data="cat_page_root_1"),
            InlineKeyboardButton(text="📋 Прайс-лист", callback_data="price_list_1")
        ],
        [InlineKeyboardButton(text="❓ FAQ", callback_data="faq")],
        [
            InlineKeyboardButton(
                text=f"🛒 Корзина: {cart_total} ₽ ({cart_quantity} шт.)" if cart_quantity > 0 else "🛒 Корзина: пуста",
                callback_data="cart"
            )
        ],
        [
            InlineKeyboardButton(text="<-- Назад", callback_data="main_menu"),
            InlineKeyboardButton(text="В меню", callback_data="main_menu")
        ]
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def price_list_keyboard(user: TelegramUser, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Клавиатура прайс-листа"""
    cart_quantity = await get_cart_quantity(user)
    cart_total = await get_cart_total(user)
    
    buttons = []
    if total_pages > 1:
        pagination = []
        if page > 1:
            pagination.append(InlineKeyboardButton(text="⬅️", callback_data=f"price_list_{page - 1}"))
        pagination.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
        if page < total_pages:
            pagination.append(InlineKeyboardButton(text="➡️", callback_data=f"price_list_{page + 1}"))
        buttons.append(pagination)
    
    buttons.extend([
        [InlineKeyboardButton(text="🛍️ Каталог", callback_data="cat_page_root_1")],
        [
            InlineKeyboardButton(
                text=f"🛒 Корзина: {cart_total} ₽ ({cart_quantity} шт.)" if cart_quantity > 0 else "🛒 Корзина: пуста",
                callback_data="cart"
            )
        ],
        [
            InlineKeyboardButton(text="<-- Назад", callback_data="main_menu"),
            InlineKeyboardButton(text="В меню", callback_data="main_menu")
        ]
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
