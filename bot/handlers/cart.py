import os
import django
import logging
import re
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from asgiref.sync import sync_to_async
from dotenv import load_dotenv

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup

from aiogram.utils.text_decorations import html_decoration as html

# Загружаем переменные из .env
load_dotenv()
SUPPORT_TELEGRAM = os.getenv("SUPPORT_TELEGRAM")

# Настройка логирования
logger = logging.getLogger(__name__)

router = Router()

# --- Состояния ---

class OrderState(StatesGroup):
    waiting_for_address = State()
    waiting_for_phone = State()
    waiting_for_wishes = State()
    waiting_for_delivery_time = State()
    waiting_for_confirmation = State()
    waiting_for_edit_choice = State()  # Новое состояние для выбора поля редактирования

# Инициализация Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_app.config.settings")
django.setup()

# --- Синхронные функции для работы с Django ORM ---

def _get_or_create_user_sync(tg_id: int):
    from django_app.shop.models import TelegramUser
    return TelegramUser.objects.get_or_create(
        telegram_id=tg_id,
        defaults={'is_active': True}
    )

def _get_cart_sync(user):
    from django_app.shop.models import Cart
    return Cart.objects.get_or_create(
        user=user,
        is_active=True
    )

def _get_cart_items_sync(user):
    from django_app.shop.models import CartItem
    return list(CartItem.objects.filter(
        cart__user=user,
        cart__is_active=True,
        is_active=True
    ).select_related("product").select_related("cart"))

def _remove_item_from_cart_sync(user, product_id):
    from django_app.shop.models import Cart, CartItem
    cart = Cart.objects.get(user=user, is_active=True)
    items = CartItem.objects.filter(cart=cart, product_id=product_id, is_active=True)
    for item in items:
        item.is_active = False
        item.save()
    
    if not CartItem.objects.filter(cart=cart, is_active=True).exists():
        cart.is_active = False
        cart.save()

def _create_order_sync(user_id, address, phone, wishes=None, desired_delivery_time=None):
    from django_app.shop.models import Cart, Order, OrderItem, TelegramUser
    user = TelegramUser.objects.get(telegram_id=user_id)
    cart = Cart.objects.get(user=user, is_active=True)
    
    # Считаем сумму заказа
    total = sum(
        item.product.price * item.quantity 
        for item in cart.items.filter(is_active=True)
    )
    
    # Создаем заказ
    order = Order.objects.create(
        user=user,
        address=address,
        phone=phone,
        wishes=wishes,
        desired_delivery_time=desired_delivery_time,
        total=total
    )
    
    # Переносим товары в заказ
    for cart_item in cart.items.filter(is_active=True):
        OrderItem.objects.create(
            order=order,
            product=cart_item.product,
            quantity=cart_item.quantity
        )
    
    # Деактивируем корзину
    cart.is_active = False
    cart.save()
    
    return order

def _get_cart_quantity_sync(user):
    from django_app.shop.models import Cart
    cart = Cart.objects.filter(user=user, is_active=True).first()
    if cart:
        return sum(item.quantity for item in cart.items.filter(is_active=True))
    return 0

def _get_cart_total_sync(user):
    from django_app.shop.models import Cart
    cart = Cart.objects.filter(user=user, is_active=True).first()
    if cart:
        return sum(
            item.product.price * item.quantity 
            for item in cart.items.filter(is_active=True)
        )
    return 0

def _get_cart_details_sync(cart_id):
    from django_app.shop.models import Cart, CartItem
    cart = Cart.objects.get(id=cart_id)
    items = CartItem.objects.filter(cart=cart, is_active=True).select_related('product')
    items_text = "\n".join(
        f"• {html.quote(item.product.name)} - {item.quantity} шт. × {html.quote(str(item.product.price))}₽"
        for item in items
    )
    total = sum(item.product.price * item.quantity for item in items)
    return items_text, total

