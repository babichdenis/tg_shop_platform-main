# File: bot/handlers/catalog/views.py
import logging
from typing import Tuple, List
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from asgiref.sync import sync_to_async
from django_app.shop.models import Category, Product, TelegramUser
from bot.handlers.cart.models import get_cart_quantity, get_cart_total
from bot.core.config import CATEGORIES_PER_PAGE, PRODUCTS_PER_PAGE, SUBSCRIPTION_CHANNEL_ID, SUBSCRIPTION_GROUP_ID
from bot.core.utils import get_or_create_user
from .keyboards import build_categories_keyboard, build_products_keyboard
from bot.handlers.start.subscriptions import check_subscriptions

router = Router()

# Настройка логирования
logger = logging.getLogger(__name__)


# --- Вспомогательные функции ---

def get_category_path(category_id: str) -> str:  # Убираем @sync_to_async
    """
    Формирует путь категорий (breadcrumb) для отображения.
    :param category_id: ID категории или "root".
    :return: Строка с путём категорий (например, "Каталог > Электроника > Смартфоны").
    """
    if category_id == "root":
        return "🛍️ Каталог"

    path = []
    current_category = Category.objects.get(id=category_id)
    while current_category:
        path.append(current_category.name)
        current_category = current_category.parent
    path.reverse()
    return "🛍️ " + " > ".join(path)


