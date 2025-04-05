import os
import django
import logging
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from asgiref.sync import sync_to_async

from django_app.shop.models import TelegramUser, Cart, Order
from bot.handlers.cart import get_cart_total, get_cart_quantity  # Импортируем функции из cart.py

router = Router()

# Настройка логирования
logger = logging.getLogger(__name__)

def register_start_handlers(dp):
    """
    Регистрирует маршрутизатор обработчиков стартовых команд в диспетчере.
    """
    dp.include_router(router)
    logger.info("Обработчики стартовых команд зарегистрированы в диспетчере.")

@sync_to_async(thread_sensitive=True)
def get_or_create_user(user_id: int, **kwargs) -> TelegramUser:
    """
    Получение пользователя по его Telegram ID или создание нового, если он не существует.

    :param user_id: Telegram ID пользователя
    :param kwargs: Дополнительные данные пользователя
    :return: Объект TelegramUser
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
    return user

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

async def format_user_profile(user: TelegramUser) -> str:
    """
    Формирует текст профиля пользователя с информацией и последними заказами.
    """
    # Получаем информацию о пользователе
    user_info = await get_user_info(user)

    # Получаем последние заказы
    orders = await get_user_orders(user, limit=5)

    # Формируем текст профиля
    text = f"👤 Профиль\n\n{user_info}\n\n"

    # Добавляем информацию о заказах
    if not orders:
        text += "📦 Заказов пока нет. Загляни в каталог и выбери что-нибудь интересное! 🛍️"
    else:
        text += "📦 Последние заказы:\n\n"
        for order in orders:
            text += (
                f"Заказ #{order.id} от {order.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                f"Сумма: {order.total} ₽\n"
                f"Статус: {'Оплачен' if order.is_paid else 'Ожидает оплаты'}\n"
                f"Адрес: {order.address}\n\n"
            )

    return text

async def main_menu_keyboard(user: TelegramUser) -> InlineKeyboardMarkup:
    """
    Создание основной инлайн-клавиатуры с учётом состояния корзины.

    :param user: Объект TelegramUser
    :return: Объект InlineKeyboardMarkup с кнопками меню
    """
    logger.debug("Создание основной клавиатуры меню.")
    cart_quantity = await get_cart_quantity(user)  # Получаем количество товаров
    cart_total = await get_cart_total(user)  # Получаем сумму корзины

    buttons = [
        [InlineKeyboardButton(text="🛍️ Каталог", callback_data="cat_page_root_1")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="❓ FAQ", callback_data="faq")]
    ]

    # Добавляем кнопку "Корзина" внизу, если корзина не пуста
    if cart_quantity > 0:
        buttons.append([
            InlineKeyboardButton(
                text=f"🛒 Корзина: {cart_total} ₽ ({cart_quantity} шт.)",
                callback_data="cart"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)



def welcome_message(user_name: str, has_cart: bool = False) -> str:
    """
    Формирование приветственного сообщения для пользователя.

    :param user_name: Имя пользователя
    :param has_cart: Флаг, показывающий, пуста ли корзина
    :return: Строка приветственного сообщения
    """
    message = (
        f"👋 Добро пожаловать, {user_name}!\n\n"
        "Мы рады видеть вас в нашем магазине! 🛍️\n"
        "Выберите действие в меню ниже:\n\n"
        "🔹 Посмотрите наш Каталог с товарами\n"
        "🔹 Проверьте свой Профиль\n"
        "🔹 Найдите ответы на вопросы в разделе FAQ\n"
    )
    if has_cart:
        message += "🔹 Загляните в корзину, чтобы оформить покупку\n"
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
    Обработчик команды /start. Проверяет подписку пользователя и приветствует его.

    :param message: Объект сообщения
    """
    bot = message.bot
    user_id = message.from_user.id
    logger.info(f"Получена команда /start от пользователя {user_id}.")

    user_data = message.from_user
    user = await get_or_create_user(
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
    Простой обработчик возврата в главное меню
    """
    try:
        user = await get_or_create_user(
            user_id=callback.from_user.id,
            first_name=callback.from_user.first_name
        )
        
        # Получаем актуальные данные для меню
        menu_text = welcome_message(callback.from_user.first_name, 
                                  await get_cart_quantity(user) > 0)
        menu_markup = await main_menu_keyboard(user)
        
        # Всегда отправляем новое сообщение (самый простой и надежный способ)
        await callback.message.answer(
            text=menu_text,
            reply_markup=menu_markup
        )
        
        # Удаляем предыдущее сообщение (опционально)
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
    Обработчик для кнопки "Сумма корзины". Просто показывает текущую сумму и обновляет меню.
    """
    user_id = callback.from_user.id
    user = await get_or_create_user(user_id, first_name=callback.from_user.first_name)
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
    Показывает информацию о пользователе и его последние заказы.
    """
    user_id = request.from_user.id
    user = await get_or_create_user(user_id, first_name=request.from_user.first_name)
    logger.info(f"Пользователь {user_id} запросил профиль.")

    # Формируем текст профиля
    text = await format_user_profile(user)

    buttons = [
        [InlineKeyboardButton(text="<-- Назад", callback_data="main_menu")]
    ]

    try:
        if isinstance(request, Message):
            await request.answer(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
            )
        else:
            await request.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
            )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e).lower():
            logger.error(f"Ошибка при обновлении сообщения: {e}")
            if isinstance(request, Message):
                await request.answer(
                    text,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
                )
            else:
                await request.message.answer(
                    text,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
                )
    await request.answer() if isinstance(request, CallbackQuery) else None
