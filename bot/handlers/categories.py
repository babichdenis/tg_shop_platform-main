# bot/handlers/categories.py
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest
from asgiref.sync import sync_to_async
from django_app.shop.models import Category, Product, TelegramUser
from bot.handlers.cart import get_cart_total, get_cart_quantity

router = Router()

# Настройка логирования
logger = logging.getLogger(__name__)

# Количество элементов на странице
CATEGORIES_PER_PAGE = 5
PRODUCTS_PER_PAGE = 5

# --- Вспомогательные функции ---

@sync_to_async
def get_categories(parent_id: str, page: int) -> tuple[str, list[Category], int]:
    """
    Получает категории для отображения с пагинацией.
    """
    logger.debug(f"Получение категорий: parent_id={parent_id}, page={page}")

    if parent_id == "root":
        categories = Category.objects.filter(parent__isnull=True, is_active=True)
    else:
        categories = Category.objects.filter(parent_id=parent_id, is_active=True)

    total_categories = categories.count()
    total_pages = (total_categories + CATEGORIES_PER_PAGE - 1) // CATEGORIES_PER_PAGE
    start = (page - 1) * CATEGORIES_PER_PAGE
    end = start + CATEGORIES_PER_PAGE
    categories_on_page = list(categories[start:end])

    if not categories_on_page:
        return "Категории не найдены.", [], 0

    if parent_id == "root":
        text = "🛍️ Каталог\n\nВыберите категорию:"
    else:
        parent = Category.objects.get(id=parent_id)
        text = f"🛍️ Каталог > {parent.name}\n\nВыберите подкатегорию:"

    return text, categories_on_page, total_pages

