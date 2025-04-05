import os
import django
import logging
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from asgiref.sync import sync_to_async

from django_app.shop.models import TelegramUser, Cart, Order, Category, Product
from bot.handlers.cart import get_cart_total, get_cart_quantity  # Импортируем функции из cart.py

router = Router()

# Настройка логирования
logger = logging.getLogger(__name__)

# Количество товаров на странице в прайс-листе
ITEMS_PER_PAGE = 10

def register_start_handlers(dp):
    """
    Регистрирует маршрутизатор обработчиков стартовых команд в диспетчере.
    """
    dp.include_router(router)
    logger.info("Обработчики стартовых команд зарегистрированы в диспетчере.")

@sync_to_async(thread_sensitive=True)
def get_or_create_user(user_id: int, **kwargs) -> tuple[TelegramUser, bool]:
    """
    Получение пользователя по его Telegram ID или создание нового, если он не существует.
    """
    user, created = TelegramUser.objects.get_or_create(
        telegram_id=user_id,
        defaults={
            'first_name': kwargs.get('first_name'),
            'last_name': kwargs.get('last_name'),
            'username': kwargs.get('username'),
            'language_code': kwargs.get('language_code'),
            'is_active': True
        }
    )
    if created:
        logger.info(f"Создан новый пользователь: {user}")
    else:
        logger.debug(f"Пользователь найден: {user}")
    return user, created

@sync_to_async
def get_user_info(user: TelegramUser) -> str:
    """
    Формирует текстовое описание информации о пользователе.
    """
    logger.debug(f"Получение информации о пользователе: {user.telegram_id}")
    info = (
        f"👤 Имя: {user.first_name or 'Не указано'}\n"
        f"Фамилия: {user.last_name or 'Не указана'}\n"
        f"Username: @{user.username if user.username else 'Не указан'}\n"
        f"Язык: {user.language_code or 'Не указан'}\n"
        f"ID: {user.telegram_id}"
    )
    return info

@sync_to_async
def get_user_orders(user: TelegramUser, limit: int = 5) -> list[Order]:
    """
    Получает последние заказы пользователя.
    """
    logger.debug(f"Получение последних заказов для пользователя: {user.telegram_id}")
    orders = list(Order.objects.filter(
        user=user,
        is_active=True
    ).order_by('-created_at')[:limit])
    return orders

@sync_to_async
def get_pending_orders(user: TelegramUser) -> list[Order]:
    """
    Получает заказы пользователя, которые не доставлены (статус != 'Доставлен').
    """
    logger.debug(f"Получение недоставленных заказов для пользователя: {user.telegram_id}")
    pending_orders = list(Order.objects.filter(
        user=user,
        is_active=True,
        status__in=['Ожидает оплаты', 'Оплачен', 'В доставке']
    ).order_by('-created_at'))
    return pending_orders

