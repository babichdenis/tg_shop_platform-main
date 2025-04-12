# bot/handlers/cart/keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.handlers.cart.models import get_cart_quantity, get_cart_total

def generate_cart_keyboard(user, items, cart_quantity: int, cart_total, page: int = 1, items_per_page: int = 5) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    if not items:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="🛒 Корзина пуста", callback_data="noop")
        ])
    else:
        # Форматируем сумму: проверяем, является ли cart_total целым числом
        formatted_total = f"{int(cart_total)}" if cart_total == int(cart_total) else f"{cart_total:.2f}"
        
        # Пагинация
        total_items = len(items)
        total_pages = max(1, (total_items + items_per_page - 1) // items_per_page)
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        current_items = items[start_idx:end_idx]
        
        # Отображаем каждый товар
        for item in current_items:
            product = item.product
            item_total = product.price * item.quantity
            formatted_item_total = f"{int(item_total)}" if item_total == int(item_total) else f"{item_total:.2f}"
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"{product.name} x{item.quantity} | {formatted_item_total} ₽",
                    callback_data="noop"
                )
            ])
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="−", callback_data=f"decrease_item_{product.id}"),
                InlineKeyboardButton(text=f"{item.quantity}", callback_data="noop"),
                InlineKeyboardButton(text="+", callback_data=f"increase_item_{product.id}"),
                InlineKeyboardButton(text="❌", callback_data=f"remove_item_{product.id}")
            ])
        
        # Пагинация (только если больше 1 страницы)
        if total_pages > 1:
            pagination = []
            if page > 1:
                pagination.append(InlineKeyboardButton(text="⬅️", callback_data=f"cart_page_{page - 1}"))
            pagination.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
            if page < total_pages:
                pagination.append(InlineKeyboardButton(text="➡️", callback_data=f"cart_page_{page + 1}"))
            keyboard.inline_keyboard.append(pagination)
        
        # Итоговая сумма
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"Итого: {formatted_total} ₽", callback_data="noop")
        ])
        
        # Кнопка оформления заказа
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"✅ Оформить за {formatted_total} ₽", callback_data="checkout")
        ])
        
        # Кнопки "Очистить корзину" и "Назад"
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="🗑️ Очистить", callback_data="clear_cart"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")
        ])

    return keyboard
def generate_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])

def generate_skip_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Пропустить", callback_data="skip"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back")
        ]
    ])

def generate_confirmation_keyboard(total):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"Заказ на {total} ₽. Оформить?", callback_data="confirm"),
            InlineKeyboardButton(text="✏️ Изменить", callback_data="edit")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back")
        ]
    ])

def generate_edit_choice_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📍 Адрес", callback_data="edit_address"),
            InlineKeyboardButton(text="📞 Телефон", callback_data="edit_phone")
        ],
        [
            InlineKeyboardButton(text="💬 Пожелания", callback_data="edit_wishes"),
            InlineKeyboardButton(text="⏰ Время доставки", callback_data="edit_delivery_time")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_confirmation")
        ]
    ])