@sync_to_async
def get_products_page(category_id: int, page: int, per_page: int = PRODUCTS_PER_PAGE) -> tuple[list[Product], int]:
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
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            logger.debug(f"Сообщение не изменено (уже актуально): {text[:50]}...")
        else:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            # Удаляем старое сообщение (например, с фото) и отправляем новое
            try:
                await callback.message.delete()
                await callback.message.answer(
                    text,
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
            except Exception as delete_error:
                logger.error(f"Ошибка при удалении и отправке нового сообщения: {delete_error}")
                await callback.message.answer(
                    text,
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
    except Exception as e:
        logger.error(f"Неизвестная ошибка при редактировании сообщения: {e}")
        # Удаляем старое сообщение и отправляем новое
        try:
            await callback.message.delete()
            await callback.message.answer(
                text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        except Exception as delete_error:
            logger.error(f"Ошибка при удалении и отправке нового сообщения: {delete_error}")
            await callback.message.answer(
                text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )

async def get_products_keyboard(category_id: int, page: int, products: list[Product], total_count: int, user: TelegramUser) -> InlineKeyboardMarkup:
    """Генерация клавиатуры для товаров"""
    buttons = [[InlineKeyboardButton(text=prod.name, callback_data=f"product_{prod.id}")] for prod in products]
    max_page = (total_count + PRODUCTS_PER_PAGE - 1) // PRODUCTS_PER_PAGE

    # Пагинация (только если больше 1 страницы)
    if max_page > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"prod_page_{category_id}_{page - 1}"))
        nav_buttons.append(InlineKeyboardButton(text=f"{page}/{max_page}", callback_data="noop"))
        if page < max_page:
            nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"prod_page_{category_id}_{page + 1}"))
        buttons.append(nav_buttons)

    # Получаем данные корзины
    cart_quantity = await get_cart_quantity(user)
    cart_total = await get_cart_total(user)

    # Кнопка "Прайс-лист"
    buttons.append([
        InlineKeyboardButton(text="📋 Прайс-лист", callback_data="price_list_1")
    ])

    # Кнопка корзины
    cart_text = f"🛒 Корзина: {cart_total} ₽ ({cart_quantity} шт.)" if cart_quantity > 0 else "🛒 Корзина: пуста"
    buttons.append([
        InlineKeyboardButton(text=cart_text, callback_data="cart")
    ])

    # Кнопки "Назад" и "В меню"
    category = await sync_to_async(Category.objects.get)(id=category_id)
    parent_id = category.parent_id
    back_callback = f"cat_page_{parent_id or 'root'}_1"
    buttons.append([
        InlineKeyboardButton(text="<-- Назад", callback_data=back_callback),
        InlineKeyboardButton(text="В меню", callback_data="main_menu")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- Обработчики ---

@router.message(F.text == "/catalog")
async def catalog_command(message: Message):
    """
    Обработчик команды /catalog для открытия каталога.
    """
    try:
        user_id = message.from_user.id
        logger.info(f"Пользователь {user_id} вызвал команду /catalog.")

        # Получаем текст, категории и общее количество страниц
        text, categories, total_pages = await get_categories("root", 1)

        # Получаем данные корзины
        user, _ = await sync_to_async(TelegramUser.objects.get_or_create)(
            telegram_id=user_id,
            defaults={
                'first_name': message.from_user.first_name,
                'is_active': True
            }
        )
        cart_quantity = await get_cart_quantity(user)
        cart_total = await get_cart_total(user)

        # Формируем клавиатуру для категорий
        buttons = []

        # Добавляем кнопки категорий
        for category in categories:
            buttons.append([
                InlineKeyboardButton(
                    text=category.name,
                    callback_data=f"cat_page_{category.id}_{1}"
                )
            ])

        # Пагинация (только если больше 1 страницы)
        if total_pages > 1:
            pagination_buttons = []
            pagination_buttons.append(
                InlineKeyboardButton(text="⬅️", callback_data=f"cat_page_root_0")
            )
            pagination_buttons.append(
                InlineKeyboardButton(text=f"1/{total_pages}", callback_data="noop")
            )
            pagination_buttons.append(
                InlineKeyboardButton(text="➡️", callback_data=f"cat_page_root_2")
            )
            buttons.append(pagination_buttons)

        # Кнопка "Прайс-лист"
        buttons.append([
            InlineKeyboardButton(text="📋 Прайс-лист", callback_data="price_list_1")
        ])

        # Кнопка корзины
        cart_text = f"🛒 Корзина: {cart_total} ₽ ({cart_quantity} шт.)" if cart_quantity > 0 else "🛒 Корзина: пуста"
        buttons.append([
            InlineKeyboardButton(text=cart_text, callback_data="cart")
        ])

        # Кнопка "Назад" и "В меню"
        buttons.append([
            InlineKeyboardButton(text="<-- Назад", callback_data="main_menu"),
            InlineKeyboardButton(text="В меню", callback_data="main_menu")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        # Отправляем сообщение
        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Ошибка при выполнении команды /catalog: {str(e)}")
        await message.answer("❌ Произошла ошибка при открытии каталога")

@router.callback_query(F.data.startswith("cat_page_"))
async def categories_pagination(callback: CallbackQuery):
    """
    Обработчик для отображения категорий с пагинацией.
    """
    try:
        # Разбираем callback_data (формат: "cat_page_<parent_id>_<page>")
        parts = callback.data.split("_")
        if len(parts) == 4:
            parent_id = parts[2]  # Например, "root" или ID категории
            page = int(parts[3])
        else:
            # Обратная совместимость с форматом "cat_page_<page>"
            parent_id = "root"
            page = int(parts[2])

        user_id = callback.from_user.id
        logger.info(f"Пользователь {user_id} запросил категории, parent_id={parent_id}, страница {page}.")

        # Получаем текст, категории и общее количество страниц
        text, categories, total_pages = await get_categories(parent_id, page)

        # Получаем данные корзины
        user, _ = await sync_to_async(TelegramUser.objects.get_or_create)(
            telegram_id=user_id,
            defaults={
                'first_name': callback.from_user.first_name,
                'is_active': True
            }
        )
        cart_quantity = await get_cart_quantity(user)
        cart_total = await get_cart_total(user)

        # Проверяем, есть ли подкатегории
        if parent_id != "root":
            subcat_text, subcategories, subcat_count = await get_categories(parent_id, 1)
            if subcategories:
                # Если есть подкатегории, показываем их
                text = subcat_text
                categories = subcategories
                total_pages = subcat_count
            else:
                # Если подкатегорий нет, показываем товары
                products, total_count = await get_products_page(int(parent_id), page)
                if products:
                    kb = await get_products_keyboard(int(parent_id), page, products, total_count, user)
                    await safe_edit_message(callback, "🛍️ Выберите товар:", kb)
                    await callback.answer()
                    return
                else:
                    text = "Товары не найдены."

        # Формируем клавиатуру для категорий
        buttons = []

        # Добавляем кнопки категорий
        for category in categories:
            buttons.append([
                InlineKeyboardButton(
                    text=category.name,
                    callback_data=f"cat_page_{category.id}_{1}"
                )
            ])

        # Пагинация (только если больше 1 страницы)
        if total_pages > 1:
            pagination_buttons = []
            if page > 1:
                pagination_buttons.append(
                    InlineKeyboardButton(text="⬅️", callback_data=f"cat_page_{parent_id}_{page - 1}")
                )
            pagination_buttons.append(
                InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop")
            )
            if page < total_pages:
                pagination_buttons.append(
                    InlineKeyboardButton(text="➡️", callback_data=f"cat_page_{parent_id}_{page + 1}")
                )
            buttons.append(pagination_buttons)

        # Кнопка "Прайс-лист"
        buttons.append([
            InlineKeyboardButton(text="📋 Прайс-лист", callback_data="price_list_1")
        ])

        # Кнопка корзины
        cart_text = f"🛒 Корзина: {cart_total} ₽ ({cart_quantity} шт.)" if cart_quantity > 0 else "🛒 Корзина: пуста"
        buttons.append([
            InlineKeyboardButton(text=cart_text, callback_data="cart")
        ])

        # Кнопка "Назад" и "В меню"
        if parent_id == "root":
            back_callback = "main_menu"
        else:
            parent_category = await sync_to_async(Category.objects.get)(id=parent_id)
            back_callback = "main_menu" if parent_category.parent is None else f"cat_page_{parent_category.parent.id}_1"
        buttons.append([
            InlineKeyboardButton(text="<-- Назад", callback_data=back_callback),
            InlineKeyboardButton(text="В меню", callback_data="main_menu")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        # Обновляем сообщение
        await safe_edit_message(callback, text, keyboard)

    except Exception as e:
        logger.error(f"Ошибка при отображении категорий: {str(e)}")
        await callback.answer("❌ Произошла ошибка при отображении категорий", show_alert=True)
    finally:
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

    user, _ = await sync_to_async(TelegramUser.objects.get_or_create)(
        telegram_id=callback.from_user.id,
        defaults={
            'first_name': callback.from_user.first_name,
            'is_active': True
        }
    )
    products, total_count = await get_products_page(category_id, page)

    if not products:
        logger.warning(f"Товары не найдены для категории ID {category_id}, страница {page}.")
        await callback.answer("Товары не найдены.")
        return

    kb = await get_products_keyboard(category_id, page, products, total_count, user)
    await safe_edit_message(callback, "🛍️ Выберите товар:", kb)
    await callback.answer()
    logger.info(f"Пагинация товаров завершена для category_id {category_id}, страница {page}.")
