# bot/handlers/cart/handlers.py
import os
import logging
import re
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from aiogram.utils.text_decorations import html_decoration as html
from dotenv import load_dotenv

from .models import (
    get_or_create_user, get_cart, get_cart_items, update_cart_item_quantity,
    remove_item_from_cart, clear_cart, create_order, get_cart_details, get_order_details
)
from .keyboards import (
    generate_cart_keyboard, generate_back_keyboard, generate_skip_keyboard,
    generate_confirmation_keyboard, generate_edit_choice_keyboard
)
from .states import OrderState
from .utils import show_cart
from bot.core.config import SUPPORT_TELEGRAM, CART_ITEMS_PER_PAGE
# Загружаем переменные из .env
load_dotenv()
SUPPORT_TELEGRAM = os.getenv("SUPPORT_TELEGRAM")

# Настройка логирования
logger = logging.getLogger(__name__)

router = Router()

# --- Обработчики корзины ---
@router.callback_query(F.data == "cart")
@router.message(F.text == "/cart")
async def handle_cart(request: Message | CallbackQuery, state: FSMContext) -> None:
    """Обработчик кнопки/команды 'Корзина'."""
    user, _ = await get_or_create_user(request.from_user.id)
    logger.info(f"Обработчик корзины вызван пользователем: {user.telegram_id}")
    await state.update_data(cart_page=1)  # Сбрасываем страницу на первую
    await show_cart(user, request, page=1)

@router.callback_query(F.data.startswith("increase_item_"))
async def increase_item(callback: CallbackQuery, state: FSMContext):
    """Увеличивает количество товара в корзине."""
    user, _ = await get_or_create_user(callback.from_user.id)
    product_id = int(callback.data.split("_")[-1])
    
    await update_cart_item_quantity(user, product_id, 1)
    await callback.answer("Количество увеличено")
    
    # Получаем текущую страницу из состояния
    data = await state.get_data()
    page = data.get("cart_page", 1)
    await show_cart(user, callback, page=page)

@router.callback_query(F.data.startswith("decrease_item_"))
async def decrease_item(callback: CallbackQuery, state: FSMContext):
    """Уменьшает количество товара в корзине."""
    user, _ = await get_or_create_user(callback.from_user.id)
    product_id = int(callback.data.split("_")[-1])
    
    await update_cart_item_quantity(user, product_id, -1)
    await callback.answer("Количество уменьшено")
    
    # Получаем текущую страницу из состояния
    data = await state.get_data()
    page = data.get("cart_page", 1)
    await show_cart(user, callback, page=page)

@router.callback_query(F.data.startswith("remove_item_"))
async def remove_item(callback: CallbackQuery, state: FSMContext):
    """Удаляет товар из корзины."""
    user, _ = await get_or_create_user(callback.from_user.id)
    product_id = int(callback.data.split("_")[-1])
    
    await remove_item_from_cart(user, product_id)
    await callback.answer("Товар удалён из корзины")
    
    # Получаем текущую страницу из состояния
    data = await state.get_data()
    page = data.get("cart_page", 1)
    await show_cart(user, callback, page=page)