@sync_to_async
def get_categories(parent_id: str, page: int) -> Tuple[str, List[Category], int]:
    """
    Получает категории для отображения с пагинацией.
    :param parent_id: ID родительской категории ("root" для корневых категорий).
    :param page: Номер страницы.
    :return: Кортеж (текст сообщения, список категорий, общее количество страниц).
    """
    logger.debug(f"Получение категорий: parent_id={parent_id}, page={page}")

    if parent_id == "root":
        categories = Category.objects.filter(parent__isnull=True, is_active=True)
    else:
        categories = Category.objects.filter(parent_id=parent_id, is_active=True)

    total_categories = categories.count()
    total_pages = max(1, (total_categories + CATEGORIES_PER_PAGE - 1) // CATEGORIES_PER_PAGE)
    page = max(1, min(page, total_pages))  # Ограничиваем страницу
    start = (page - 1) * CATEGORIES_PER_PAGE
    end = start + CATEGORIES_PER_PAGE
    categories_on_page = list(categories[start:end])

    if not categories_on_page:
        breadcrumb = get_category_path(parent_id)  # Вызов синхронный
        return f"{breadcrumb}\n\nКатегории не найдены.", [], 0

    breadcrumb = get_category_path(parent_id)  # Вызов синхронный
    text = f"{breadcrumb}\n\nВыберите {'категорию' if parent_id == 'root' else 'подкатегорию'}:"
    return text, categories_on_page, total_pages


@sync_to_async
def get_products_page(category_id: int, page: int, per_page: int = PRODUCTS_PER_PAGE) -> Tuple[List[Product], int]:
    """
    Получение страницы товаров с пагинацией.
    :param category_id: ID категории.
    :param page: Номер страницы.
    :param per_page: Количество товаров на странице.
    :return: Кортеж (список товаров, общее количество товаров).
    """
    logger.debug(f"Получение товаров: category_id={category_id}, page={page}")
    qs = Product.objects.filter(category_id=category_id, is_active=True)
    total_count = qs.count()
    start = (page - 1) * per_page
    end = start + per_page
    products = list(qs[start:end])
    return products, total_count


async def safe_edit_message(callback: CallbackQuery, text: str, reply_markup=None) -> None:
    """
    Безопасное редактирование сообщения.
    :param callback: CallbackQuery объект.
    :param text: Текст сообщения.
    :param reply_markup: Клавиатура (опционально).
    """
    try:
        await callback.message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        logger.debug(f"Сообщение успешно отредактировано: {text[:50]}...")
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            logger.debug(f"Сообщение не изменено (уже актуально): {text[:50]}...")
        else:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
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


# --- Обработчики ---

@router.message(F.text == "/catalog")
async def catalog_command(message: Message) -> None:
    """
    Обработчик команды /catalog для открытия каталога.
    """
    try:
        user_id = message.from_user.id
        logger.info(f"Пользователь {user_id} вызвал команду /catalog.")

        # Проверка подписки
        if SUBSCRIPTION_CHANNEL_ID or SUBSCRIPTION_GROUP_ID:
            subscription_result, message_text = await check_subscriptions(message.bot, user_id, "/catalog")
            if not subscription_result:
                await message.answer(
                    message_text,
                    disable_web_page_preview=True,
                    parse_mode="Markdown"
                )
                return

        # Получаем текст, категории и общее количество страниц
        text, categories, total_pages = await get_categories("root", 1)

        # Получаем данные пользователя
        user, _ = await get_or_create_user(
            user_id=user_id,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            username=message.from_user.username,
            language_code=message.from_user.language_code
        )

        # Формируем клавиатуру для категорий
        keyboard = await build_categories_keyboard(categories, "root", 1, total_pages, user)

        # Отправляем сообщение
        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Ошибка при выполнении команды /catalog: {e}")
        await message.answer("❌ Произошла ошибка при открытии каталога")


@router.callback_query(F.data.startswith("cat_page_"))
async def categories_pagination(callback: CallbackQuery) -> None:
    """
    Обработчик для отображения категорий с пагинацией.
    """
    try:
        # Разбираем callback_data (формат: "cat_page_<parent_id>_<page>")
        parts = callback.data.split("_")
        if len(parts) != 4:
            raise ValueError(f"Неверный формат callback_data: {callback.data}")

        parent_id = parts[2]  # Например, "root" или ID категории
        page = int(parts[3])
        user_id = callback.from_user.id
        logger.info(f"Пользователь {user_id} запросил категории, parent_id={parent_id}, страница {page}.")

        # Получаем текст, категории и общее количество страниц
        text, categories, total_pages = await get_categories(parent_id, page)

        # Получаем данные пользователя
        user, _ = await get_or_create_user(
            user_id=user_id,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
            username=callback.from_user.username,
            language_code=callback.from_user.language_code
        )

        # Проверяем, есть ли подкатегории
        if parent_id != "root":
            _, subcategories, _ = await get_categories(parent_id, 1)
            if not subcategories:
                # Если подкатегорий нет, показываем товары
                products, total_count = await get_products_page(int(parent_id), page)
                if products:
                    breadcrumb = await sync_to_async(get_category_path)(parent_id)  # Добавляем sync_to_async
                    kb = await build_products_keyboard(int(parent_id), page, products, total_count, user)
                    await safe_edit_message(callback, f"{breadcrumb}\n\n🛍️ Выберите товар:", kb)
                    await callback.answer()
                    return
                else:
                    text = f"{breadcrumb}\n\nТовары не найдены."

        # Формируем клавиатуру для категорий
        keyboard = await build_categories_keyboard(categories, parent_id, page, total_pages, user)

        # Обновляем сообщение
        await safe_edit_message(callback, text, keyboard)

    except ValueError as e:
        logger.error(f"Ошибка формата данных: {e}")
        await callback.answer("❌ Неверный формат данных", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка при отображении категорий: {str(e)}")
        await callback.answer("❌ Произошла ошибка при отображении категорий", show_alert=True)
    finally:
        await callback.answer()


@router.callback_query(F.data.startswith("prod_page_"))
async def products_pagination(callback: CallbackQuery) -> None:
    """
    Обработчик пагинации товаров.
    """
    try:
        parts = callback.data.split("_")
        if len(parts) != 4:
            raise ValueError(f"Неверный формат callback_data: {callback.data}")

        category_id = int(parts[2])
        page = int(parts[3])
        logger.info(f"Пагинация товаров для category_id {category_id}, страница {page}.")

        # Получаем данные пользователя
        user, _ = await get_or_create_user(
            user_id=callback.from_user.id,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
            username=callback.from_user.username,
            language_code=callback.from_user.language_code
        )

        # Получаем товары
        products, total_count = await get_products_page(category_id, page)

        if not products:
            logger.warning(f"Товары не найдены для категории ID {category_id}, страница {page}.")
            breadcrumb = await sync_to_async(get_category_path)(str(category_id))  # Добавляем sync_to_async
            await safe_edit_message(callback, f"{breadcrumb}\n\nТовары не найдены.", None)
            await callback.answer()
            return

        # Формируем клавиатуру для товаров
        breadcrumb = await sync_to_async(get_category_path)(str(category_id))  # Добавляем sync_to_async
        kb = await build_products_keyboard(category_id, page, products, total_count, user)
        await safe_edit_message(callback, f"{breadcrumb}\n\n🛍️ Выберите товар:", kb)

    except ValueError as e:
        logger.error(f"Ошибка формата данных: {e}")
        await callback.answer("❌ Неверный формат данных", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка при пагинации товаров: {str(e)}")
        await callback.answer("❌ Произошла ошибка при отображении товаров", show_alert=True)
    finally:
        await callback.answer()


@router.callback_query(F.data == "catalog")
async def catalog_callback(callback: CallbackQuery) -> None:
    """
    Обработчик нажатия кнопки 'Каталог'.
    """
    try:
        user_id = callback.from_user.id
        logger.info(f"Пользователь {user_id} нажал кнопку 'Каталог'.")

        # Проверка подписки
        if SUBSCRIPTION_CHANNEL_ID or SUBSCRIPTION_GROUP_ID:
            subscription_result, message_text = await check_subscriptions(callback.bot, user_id, "catalog")
            if not subscription_result:
                try:
                    await callback.message.edit_text(
                        message_text,
                        disable_web_page_preview=True,
                        parse_mode="Markdown"
                    )
                except TelegramBadRequest:
                    await callback.message.answer(
                        message_text,
                        disable_web_page_preview=True,
                        parse_mode="Markdown"
                    )
                await callback.answer()
                return

        # Получаем текст, категории и общее количество страниц
        text, categories, total_pages = await get_categories("root", 1)

        # Получаем данные пользователя
        user, _ = await get_or_create_user(
            user_id=user_id,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
            username=callback.from_user.username,
            language_code=callback.from_user.language_code
        )

        # Формируем клавиатуру для категорий
        keyboard = await build_categories_keyboard(categories, "root", 1, total_pages, user)

        # Обновляем сообщение
        await safe_edit_message(callback, text, keyboard)

    except Exception as e:
        logger.error(f"Ошибка при выполнении callback 'catalog': {e}")
        await callback.answer("❌ Произошла ошибка при открытии каталога", show_alert=True)
    finally:
        await callback.answer()
