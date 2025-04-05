import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from asgiref.sync import sync_to_async
from django_app.shop.models import Category, Product

router = Router()
logger = logging.getLogger(__name__)

# --- Вспомогательные функции ---

@sync_to_async
def get_categories_page(parent_id: int | None, page: int, per_page: int = 5) -> tuple[list[Category], int]:
    """Получение страницы категорий с пагинацией"""
    if parent_id is None:
        qs = Category.objects.filter(parent__isnull=True, is_active=True)
    else:
        qs = Category.objects.filter(parent_id=parent_id, is_active=True)
    
    total_count = qs.count()
    start = (page - 1) * per_page
    end = start + per_page
    categories = list(qs[start:end])
    return categories, total_count

@sync_to_async
def get_products_page(category_id: int, page: int, per_page: int = 5) -> tuple[list[Product], int]:
    """Получение страницы товаров с пагинацией"""
    qs = Product.objects.filter(category_id=category_id, is_active=True)
    total_count = qs.count()
    start = (page - 1) * per_page
    end = start + per_page
    products = list(qs[start:end])
    return products, total_count

async def safe_edit_message(callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup):
    """Безопасное редактирование сообщения"""
    try:
        await callback.message.edit_text(
            text,
            reply_markup=reply_markup
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            logger.debug(f"Сообщение не изменено (уже актуально): {text[:50]}...")
        else:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.message.answer(text, reply_markup=reply_markup)  # Отправляем новое сообщение
    except Exception as e:
        logger.error(f"Неизвестная ошибка при редактировании сообщения: {e}")
        await callback.message.answer(text, reply_markup=reply_markup)  # Отправляем новое сообщение

async def get_categories_keyboard(parent_id: int | None, page: int, categories: list[Category], total_count: int) -> InlineKeyboardMarkup:
    """Генерация клавиатуры для категорий"""
    buttons = [[InlineKeyboardButton(text=cat.name, callback_data=f"category_{cat.id}_1")] for cat in categories]
    per_page = 5
    max_page = (total_count + per_page - 1) // per_page

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="←", callback_data=f"cat_page_{parent_id or 'root'}_{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"{page}/{max_page}", callback_data="noop"))
    if page < max_page:
        nav_buttons.append(InlineKeyboardButton(text="→", callback_data=f"cat_page_{parent_id or 'root'}_{page + 1}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)

    if parent_id is None:
        buttons.append([InlineKeyboardButton(text="<-- Назад", callback_data="main_menu")])
    else:
        parent = await sync_to_async(Category.objects.get)(id=parent_id)
        parent_callback = "main_menu" if parent.parent is None else f"cat_page_{parent.parent.id}_1"
        buttons.append([InlineKeyboardButton(text="<-- Назад", callback_data=parent_callback)])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def get_products_keyboard(category_id: int, page: int, products: list[Product], total_count: int) -> InlineKeyboardMarkup:
    """Генерация клавиатуры для товаров"""
    buttons = [[InlineKeyboardButton(text=prod.name, callback_data=f"product_{prod.id}")] for prod in products]
    per_page = 5
    max_page = (total_count + per_page - 1) // per_page

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="←", callback_data=f"prod_page_{category_id}_{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"{page}/{max_page}", callback_data="noop"))
    if page < max_page:
        nav_buttons.append(InlineKeyboardButton(text="→", callback_data=f"prod_page_{category_id}_{page + 1}"))

    if nav_buttons:
        buttons.append(nav_buttons)

    category = await sync_to_async(Category.objects.get)(id=category_id)
    parent_id = category.parent_id
    buttons.append([
        InlineKeyboardButton(
            text="<-- Назад",
            callback_data=f"cat_page_{parent_id or 'root'}_1"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- Обработчики ---

@router.callback_query(F.data.startswith("cat_page_"))
async def categories_pagination(callback: CallbackQuery):
    """Обработчик пагинации категорий"""
    logger.info("Запрос на пагинацию категорий.")
    try:
        parts = callback.data.split("_")
        if len(parts) == 3:  # cat_page_<page>
            _, _, page = parts
            parent_id = None
            page = int(page)
        elif len(parts) == 4:  # cat_page_<parent_id>_<page>
            _, _, parent_id, page = parts
            parent_id = None if parent_id == "root" else int(parent_id)
            page = int(page)
        else:
            raise ValueError(f"Неверное количество частей в callback_data: {callback.data}")
        logger.debug(f"Пагинация категорий для parent_id {parent_id}, страница {page}.")
    except (ValueError, IndexError) as e:
        logger.error(f"Неверный формат данных для пагинации категорий: {callback.data} - {e}")
        await callback.answer("Некорректные данные для пагинации.", show_alert=True)
        return

    categories, total_count = await get_categories_page(parent_id, page)

    if not categories:
        logger.warning(f"Категории не найдены для parent_id {parent_id}, страница {page}.")
        await callback.answer("Категории не найдены.")
        return

    kb = await get_categories_keyboard(parent_id, page, categories, total_count)
    await safe_edit_message(callback, "Выберите категорию:", kb)
    await callback.answer()
    logger.info(f"Пагинация категорий завершена для parent_id {parent_id}, страница {page}.")

@router.callback_query(F.data.startswith("category_"))
async def category_show(callback: CallbackQuery):
    """Обработчик отображения содержимого категории"""
    logger.info("Запрос на отображение содержимого категории.")
    try:
        _, cat_id, page = callback.data.split("_")
        cat_id = int(cat_id)
        page = int(page)
        logger.debug(f"Показ содержимого для категории ID {cat_id}, страница {page}.")
    except (ValueError, IndexError) as e:
        logger.error(f"Неверный формат данных для отображения категории: {callback.data} - {e}")
        await callback.answer("Некорректные данные для отображения категории.", show_alert=True)
        return

    # Проверяем, есть ли подкатегории
    subcategories, subcat_count = await get_categories_page(cat_id, 1)
    if subcategories:
        # Если есть подкатегории, показываем их
        kb = await get_categories_keyboard(cat_id, 1, subcategories, subcat_count)
        await safe_edit_message(callback, "Выберите категорию:", kb)
    else:
        # Если подкатегорий нет, показываем товары
        products, total_count = await get_products_page(cat_id, page)
        if not products:
            logger.warning(f"Товары не найдены для категории ID {cat_id}, страница {page}.")
            await callback.answer("Товары не найдены.")
            return
        kb = await get_products_keyboard(cat_id, page, products, total_count)
        await safe_edit_message(callback, "Выберите товар:", kb)

    await callback.answer()

@router.callback_query(F.data.startswith("prod_page_"))
async def products_pagination(callback: CallbackQuery):
    """Обработчик пагинации товаров"""
    logger.info("Запрос на пагинацию товаров.")
    try:
        _, _, category_id, page = callback.data.split("_")
        category_id = int(category_id)
        page = int(page)
        logger.debug(f"Пагинация товаров для category_id {category_id}, страница {page}.")
    except (ValueError, IndexError) as e:
        logger.error(f"Неверный формат данных для пагинации товаров: {callback.data} - {e}")
        await callback.answer("Некорректные данные для пагинации товаров.", show_alert=True)
        return

    products, total_count = await get_products_page(category_id, page)

    if not products:
        logger.warning(f"Товары не найдены для категории ID {category_id}, страница {page}.")
        await callback.answer("Товары не найдены.")
        return

    kb = await get_products_keyboard(category_id, page, products, total_count)
    await safe_edit_message(callback, "Выберите товар:", kb)
    await callback.answer()
    logger.info(f"Пагинация товаров завершена для category_id {category_id}, страница {page}.")