@router.callback_query(F.data.startswith("cart_page_"))
async def handle_cart_pagination(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает пагинацию в корзине."""
    user, _ = await get_or_create_user(callback.from_user.id)
    page = int(callback.data.split("_")[-1])
    
    # Получаем данные корзины
    cart_items = await get_cart_items(user)
    cart_quantity = await get_cart_quantity(user)
    cart_total = await get_cart_total(user)
    
    # Сохраняем текущую страницу в состоянии
    await state.update_data(cart_page=page)
    
    # Генерируем клавиатуру с пагинацией
    keyboard = generate_cart_keyboard(
        user,
        cart_items,
        cart_quantity=cart_quantity,
        cart_total=cart_total,
        page=page,
        items_per_page=CARТ_ITEMS_PER_PAGE  # Используем константу из bot/core/config.py
    )
    
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "clear_cart")
async def clear_cart_handler(callback: CallbackQuery, state: FSMContext):
    """Очищает корзину."""
    user, _ = await get_or_create_user(callback.from_user.id)
    await clear_cart(user)
    await callback.answer("Корзина очищена")
    
    # Сбрасываем страницу на первую
    await state.update_data(cart_page=1)
    await show_cart(user, callback, page=1)

@router.callback_query(F.data == "checkout")
async def start_checkout(callback: CallbackQuery, state: FSMContext):
    """Начинает процесс оформления заказа."""
    user, _ = await get_or_create_user(callback.from_user.id)
    cart_items = await get_cart_items(user)
    
    if not cart_items:
        await callback.answer("Ваша корзина пуста!", show_alert=True)
        return

    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение при старте оформления заказа: {e}")

    msg = await callback.message.answer(
        "📍 Пожалуйста, укажите адрес доставки:",
        reply_markup=generate_back_keyboard()
    )

    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_address)

# --- Обработчики оформления заказа ---
@router.callback_query(F.data == "back", OrderState.waiting_for_address)
async def back_from_address(callback: CallbackQuery, state: FSMContext):
    """Возвращает пользователя к корзине из шага ввода адреса."""
    user, _ = await get_or_create_user(callback.from_user.id)
    data = await state.get_data()
    page = data.get("cart_page", 1)
    await state.clear()
    await show_cart(user, callback, page=page)

@router.message(OrderState.waiting_for_address)
async def process_address(message: Message, state: FSMContext):
    """Обрабатывает введённый адрес."""
    address = message.text.strip()
    if not address:
        await message.answer("❌ Адрес не может быть пустым. Пожалуйста, введите снова:")
        return

    await state.update_data(address=address)
    
    data = await state.get_data()
    try:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=data.get("message_id"))
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение при обработке адреса: {e}")

    msg = await message.answer(
        "📞 Пожалуйста, укажите ваш номер телефона:",
        reply_markup=generate_back_keyboard()
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_phone)

@router.callback_query(F.data == "back", OrderState.waiting_for_phone)
async def back_from_phone(callback: CallbackQuery, state: FSMContext):
    """Возвращает пользователя к вводу адреса."""
    data = await state.get_data()
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение при возврате к вводу адреса: {e}")

    msg = await callback.message.answer(
        "📍 Пожалуйста, укажите адрес доставки:",
        reply_markup=generate_back_keyboard()
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_address)

@router.message(OrderState.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    """Обрабатывает введённый номер телефона."""
    phone = message.text.strip()
    if not re.match(r'^\+?\d{10,15}$', phone):
        await message.answer("❌ Некорректный номер телефона. Пожалуйста, введите снова:")
        return

    await state.update_data(phone=phone)
    
    data = await state.get_data()
    try:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=data.get("message_id"))
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение при обработке телефона: {e}")

    msg = await message.answer(
        "💬 Укажите пожелания к заказу (или нажмите 'Пропустить'):",
        reply_markup=generate_skip_keyboard()
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_wishes)

@router.callback_query(F.data == "back", OrderState.waiting_for_wishes)
async def back_from_wishes(callback: CallbackQuery, state: FSMContext):
    """Возвращает пользователя к вводу телефона."""
    data = await state.get_data()
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение при возврате к вводу телефона: {e}")

    msg = await callback.message.answer(
        "📞 Пожалуйста, укажите ваш номер телефона:",
        reply_markup=generate_back_keyboard()
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_phone)

@router.message(OrderState.waiting_for_wishes)
@router.callback_query(F.data == "skip", OrderState.waiting_for_wishes)
async def process_wishes(request: Message | CallbackQuery, state: FSMContext):
    """Обрабатывает пожелания к заказу."""
    wishes = request.text.strip() if isinstance(request, Message) else None
    await state.update_data(wishes=wishes)
    
    data = await state.get_data()
    try:
        if isinstance(request, Message):
            await request.bot.delete_message(chat_id=request.chat.id, message_id=data.get("message_id"))
        else:
            await request.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение при обработке пожеланий: {e}")

    msg = await (request.message if isinstance(request, CallbackQuery) else request).answer(
        "⏰ Укажите желаемое время доставки (или нажмите 'Пропустить'):",
        reply_markup=generate_skip_keyboard()
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_delivery_time)

@router.callback_query(F.data == "back", OrderState.waiting_for_delivery_time)
async def back_from_delivery_time(callback: CallbackQuery, state: FSMContext):
    """Возвращает пользователя к вводу пожеланий."""
    data = await state.get_data()
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение при возврате к вводу пожеланий: {e}")

    msg = await callback.message.answer(
        "💬 Укажите пожелания к заказу (или нажмите 'Пропустить'):",
        reply_markup=generate_skip_keyboard()
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_wishes)

@router.message(OrderState.waiting_for_delivery_time)
@router.callback_query(F.data == "skip", OrderState.waiting_for_delivery_time)
async def process_delivery_time(request: Message | CallbackQuery, state: FSMContext):
    """Обрабатывает желаемое время доставки."""
    delivery_time = request.text.strip() if isinstance(request, Message) else None
    await state.update_data(desired_delivery_time=delivery_time)
    
    data = await state.get_data()
    user, _ = await get_or_create_user(request.from_user.id)
    cart = await get_cart(user)
    items_text, total, first_item_photo = await get_cart_details(cart.id)

    text = (
        f"📋 Проверьте данные заказа:\n\n"
        f"📍 Адрес: {html.quote(data.get('address'))}\n"
        f"📞 Телефон: {html.quote(data.get('phone'))}\n"
        f"💬 Пожелания: {html.quote(data.get('wishes')) if data.get('wishes') else 'Нет'}\n"
        f"⏰ Время доставки: {html.quote(delivery_time) if delivery_time else 'Не указано'}\n\n"
        f"🛒 Состав заказа:\n{items_text}\n\n"
        f"💵 Итого: {html.bold(f'{total} ₽')}\n\n"
    )

    try:
        if isinstance(request, Message):
            await request.bot.delete_message(chat_id=request.chat.id, message_id=data.get("message_id"))
        else:
            await request.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение при обработке времени доставки: {e}")

    msg = await (request.message if isinstance(request, CallbackQuery) else request).answer(
        text,
        reply_markup=generate_confirmation_keyboard(total),
        parse_mode=ParseMode.HTML
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_confirmation)

@router.callback_query(F.data == "back", OrderState.waiting_for_confirmation)
async def back_from_confirmation(callback: CallbackQuery, state: FSMContext):
    """Возвращает пользователя к вводу времени доставки."""
    data = await state.get_data()
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение при возврате к вводу времени доставки: {e}")

    msg = await callback.message.answer(
        "⏰ Укажите желаемое время доставки (или нажмите 'Пропустить'):",
        reply_markup=generate_skip_keyboard()
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_delivery_time)

@router.callback_query(F.data == "confirm", OrderState.waiting_for_confirmation)
async def confirm_order(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обрабатывает подтверждение заказа."""
    data = await state.get_data()
    user, _ = await get_or_create_user(callback.from_user.id)

    try:
        order = await create_order(
            user_id=user.telegram_id,
            address=data.get("address"),
            phone=data.get("phone"),
            wishes=data.get("wishes"),
            desired_delivery_time=data.get("desired_delivery_time")
        )

        items_text, total = await get_order_details(order.id)

        user_text = (
            f"✅ Заказ {html.bold(f'#{order.id}')} оформлен!\n\n"
            f"📍 Адрес: {html.quote(data.get('address'))}\n"
            f"📞 Телефон: {html.quote(data.get('phone'))}\n"
            f"💬 Пожелания: {html.quote(data.get('wishes')) if data.get('wishes') else 'Нет'}\n"
            f"⏰ Время доставки: {html.quote(data.get('desired_delivery_time')) if data.get('desired_delivery_time') else 'Не указано'}\n\n"
            f"🛒 Состав заказа:\n{items_text}\n\n"
            f"💵 Итого: {html.bold(f'{total} ₽')}"
        )

        try:
            await callback.message.delete()
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение при подтверждении заказа: {e}")

        await callback.message.answer(
            user_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ В меню", callback_data="main_menu")]
            ]),
            parse_mode=ParseMode.HTML
        )

        if SUPPORT_TELEGRAM and SUPPORT_TELEGRAM.strip():
            admin_text = (
                f"🔔 Новый заказ #{order.id}!\n\n"
                f"👤 Пользователь: {user.telegram_id}\n"
                f"📞 Телефон: {data.get('phone')}\n"
                f"📍 Адрес: {data.get('address')}\n"
                f"🛒 Товары:\n{items_text}\n"
                f"💵 Сумма: {total}₽"
            )
            try:
                await bot.send_message(
                    chat_id=int(SUPPORT_TELEGRAM),
                    text=admin_text,
                    parse_mode=ParseMode.HTML
                )
                logger.info(f"Уведомление о заказе #{order.id} успешно отправлено администратору")
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления администратору: {e}")
        else:
            logger.warning("SUPPORT_TELEGRAM не указан в .env, уведомление администратору не отправлено.")

    except Exception as e:
        logger.error(f"Ошибка создания заказа: {e}")
        await callback.message.answer(
            "❌ Ошибка при оформлении заказа. Пожалуйста, попробуйте снова или обратитесь в поддержку.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ В меню", callback_data="main_menu")]
            ])
        )
    
    await state.clear()