@sync_to_async
def get_price_list(page: int) -> tuple[str, int]:
    """
    Получает список товаров с пагинацией для прайс-листа.
    """
    logger.debug(f"Получение прайс-листа для страницы {page}")
    categories = Category.objects.filter(is_active=True).prefetch_related('products')
    products = Product.objects.filter(is_active=True).order_by('category__name', 'name')
    total_products = products.count()
    total_pages = (total_products + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    products_on_page = products[start:end]

    text = "📋 Прайс-лист\n\n"
    current_category = None
    for product in products_on_page:
        if product.category != current_category:
            current_category = product.category
            text += f"**{current_category.name}**\n"
        text += f"• {product.name} — {product.price} ₽\n"
    if not products_on_page:
        text += "Товаров пока нет.\n"
    return text, total_pages

async def format_user_profile(user: TelegramUser) -> str:
    """
    Формирует текст профиля пользователя.
    """
    user_info = await get_user_info(user)
    orders = await get_user_orders(user, limit=5)
    pending_orders = await get_pending_orders(user)

    text = f"👤 Профиль\n\n{user_info}\n\n"
    if pending_orders:
        text += "📬 Текущие заказы (не доставлены):\n\n"
        for order in pending_orders:
            text += (
                f"Заказ #{order.id} от {order.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                f"Сумма: {order.total} ₽\n"
                f"Статус: {order.status}\n"
                f"Адрес: {order.address}\n\n"
            )
    else:
        text += "📬 Нет текущих заказов.\n\n"

    if not orders:
        text += "📦 Заказов пока нет. Загляни в каталог и выбери что-нибудь интересное! 🛍️"
    else:
        text += "📦 Последние заказы:\n\n"
        for order in orders:
            text += (
                f"Заказ #{order.id} от {order.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                f"Сумма: {order.total} ₽\n"
                f"Статус: {order.status}\n"
                f"Адрес: {order.address}\n\n"
            )
    return text

async def profile_keyboard(user: TelegramUser) -> InlineKeyboardMarkup:
    """
    Создание клавиатуры для профиля.
    """
    logger.debug("Создание клавиатуры профиля.")
    cart_quantity = await get_cart_quantity(user)
    cart_total = await get_cart_total(user)
    pending_orders = await get_pending_orders(user)

    buttons = []
    for order in pending_orders:
        try:
            if not order.is_paid and order.status != "Доставлен":
                buttons.append([
                    InlineKeyboardButton(
                        text=f"💳 Оплатить заказ #{order.id} ({order.total} ₽)",
                        callback_data=f"pay_order_{order.id}"
                    )
                ])
        except AttributeError:
            if order.status != "Доставлен":
                buttons.append([
                    InlineKeyboardButton(
                        text=f"💳 Оплатить заказ #{order.id} ({order.total} ₽)",
                        callback_data=f"pay_order_{order.id}"
                    )
                ])

    # Первый ряд: Каталог и Прайс-лист (без кнопки "Профиль")
    buttons.append([
        InlineKeyboardButton(text="🛍️ Каталог", callback_data="cat_page_root_1"),
        InlineKeyboardButton(text="📋 Прайс-лист", callback_data="price_list_1")
    ])

    # Второй ряд: FAQ
    buttons.append([InlineKeyboardButton(text="❓ FAQ", callback_data="faq")])

    # Третий ряд: Корзина (всегда показываем, даже если пуста)
    cart_text = f"🛒 Корзина: {cart_total} ₽ ({cart_quantity} шт.)" if cart_quantity > 0 else "🛒 Корзина: пуста"
    buttons.append([InlineKeyboardButton(text=cart_text, callback_data="cart")])

    # Четвёртый ряд: Назад и В меню
    buttons.append([
        InlineKeyboardButton(text="<-- Назад", callback_data="main_menu"),
        InlineKeyboardButton(text="В меню", callback_data="main_menu")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def main_menu_keyboard(user: TelegramUser) -> InlineKeyboardMarkup:
    """
    Создание основной инлайн-клавиатуры.
    """
    logger.debug("Создание основной клавиатуры меню.")
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
        ]
    ]

    # Всегда показываем корзину, даже если она пуста
    cart_text = f"🛒 Корзина: {cart_total} ₽ ({cart_quantity} шт.)" if cart_quantity > 0 else "🛒 Корзина: пуста"
    buttons.append([InlineKeyboardButton(text=cart_text, callback_data="cart")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def welcome_message(user_name: str, has_cart: bool = False) -> str:
    """
    Формирование приветственного сообщения.
    """
    message = (
        f"👋 Добро пожаловать, {user_name}!\n\n"
        "Мы рады видеть вас в нашем магазине! 🛍️\n"
        "Выберите действие в меню ниже:\n\n"
        "🔹 Посмотрите наш Каталог с товарами\n"
        "🔹 Ознакомьтесь с Прайс-листом\n"
        "🔹 Проверьте свой Профиль\n"
        "🔹 Найдите ответы на вопросы в разделе FAQ\n"
        "🔹 Загляните в Корзину\n"
    )
    logger.debug(f"Формирование приветственного сообщения для пользователя {user_name}.")
    return message

@sync_to_async
def has_orders_or_cart(user: TelegramUser) -> bool:
    """
    Проверяет, есть ли у пользователя активные заказы или корзина.
    """
    has_cart = Cart.objects.filter(user=user, is_active=True).exists()
    has_orders = Order.objects.filter(user=user, is_active=True).exists()
    return has_cart or has_orders

@router.message(F.text == "/start")
async def start_command(message: Message):
    """
    Обработчик команды /start.
    """
    bot = message.bot
    user_id = message.from_user.id
    logger.info(f"Получена команда /start от пользователя {user_id}.")

    user_data = message.from_user
    user, _ = await get_or_create_user(
        user_id=user_data.id,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        username=user_data.username,
        language_code=user_data.language_code
    )
    logger.debug(f"Пользователь {user_id} обработан.")

    has_cart = await get_cart_quantity(user) > 0
    await message.answer(
        welcome_message(message.from_user.first_name, has_cart),
        reply_markup=await main_menu_keyboard(user)
    )

@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery):
    """
    Обработчик возврата в главное меню.
    """
    try:
        user, _ = await get_or_create_user(
            user_id=callback.from_user.id,
            first_name=callback.from_user.first_name
        )
        menu_text = welcome_message(callback.from_user.first_name, await get_cart_quantity(user) > 0)
        menu_markup = await main_menu_keyboard(user)
        await callback.message.answer(text=menu_text, reply_markup=menu_markup)
        try:
            await callback.message.delete()
        except:
            pass
    except Exception as e:
        logger.error(f"Ошибка в main_menu: {str(e)}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)
    finally:
        await callback.answer()

@router.callback_query(F.data == "cart_total")
async def show_cart_total(callback: CallbackQuery):
    """
    Обработчик для кнопки "Сумма корзины".
    """
    user_id = callback.from_user.id
    user, _ = await get_or_create_user(user_id=user_id, first_name=callback.from_user.first_name)
    logger.info(f"Пользователь {user_id} запросил сумму корзины.")

    cart_total = await get_cart_total(user)
    cart_quantity = await get_cart_quantity(user)
    await callback.answer(f"Сумма корзины: {cart_total} ₽ ({cart_quantity} шт.)", show_alert=True)

    has_cart = cart_quantity > 0
    try:
        await callback.message.edit_text(
            welcome_message(callback.from_user.first_name, has_cart),
            reply_markup=await main_menu_keyboard(user)
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e).lower():
            logger.error(f"Ошибка при обновлении сообщения: {e}")
            await callback.message.answer(
                welcome_message(callback.from_user.first_name, has_cart),
                reply_markup=await main_menu_keyboard(user)
            )

@router.callback_query(F.data == "profile")
@router.message(F.text == "/profile")
async def show_profile(request: Message | CallbackQuery) -> None:
    """
    Обработчик для кнопки "Профиль" и команды /profile.
    """
    user_id = request.from_user.id
    user, _ = await get_or_create_user(user_id=user_id, first_name=request.from_user.first_name)
    logger.info(f"Пользователь {user_id} запросил профиль.")

    text = await format_user_profile(user)
    keyboard = await profile_keyboard(user)

    try:
        if isinstance(request, Message):
            await request.answer(text, reply_markup=keyboard)
        else:
            await request.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e).lower():
            logger.error(f"Ошибка при обновлении сообщения: {e}")
            if isinstance(request, Message):
                await request.answer(text, reply_markup=keyboard)
            else:
                await request.message.answer(text, reply_markup=keyboard)
    if isinstance(request, CallbackQuery):
        await request.answer()

@router.callback_query(F.data.startswith("pay_order_"))
async def handle_payment(callback: CallbackQuery):
    """
    Обработчик для кнопки "Оплатить заказ".
    """
    order_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    user, _ = await get_or_create_user(user_id=user_id, first_name=callback.from_user.first_name)
    logger.info(f"Пользователь {user_id} инициировал оплату заказа #{order_id}.")

    try:
        order = await sync_to_async(Order.objects.get)(id=order_id, user=user)
        try:
            if order.is_paid:
                await callback.answer("Этот заказ уже оплачен!", show_alert=True)
                return
        except AttributeError:
            pass  # Если поле is_paid отсутствует, пропускаем проверку

        if order.status == "Доставлен":
            await callback.answer("Этот заказ уже доставлен!", show_alert=True)
            return

        payment_link = f"https://example.com/pay/{order_id}"
        await callback.message.answer(
            f"💳 Для оплаты заказа #{order_id} на сумму {order.total} ₽ перейдите по ссылке:\n{payment_link}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад в профиль", callback_data="profile"),
                 InlineKeyboardButton(text="В меню", callback_data="main_menu")]
            ])
        )
        try:
            await callback.message.delete()
        except:
            pass
    except Order.DoesNotExist:
        logger.error(f"Заказ #{order_id} не найден для пользователя {user_id}.")
        await callback.answer("❌ Заказ не найден", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка при обработке оплаты заказа #{order_id}: {str(e)}")
        await callback.answer("❌ Произошла ошибка при обработке оплаты", show_alert=True)
    finally:
        await callback.answer()

@router.callback_query(F.data.startswith("price_list_"))
async def show_price_list(callback: CallbackQuery):
    """
    Обработчик для кнопки "Прайс-лист".
    """
    page = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    logger.info(f"Пользователь {user_id} запросил прайс-лист, страница {page}.")

    try:
        price_list_text, total_pages = await get_price_list(page)
        user, _ = await get_or_create_user(user_id=user_id, first_name=callback.from_user.first_name)
        cart_quantity = await get_cart_quantity(user)
        cart_total = await get_cart_total(user)

        buttons = []
        # Пагинация (только если больше 1 страницы)
        if total_pages > 1:
            pagination_buttons = []
            if page > 1:
                pagination_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"price_list_{page - 1}"))
            pagination_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
            if page < total_pages:
                pagination_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"price_list_{page + 1}"))
            buttons.append(pagination_buttons)

        # Второй ряд: Только Каталог (без кнопки "Прайс-лист")
        buttons.append([InlineKeyboardButton(text="🛍️ Каталог", callback_data="cat_page_root_1")])

        # Третий ряд: Корзина (всегда показываем, даже если пуста)
        cart_text = f"🛒 Корзина: {cart_total} ₽ ({cart_quantity} шт.)" if cart_quantity > 0 else "🛒 Корзина: пуста"
        buttons.append([InlineKeyboardButton(text=cart_text, callback_data="cart")])

        # Четвёртый ряд: Назад и В меню
        buttons.append([
            InlineKeyboardButton(text="<-- Назад", callback_data="main_menu"),
            InlineKeyboardButton(text="В меню", callback_data="main_menu")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_text(price_list_text, reply_markup=keyboard, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка при отображении прайс-листа: {str(e)}")
        await callback.answer("❌ Произошла ошибка при отображении прайс-листа", show_alert=True)
    finally:
        await callback.answer()