def _get_order_details_sync(order_id):
    from django_app.shop.models import OrderItem
    items = OrderItem.objects.filter(order_id=order_id).select_related('product')
    items_text = "\n".join(
        f"• {html.quote(item.product.name)} - {item.quantity} шт. × {html.quote(str(item.product.price))}₽"
        for item in items
    )
    total = sum(item.product.price * item.quantity for item in items)
    return items_text, total

# --- Асинхронные обертки для синхронных функций ---

@sync_to_async
def get_or_create_user(tg_id: int):
    return _get_or_create_user_sync(tg_id)

@sync_to_async
def get_cart(user):
    return _get_cart_sync(user)

@sync_to_async
def get_cart_items(user):
    return _get_cart_items_sync(user)

@sync_to_async
def remove_item_from_cart(user, product_id):
    return _remove_item_from_cart_sync(user, product_id)

@sync_to_async
def create_order(user_id, address, phone, wishes=None, desired_delivery_time=None):
    return _create_order_sync(user_id, address, phone, wishes, desired_delivery_time)

@sync_to_async
def get_cart_quantity(user):
    return _get_cart_quantity_sync(user)

@sync_to_async
def get_cart_total(user):
    return _get_cart_total_sync(user)

@sync_to_async
def get_cart_details(cart_id):
    return _get_cart_details_sync(cart_id)

@sync_to_async
def get_order_details(order_id):
    return _get_order_details_sync(order_id)

# --- Генерация клавиатур ---

def generate_cart_keyboard(items):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"❌ {item.product.name} x{item.quantity}",
                callback_data=f"remove_item_{item.product.id}"
            )
        ]
        for item in items
    ])

    if items:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout")
        ])

    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="<-- Назад", callback_data="main_menu")
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

def generate_confirmation_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm"),
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

# --- Обработчики ---

async def show_cart(user, message: Message | CallbackQuery):
    items = await get_cart_items(user)

    if not items:
        text = "🛒 Ваша корзина пуста"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="<-- Назад", callback_data="main_menu")]
        ])

        if isinstance(message, Message):
            await message.answer(text, reply_markup=kb)
        else:
            await message.message.edit_text(text, reply_markup=kb)
        return

    items_text, total = await get_cart_details(items[0].cart.id)
    text = (
        html.bold("🛒 Ваша корзина:") + "\n\n" +
        items_text +
        "\n\n" +
        html.bold(f"Итого: {total} ₽")
    )

    kb = generate_cart_keyboard(items)
    
    try:
        if isinstance(message, Message):
            await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        else:
            await message.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except TelegramBadRequest:
        await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "cart")
@router.message(F.text == "/cart")
async def handle_cart(request: Message | CallbackQuery) -> None:
    """
    Обработчик кнопки/команды "Корзина".
    """
    user, _ = await get_or_create_user(request.from_user.id)
    logger.info(f"Обработчик корзины вызван пользователем: {user.telegram_id}")
    
    items = await get_cart_items(user)

    if not items:
        text = "🛒 Ваша корзина пуста"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="<-- Назад", callback_data="main_menu")]
        ])
        
        if isinstance(request, Message):
            await request.answer(text, reply_markup=kb)
        else:
            try:
                await request.message.edit_text(text, reply_markup=kb)
            except TelegramBadRequest:
                await request.message.answer(text, reply_markup=kb)
        return

    total = sum(item.product.price * item.quantity for item in items)
    text = (
        html.bold("🛒 Ваша корзина:") + "\n\n" +
        "\n".join(
            f"• {html.quote(item.product.name)} - {item.quantity} шт. × {html.quote(str(item.product.price))}₽"
            for item in items
        ) +
        "\n\n" +
        html.bold(f"Итого: {total} ₽")
    )

    kb = generate_cart_keyboard(items)
    
    try:
        if isinstance(request, Message):
            await request.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        else:
            try:
                await request.message.edit_text(
                    text,
                    reply_markup=kb,
                    parse_mode=ParseMode.HTML
                )
            except TelegramBadRequest as e:
                if "message is not modified" not in str(e):
                    await request.message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Ошибка при отображении корзины: {e}")
        await request.answer("❌ Произошла ошибка при отображении корзины")

