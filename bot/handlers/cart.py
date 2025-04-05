# bot/handlers/cart.py
import logging
from typing import List, Optional, Tuple

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
)

from asgiref.sync import sync_to_async
from django_app.shop.models import Cart, CartItem, Order, TelegramUser

# Настройка логирования
logger = logging.getLogger(__name__)

router = Router()

# --- Состояния для оформления заказа ---

class OrderStates(StatesGroup):
    WAITING_FOR_ADDRESS = State()
    WAITING_FOR_CONFIRMATION = State()

# --- Вспомогательные функции ---

@sync_to_async
def get_cart_items(user: TelegramUser) -> List[CartItem]:
    """
    Получает активные элементы корзины пользователя.
    """
    cart, _ = Cart.objects.get_or_create(user=user, is_active=True)
    items = list(
        CartItem.objects.filter(cart=cart, is_active=True).select_related("product")
    )
    logger.debug(f"Получены элементы корзины для пользователя {user.telegram_id}: {len(items)} шт.")
    return items

@sync_to_async
def get_cart_total_price(user: TelegramUser) -> int:
    """
    Вычисляет общую стоимость корзины.
    """
    cart, _ = Cart.objects.get_or_create(user=user, is_active=True)
    total = sum(item.product.price * item.quantity for item in CartItem.objects.filter(cart=cart, is_active=True))
    logger.debug(f"Общая стоимость корзины пользователя {user.telegram_id}: {total} ₽.")
    return total

async def get_cart_total(user: TelegramUser) -> int:
    """
    Асинхронная обёртка для получения общей стоимости корзины.
    """
    return await get_cart_total_price(user)

async def get_cart_quantity(user: TelegramUser) -> int:
    """
    Асинхронная обёртка для получения количества товаров в корзине.
    """
    items = await get_cart_items(user)
    return sum(item.quantity for item in items)