@router.callback_query(F.data == "edit", OrderState.waiting_for_confirmation)
async def edit_order(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает нажатие на 'Изменить'."""
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение при редактировании заказа: {e}")

    msg = await callback.message.answer(
        "Что вы хотите изменить?",
        reply_markup=generate_edit_choice_keyboard()
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_edit_choice)

@router.callback_query(F.data == "back_to_confirmation", OrderState.waiting_for_edit_choice)
async def back_to_confirmation(callback: CallbackQuery, state: FSMContext):
    """Возвращает пользователя к подтверждению заказа."""
    data = await state.get_data()
    user, _ = await get_or_create_user(callback.from_user.id)
    cart = await get_cart(user)
    items_text, total, _ = await get_cart_details(cart.id)

    text = (
        f"📋 Проверьте данные заказа:\n\n"
        f"📍 Адрес: {html.quote(data.get('address'))}\n"
        f"📞 Телефон: {html.quote(data.get('phone'))}\n"
        f"💬 Пожелания: {html.quote(data.get('wishes')) if data.get('wishes') else 'Нет'}\n"
        f"⏰ Время доставки: {html.quote(data.get('desired_delivery_time')) if data.get('desired_delivery_time') else 'Не указано'}\n\n"
        f"🛒 Состав заказа:\n{items_text}\n\n"
        f"💵 Итого: {html.bold(f'{total} ₽')}\n\n"
    )

    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение при возврате к подтверждению заказа: {e}")

    msg = await callback.message.answer(
        text,
        reply_markup=generate_confirmation_keyboard(total),
        parse_mode=ParseMode.HTML
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_confirmation)

@router.callback_query(F.data == "edit_address", OrderState.waiting_for_edit_choice)
async def edit_address(callback: CallbackQuery, state: FSMContext):
    """Позволяет пользователю отредактировать адрес."""
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение при редактировании адреса: {e}")

    msg = await callback.message.answer(
        "📍 Пожалуйста, укажите новый адрес доставки:",
        reply_markup=generate_back_keyboard()
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_address)

@router.callback_query(F.data == "edit_phone", OrderState.waiting_for_edit_choice)
async def edit_phone(callback: CallbackQuery, state: FSMContext):
    """Позволяет пользователю отредактировать номер телефона."""
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение при редактировании телефона: {e}")

    msg = await callback.message.answer(
        "📞 Пожалуйста, укажите ваш новый номер телефона:",
        reply_markup=generate_back_keyboard()
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_phone)

@router.callback_query(F.data == "edit_wishes", OrderState.waiting_for_edit_choice)
async def edit_wishes(callback: CallbackQuery, state: FSMContext):
    """Позволяет пользователю отредактировать пожелания."""
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение при редактировании пожеланий: {e}")

    msg = await callback.message.answer(
        "💬 Укажите новые пожелания к заказу (или нажмите 'Пропустить'):",
        reply_markup=generate_skip_keyboard()
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_wishes)

@router.callback_query(F.data == "edit_delivery_time", OrderState.waiting_for_edit_choice)
async def edit_delivery_time(callback: CallbackQuery, state: FSMContext):
    """Позволяет пользователю отредактировать время доставки."""
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение при редактировании времени доставки: {e}")

    msg = await callback.message.answer(
        "⏰ Укажите новое желаемое время доставки (или нажмите 'Пропустить'):",
        reply_markup=generate_skip_keyboard()
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_delivery_time)