@router.callback_query(F.data.startswith("remove_item_"))
async def remove_item(callback: CallbackQuery):
    user, _ = await get_or_create_user(callback.from_user.id)
    product_id = int(callback.data.split("_")[-1])
    
    await remove_item_from_cart(user, product_id)
    await callback.answer("Товар удалён из корзины")
    await show_cart(user, callback)

@router.callback_query(F.data == "checkout")
async def start_checkout(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.message.delete()
    except:
        pass

    msg = await callback.message.answer(
        "📍 Пожалуйста, укажите адрес доставки:",
        reply_markup=generate_back_keyboard()
    )

    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_address)

@router.callback_query(F.data == "back", OrderState.waiting_for_address)
async def back_from_address(callback: CallbackQuery, state: FSMContext):
    """
    Возвращает пользователя к корзине из шага ввода адреса.
    """
    await state.clear()  # Сбрасываем состояние, так как это первый шаг
    user, _ = await get_or_create_user(callback.from_user.id)
    await show_cart(user, callback)

@router.message(OrderState.waiting_for_address)
async def process_address(message: Message, state: FSMContext):
    await state.update_data(address=message.text.strip())
    
    # Удаляем предыдущее сообщение
    data = await state.get_data()
    try:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=data.get("message_id"))
    except:
        pass

    msg = await message.answer(
        "📞 Пожалуйста, укажите ваш номер телефона:",
        reply_markup=generate_back_keyboard()
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_phone)

@router.callback_query(F.data == "back", OrderState.waiting_for_phone)
async def back_from_phone(callback: CallbackQuery, state: FSMContext):
    """
    Возвращает пользователя к вводу адреса из шага ввода телефона.
    """
    data = await state.get_data()
    try:
        await callback.message.delete()
    except:
        pass

    msg = await callback.message.answer(
        "📍 Пожалуйста, укажите адрес доставки:",
        reply_markup=generate_back_keyboard()
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_address)

@router.message(OrderState.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    if not re.match(r'^\+?\d{10,15}$', message.text.strip()):
        await message.answer("❌ Некорректный номер телефона. Пожалуйста, введите снова:")
        return

    await state.update_data(phone=message.text.strip())
    
    # Удаляем предыдущее сообщение
    data = await state.get_data()
    try:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=data.get("message_id"))
    except:
        pass

    msg = await message.answer(
        "💬 Укажите пожелания к заказу (или нажмите 'Пропустить'):",
        reply_markup=generate_skip_keyboard()
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_wishes)

@router.callback_query(F.data == "back", OrderState.waiting_for_wishes)
async def back_from_wishes(callback: CallbackQuery, state: FSMContext):
    """
    Возвращает пользователя к вводу телефона из шага ввода пожеланий.
    """
    data = await state.get_data()
    try:
        await callback.message.delete()
    except:
        pass

    msg = await callback.message.answer(
        "📞 Пожалуйста, укажите ваш номер телефона:",
        reply_markup=generate_back_keyboard()
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_phone)

@router.message(OrderState.waiting_for_wishes)
@router.callback_query(F.data == "skip", OrderState.waiting_for_wishes)
async def process_wishes(request: Message | CallbackQuery, state: FSMContext):
    wishes = request.text.strip() if isinstance(request, Message) else None
    await state.update_data(wishes=wishes)
    
    # Удаляем предыдущее сообщение
    data = await state.get_data()
    try:
        if isinstance(request, Message):
            await request.bot.delete_message(chat_id=request.chat.id, message_id=data.get("message_id"))
        else:
            await request.message.delete()
    except:
        pass

    msg = await (request.message if isinstance(request, CallbackQuery) else request).answer(
        "⏰ Укажите желаемое время доставки (или нажмите 'Пропустить'):",
        reply_markup=generate_skip_keyboard()
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_delivery_time)