def cart_keyboard() -> InlineKeyboardMarkup:
    """
    Генерирует клавиатуру для корзины.
    """
    buttons = [
        [
            InlineKeyboardButton(text="Оформить заказ", callback_data="checkout"),
            InlineKeyboardButton(text="Очистить корзину", callback_data="clear_cart"),
        ],
        [
            InlineKeyboardButton(text="<-- Назад", callback_data="main_menu"),
            InlineKeyboardButton(text="В меню", callback_data="main_menu"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def cancel_keyboard() -> ReplyKeyboardMarkup:
    """
    Генерирует клавиатуру с кнопками "Назад" и "Отмена" для процесса оформления заказа.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Назад"), KeyboardButton(text="Отмена")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# --- Обработчики ---

@router.callback_query(F.data == "cart")
async def show_cart(callback: CallbackQuery, state: FSMContext):
    """
    Показывает содержимое корзины пользователя.
    """
    user_id = callback.from_user.id
    current_state = await state.get_state()
    logger.info(f"Пользователь {user_id} запросил корзину. Текущее состояние: {current_state}")

    try:
        user, _ = await sync_to_async(TelegramUser.objects.get_or_create)(
            telegram_id=user_id,
            defaults={"first_name": callback.from_user.first_name, "is_active": True}
        )
        items = await get_cart_items(user)
        total = await get_cart_total(user)

        if not items:
            await callback.message.edit_text(
                "🛒 Ваша корзина пуста.",
                reply_markup=cart_keyboard()
            )
            await callback.answer()
            return

        text = "🛒 Ваша корзина:\n\n"
        for item in items:
            text += f"{item.product.name} × {item.quantity} - {item.product.price * item.quantity} ₽\n"
        text += f"\nИтого: {total} ₽"

        await callback.message.edit_text(
            text,
            reply_markup=cart_keyboard()
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при отображении корзины для пользователя {user_id}: {e}")
        await callback.answer("❌ Произошла ошибка при отображении корзины", show_alert=True)

@router.callback_query(F.data == "checkout")
async def start_checkout(callback: CallbackQuery, state: FSMContext):
    """
    Начинает процесс оформления заказа.
    """
    user_id = callback.from_user.id
    logger.info(f"Пользователь {user_id} начал оформление заказа.")

    try:
        user, _ = await sync_to_async(TelegramUser.objects.get_or_create)(
            telegram_id=user_id,
            defaults={"first_name": callback.from_user.first_name, "is_active": True}
        )
        items = await get_cart_items(user)

        if not items:
            await callback.message.edit_text(
                "🛒 Ваша корзина пуста. Добавьте товары, чтобы оформить заказ.",
                reply_markup=cart_keyboard()
            )
            await callback.answer()
            return

        await state.set_state(OrderStates.WAITING_FOR_ADDRESS)
        await callback.message.edit_text(
            "📍 Пожалуйста, укажите адрес доставки:",
            reply_markup=cancel_keyboard()
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при начале оформления заказа для пользователя {user_id}: {e}")
        await callback.answer("❌ Произошла ошибка при оформлении заказа", show_alert=True)

@router.message(OrderStates.WAITING_FOR_ADDRESS, F.text == "Назад")
async def go_back_to_cart(message: Message, state: FSMContext):
    """
    Обрабатывает нажатие кнопки "Назад" на этапе ввода адреса, возвращая пользователя к корзине.
    """
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} вернулся к корзине на этапе ввода адреса.")

    # Удаляем клавиатуру
    await message.answer(
        "Вы вернулись к корзине.",
        reply_markup=ReplyKeyboardRemove()
    )

    # Удаляем сообщение с запросом адреса и сообщение "Назад"
    await message.bot.delete_message(
        chat_id=message.chat.id,
        message_id=message.message_id - 1
    )  # Удаляем сообщение с запросом адреса
    await message.delete()  # Удаляем сообщение "Назад"

    # Показываем корзину
    user, _ = await sync_to_async(TelegramUser.objects.get_or_create)(
        telegram_id=user_id,
        defaults={"first_name": message.from_user.first_name, "is_active": True}
    )
    items = await get_cart_items(user)
    total = await get_cart_total(user)

    if not items:
        await message.answer(
            "🛒 Ваша корзина пуста.",
            reply_markup=cart_keyboard()
        )
        return

    text = "🛒 Ваша корзина:\n\n"
    for item in items:
        text += f"{item.product.name} × {item.quantity} - {item.product.price * item.quantity} ₽\n"
    text += f"\nИтого: {total} ₽"

    await message.answer(
        text,
        reply_markup=cart_keyboard()
    )

@router.message(OrderStates.WAITING_FOR_ADDRESS, F.text == "Отмена")
async def cancel_order_at_address(message: Message, state: FSMContext):
    """
    Обрабатывает отмену заказа на этапе ввода адреса.
    """
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} отменил заказ на этапе ввода адреса.")

    await state.clear()
    await message.answer(
        "❌ Оформление заказа отменено.",
        reply_markup=ReplyKeyboardRemove()
    )
    await message.bot.delete_message(
        chat_id=message.chat.id,
        message_id=message.message_id - 1
    )  # Удаляем сообщение с запросом адреса
    await message.delete()  # Удаляем сообщение "Отмена"

    # Показываем корзину
    user, _ = await sync_to_async(TelegramUser.objects.get_or_create)(
        telegram_id=user_id,
        defaults={"first_name": message.from_user.first_name, "is_active": True}
    )
    items = await get_cart_items(user)
    total = await get_cart_total(user)

    if not items:
        await message.answer(
            "🛒 Ваша корзина пуста.",
            reply_markup=cart_keyboard()
        )
        return

    text = "🛒 Ваша корзина:\n\n"
    for item in items:
        text += f"{item.product.name} × {item.quantity} - {item.product.price * item.quantity} ₽\n"
    text += f"\nИтого: {total} ₽"

    await message.answer(
        text,
        reply_markup=cart_keyboard()
    )

@router.message(OrderStates.WAITING_FOR_ADDRESS)
async def process_address(message: Message, state: FSMContext):
    """
    Обрабатывает введённый адрес доставки.
    """
    user_id = message.from_user.id
    address = message.text
    logger.info(f"Пользователь {user_id} ввёл адрес: {address}")

    try:
        user, _ = await sync_to_async(TelegramUser.objects.get_or_create)(
            telegram_id=user_id,
            defaults={"first_name": message.from_user.first_name, "is_active": True}
        )
        items = await get_cart_items(user)
        total = await get_cart_total(user)

        await state.update_data(address=address)
        await state.set_state(OrderStates.WAITING_FOR_CONFIRMATION)

        text = "📦 Подтверждение заказа:\n\n"
        for item in items:
            text += f"{item.product.name} × {item.quantity} - {item.product.price * item.quantity} ₽\n"
        text += f"\nИтого: {total} ₽\n"
        text += f"Адрес доставки: {address}\n\n"
        text += "Подтвердить заказ?"

        confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Подтвердить", callback_data="confirm_order"),
                InlineKeyboardButton(text="Отмена", callback_data="cancel_order"),
            ]
        ])

        await message.answer(
            text,
            reply_markup=confirm_keyboard
        )
        await message.delete()  # Удаляем сообщение с введённым адресом
        await message.bot.delete_message(
            chat_id=message.chat.id,
            message_id=message.message_id - 1
        )  # Удаляем сообщение с запросом адреса

    except Exception as e:
        logger.error(f"Ошибка при обработке адреса для пользователя {user_id}: {e}")
        await message.answer("❌ Произошла ошибка при обработке адреса")

@router.callback_query(F.data == "confirm_order")
async def confirm_order(callback: CallbackQuery, state: FSMContext):
    """
    Подтверждает заказ и завершает процесс оформления.
    """
    user_id = callback.from_user.id
    logger.info(f"Пользователь {user_id} подтвердил заказ.")

    try:
        user, _ = await sync_to_async(TelegramUser.objects.get_or_create)(
            telegram_id=user_id,
            defaults={"first_name": callback.from_user.first_name, "is_active": True}
        )
        items = await get_cart_items(user)
        data = await state.get_data()
        address = data.get("address")

        # Создаём заказ
        order = await sync_to_async(Order.objects.create)(
            user=user,
            address=address,
            total_price=sum(item.product.price * item.quantity for item in items),
            status="pending"
        )
        for item in items:
            await sync_to_async(order.items.create)(
                product=item.product,
                quantity=item.quantity,
                price=item.product.price
            )
        # Очищаем корзину
        await sync_to_async(CartItem.objects.filter(cart__user=user, is_active=True).delete)()

        await state.clear()
        await callback.message.edit_text(
            "✅ Заказ успешно оформлен! Мы свяжемся с вами для подтверждения.",
            reply_markup=cart_keyboard()
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при подтверждении заказа для пользователя {user_id}: {e}")
        await callback.answer("❌ Произошла ошибка при подтверждении заказа", show_alert=True)

@router.callback_query(F.data == "cancel_order")
async def cancel_order_at_confirmation(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает отмену заказа на этапе подтверждения.
    """
    user_id = callback.from_user.id
    logger.info(f"Пользователь {user_id} отменил заказ на этапе подтверждения.")

    await state.clear()
    await callback.message.edit_text(
        "❌ Оформление заказа отменено.",
        reply_markup=cart_keyboard()
    )
    await callback.answer()

    # Показываем корзину
    user, _ = await sync_to_async(TelegramUser.objects.get_or_create)(
        telegram_id=user_id,
        defaults={"first_name": callback.from_user.first_name, "is_active": True}
    )
    items = await get_cart_items(user)
    total = await get_cart_total(user)

    if not items:
        await callback.message.edit_text(
            "🛒 Ваша корзина пуста.",
            reply_markup=cart_keyboard()
        )
        return

    text = "🛒 Ваша корзина:\n\n"
    for item in items:
        text += f"{item.product.name} × {item.quantity} - {item.product.price * item.quantity} ₽\n"
    text += f"\nИтого: {total} ₽"

    await callback.message.edit_text(
        text,
        reply_markup=cart_keyboard()
    )

@router.callback_query(F.data == "clear_cart")
async def clear_cart(callback: CallbackQuery):
    """
    Очищает корзину пользователя.
    """
    user_id = callback.from_user.id
    logger.info(f"Пользователь {user_id} запросил очистку корзины.")

    try:
        user, _ = await sync_to_async(TelegramUser.objects.get_or_create)(
            telegram_id=user_id,
            defaults={"first_name": callback.from_user.first_name, "is_active": True}
        )
        await sync_to_async(CartItem.objects.filter(cart__user=user, is_active=True).delete)()

        await callback.message.edit_text(
            "🛒 Корзина очищена.",
            reply_markup=cart_keyboard()
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка при очистке корзины для пользователя {user_id}: {e}")
        await callback.answer("❌ Произошла ошибка при очистке корзины", show_alert=True)
