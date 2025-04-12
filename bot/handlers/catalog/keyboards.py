# File: bot/handlers/catalog/keyboards.py
import logging
from typing import List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.handlers.cart.models import get_cart_quantity, get_cart_total
from bot.core.config import CATEGORIES_PER_PAGE, PRODUCTS_PER_PAGE
from asgiref.sync import sync_to_async
from django_app.shop.models import Category, Product

# Настройка логирования
logger = logging.getLogger(__name__)

@sync_to_async
def get_parent_category(category_id: str) -> Category:
    """
    Получает родительскую категорию для указанного ID категории.
    :param category_id: ID категории.
    :return: Объект Category или None, если категория не найдена.
    """
    try:
        category = Category.objects.get(id=category_id)
        return category.parent
    except Category.DoesNotExist:
        logger.warning(f"Категория с ID {category_id} не найдена.")
        return None

async def build_categories_keyboard(categories: List[Category], parent_id: str, page: int, total_pages: int, user) -> InlineKeyboardMarkup:
    """
    Генерация клавиатуры для категорий (2 кнопки в строке).
    :param categories: Список категорий.
    :param parent_id: ID родительской категории ("root" для корневых).
    :param page: Текущая страница.
    :param total_pages: Общее количество страниц.
    :param user: Объект TelegramUser для получения данных корзины.
    :return: InlineKeyboardMarkup с клавиатурой.
    """
    logger.debug(f"Генерация клавиатуры для категорий: parent_id={parent_id}, page={page}, total_pages={total_pages}")
    buttons = []

    # Группируем категории по 2 в ряд
    for i in range(0, len(categories), 2):
        row = []
        category1 = categories[i]
        row.append(InlineKeyboardButton(text=category1.name, callback_data=f"cat_page_{category1.id}_1"))
        if i + 1 < len(categories):
            category2 = categories[i + 1]
            row.append(InlineKeyboardButton(text=category2.name, callback_data=f"cat_page_{category2.id}_1"))
        buttons.append(row)

    # Добавляем пагинацию
    if total_pages > 1:
        pagination_buttons = []
        if page > 1:
            pagination_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"cat_page_{parent_id}_{page - 1}"))
        else:
            pagination_buttons.append(InlineKeyboardButton(text="⬅️", callback_data="noop"))
        pagination_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
        if page < total_pages:
            pagination_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"cat_page_{parent_id}_{page + 1}"))
        else:
            pagination_buttons.append(InlineKeyboardButton(text="➡️", callback_data="noop"))
        buttons.append(pagination_buttons)

    # Добавляем кнопку корзины
    cart_quantity = await get_cart_quantity(user)
    cart_total = await get_cart_total(user)
    cart_text = f"🛒 Корзина: {cart_total} ₽ ({cart_quantity} шт.)" if cart_quantity > 0 else "🛒 Корзина: пуста"
    buttons.append([InlineKeyboardButton(text=cart_text, callback_data="cart")])

    # Кнопки "Назад" и "В меню"
    if parent_id == "root":
        back_callback = "main_menu"
    else:
        parent_category = await get_parent_category(parent_id)
        grandparent_id = parent_category.id if parent_category else "root"
        back_callback = f"cat_page_{grandparent_id}_1"
    buttons.append([
        InlineKeyboardButton(text="<-- Назад", callback_data=back_callback),
        InlineKeyboardButton(text="В меню", callback_data="main_menu")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def build_products_keyboard(category_id: int, page: int, products: List[Product], total_count: int, user) -> InlineKeyboardMarkup:
    """
    Генерация клавиатуры для товаров (2 кнопки в строке).
    :param category_id: ID категории.
    :param page: Текущая страница.
    :param products: Список товаров.
    :param total_count: Общее количество товаров.
    :param user: Объект TelegramUser для получения данных корзины.
    :return: InlineKeyboardMarkup с клавиатурой.
    """
    logger.debug(f"Генерация клавиатуры для товаров: category_id={category_id}, page={page}, total_count={total_count}")
    buttons = []

    # Группируем товары по 2 в ряд
    for i in range(0, len(products), 2):
        row = []
        prod1 = products[i]
        row.append(InlineKeyboardButton(text=prod1.name, callback_data=f"product_{prod1.id}"))
        if i + 1 < len(products):
            prod2 = products[i + 1]
            row.append(InlineKeyboardButton(text=prod2.name, callback_data=f"product_{prod2.id}"))
        buttons.append(row)

    # Добавляем пагинацию
    max_page = max(1, (total_count + PRODUCTS_PER_PAGE - 1) // PRODUCTS_PER_PAGE)
    if max_page > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"prod_page_{category_id}_{page - 1}"))
        nav_buttons.append(InlineKeyboardButton(text=f"{page}/{max_page}", callback_data="noop"))
        if page < max_page:
            nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"prod_page_{category_id}_{page + 1}"))
        buttons.append(nav_buttons)

    # Добавляем кнопки "Прайс-лист" и корзины
    cart_quantity = await get_cart_quantity(user)
    cart_total = await get_cart_total(user)
    buttons.append([InlineKeyboardButton(text="📋 Прайс-лист", callback_data="price_list_1")])
    cart_text = f"🛒 Корзина: {cart_total} ₽ ({cart_quantity} шт.)" if cart_quantity > 0 else "🛒 Корзина: пуста"
    buttons.append([InlineKeyboardButton(text=cart_text, callback_data="cart")])

    # Кнопки "Назад" и "В меню"
    parent_category = await get_parent_category(str(category_id))
    parent_id = parent_category.id if parent_category else "root"
    back_callback = f"cat_page_{parent_id}_1"
    buttons.append([
        InlineKeyboardButton(text="<-- Назад", callback_data=back_callback),
        InlineKeyboardButton(text="В меню", callback_data="main_menu")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