@router.callback_query(F.data == "back", OrderState.waiting_for_delivery_time)
async def back_from_delivery_time(callback: CallbackQuery, state: FSMContext):
    """
    Возвращает пользователя к вводу пожеланий из шага ввода времени доставки.
    """
    data = await state.get_data()
    try:
        await callback.message.delete()
    except:
        pass

    msg = await callback.message.answer(
        "💬 Укажите пожелания к заказу (или нажмите 'Пропустить'):",
        reply_markup=generate_skip_keyboard()
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_wishes)

@router.message(OrderState.waiting_for_delivery_time)
@router.callback_query(F.data == "skip", OrderState.waiting_for_delivery_time)
async def process_delivery_time(request: Message | CallbackQuery, state: FSMContext):
    delivery_time = request.text.strip() if isinstance(request, Message) else None
    await state.update_data(desired_delivery_time=delivery_time)
    
    # Получаем данные для подтверждения
    data = await state.get_data()
    user, _ = await get_or_create_user(request.from_user.id)
    cart, _ = await get_cart(user)
    items_text, total = await get_cart_details(cart.id)

    text = (
        f"📋 Проверьте данные заказа:\n\n"
        f"📍 Адрес: {html.quote(data.get('address'))}\n"
        f"📞 Телефон: {html.quote(data.get('phone'))}\n"
        f"💬 Пожелания: {html.quote(data.get('wishes')) if data.get('wishes') else 'Нет'}\n"
        f"⏰ Время доставки: {html.quote(delivery_time) if delivery_time else 'Не указано'}\n\n"
        f"🛒 Состав заказа:\n{items_text}\n\n"
        f"💵 Итого: {html.bold(f'{total} ₽')}\n\n"
        f"Всё верно?"
    )

    # Удаляем предыдущее сообщение
    try:
        if isinstance(request, Message):
            await request.bot.delete_message(chat_id=request.chat.id, message_id=data.get("message_id"))
        else:
            await request.message.delete()
    except:
        pass

    msg = await (request.message if isinstance(request, CallbackQuery) else request).answer(
        text,
        reply_markup=generate_confirmation_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_confirmation)

@router.callback_query(F.data == "back", OrderState.waiting_for_confirmation)
async def back_from_confirmation(callback: CallbackQuery, state: FSMContext):
    """
    Возвращает пользователя к вводу времени доставки из шага подтверждения.
    """
    data = await state.get_data()
    try:
        await callback.message.delete()
    except:
        pass

    msg = await callback.message.answer(
        "⏰ Укажите желаемое время доставки (или нажмите 'Пропустить'):",
        reply_markup=generate_skip_keyboard()
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_delivery_time)

@router.callback_query(F.data == "confirm", OrderState.waiting_for_confirmation)
async def confirm_order(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Обрабатывает подтверждение заказа.
    """
    data = await state.get_data()
    user, _ = await get_or_create_user(callback.from_user.id)

    try:
        # Создаем заказ
        order = await create_order(
            user_id=user.telegram_id,
            address=data.get("address"),
            phone=data.get("phone"),
            wishes=data.get("wishes"),
            desired_delivery_time=data.get("desired_delivery_time")
        )

        # Получаем детали заказа
        items_text, total = await get_order_details(order.id)

        # Формируем сообщение для пользователя
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
        except:
            pass

        await callback.message.answer(
            user_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ В меню", callback_data="main_menu")]
            ]),
            parse_mode=ParseMode.HTML
        )

        # Отправляем уведомление администратору
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
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления администратору: {e}")
        else:
            logger.warning("SUPPORT_TELEGRAM не указан в .env, уведомление администратору не отправлено.")

    except Exception as e:
        logger.error(f"Ошибка создания заказа: {e}")
        await callback.message.answer(
            "❌ Ошибка при оформлении заказа",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ В меню", callback_data="main_menu")]
            ]))
    
    await state.clear()

@router.callback_query(F.data == "edit", OrderState.waiting_for_confirmation)
async def edit_order(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие на "Изменить", показывая пользователю варианты редактирования.
    """
    try:
        await callback.message.delete()
    except:
        pass

    msg = await callback.message.answer(
        "Что вы хотите изменить?",
        reply_markup=generate_edit_choice_keyboard()
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_edit_choice)

@router.callback_query(F.data == "back_to_confirmation", OrderState.waiting_for_edit_choice)
async def back_to_confirmation(callback: CallbackQuery, state: FSMContext):
    """
    Возвращает пользователя к подтверждению заказа из меню редактирования.
    """
    data = await state.get_data()
    user, _ = await get_or_create_user(callback.from_user.id)
    cart, _ = await get_cart(user)
    items_text, total = await get_cart_details(cart.id)

    text = (
        f"📋 Проверьте данные заказа:\n\n"
        f"📍 Адрес: {html.quote(data.get('address'))}\n"
        f"📞 Телефон: {html.quote(data.get('phone'))}\n"
        f"💬 Пожелания: {html.quote(data.get('wishes')) if data.get('wishes') else 'Нет'}\n"
        f"⏰ Время доставки: {html.quote(data.get('desired_delivery_time')) if data.get('desired_delivery_time') else 'Не указано'}\n\n"
        f"🛒 Состав заказа:\n{items_text}\n\n"
        f"💵 Итого: {html.bold(f'{total} ₽')}\n\n"
        f"Всё верно?"
    )

    try:
        await callback.message.delete()
    except:
        pass

    msg = await callback.message.answer(
        text,
        reply_markup=generate_confirmation_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_confirmation)

@router.callback_query(F.data == "edit_address", OrderState.waiting_for_edit_choice)
async def edit_address(callback: CallbackQuery, state: FSMContext):
    """
    Позволяет пользователю отредактировать адрес.
    """
    try:
        await callback.message.delete()
    except:
        pass

    msg = await callback.message.answer(
        "📍 Пожалуйста, укажите новый адрес доставки:",
        reply_markup=generate_back_keyboard()
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_address)

@router.callback_query(F.data == "edit_phone", OrderState.waiting_for_edit_choice)
async def edit_phone(callback: CallbackQuery, state: FSMContext):
    """
    Позволяет пользователю отредактировать номер телефона.
    """
    try:
        await callback.message.delete()
    except:
        pass

    msg = await callback.message.answer(
        "📞 Пожалуйста, укажите ваш новый номер телефона:",
        reply_markup=generate_back_keyboard()
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_phone)

@router.callback_query(F.data == "edit_wishes", OrderState.waiting_for_edit_choice)
async def edit_wishes(callback: CallbackQuery, state: FSMContext):
    """
    Позволяет пользователю отредактировать пожелания.
    """
    try:
        await callback.message.delete()
    except:
        pass

    msg = await callback.message.answer(
        "💬 Укажите новые пожелания к заказу (или нажмите 'Пропустить'):",
        reply_markup=generate_skip_keyboard()
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_wishes)

@router.callback_query(F.data == "edit_delivery_time", OrderState.waiting_for_edit_choice)
async def edit_delivery_time(callback: CallbackQuery, state: FSMContext):
    """
    Позволяет пользователю отредактировать время доставки.
    """
    try:
        await callback.message.delete()
    except:
        pass

    msg = await callback.message.answer(
        "⏰ Укажите новое желаемое время доставки (или нажмите 'Пропустить'):",
        reply_markup=generate_skip_keyboard()
    )
    await state.update_data(message_id=msg.message_id)
    await state.set_state(OrderState.waiting_for_delivery_time)
