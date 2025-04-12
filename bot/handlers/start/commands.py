import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

from bot.handlers.start.messages import welcome_message, format_user_profile
from bot.handlers.start.keyboards import main_menu_keyboard, profile_keyboard
from bot.handlers.start.subscriptions import check_subscriptions
from bot.core.config import SUBSCRIPTION_CHANNEL_ID, SUBSCRIPTION_GROUP_ID
from bot.core.utils import get_or_create_user

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text == "/start")
async def start_command(message: Message):
    """Обработчик команды /start с проверкой подписки"""
    user_id = message.from_user.id
    logger.info(f"Получена команда /start от пользователя {user_id}")

    user_data = message.from_user
    user, _ = await get_or_create_user(
        user_id=user_data.id,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        username=user_data.username,
        language_code=user_data.language_code
    )

    # Проверка подписки, если требуется
    if SUBSCRIPTION_CHANNEL_ID or SUBSCRIPTION_GROUP_ID:
        subscription_result = await check_subscription(message.bot, user_id)
        if subscription_result:
            await message.answer(
                subscription_result,
                disable_web_page_preview=True,
                parse_mode="Markdown"
            )
            return

    # Отправка приветственного сообщения
    from bot.handlers.cart.models import get_cart_quantity
    has_cart = await get_cart_quantity(user) > 0
    await message.answer(
        welcome_message(user_data.first_name, has_cart),
        reply_markup=await main_menu_keyboard(user)
    )

@router.message(F.text == "/profile")
async def profile_command(message: Message):
    """Обработчик команды /profile"""
    user_id = message.from_user.id
    logger.info(f"Получена команда /profile от пользователя {user_id}")

    user, _ = await get_or_create_user(
        user_id=user_id,
        first_name=message.from_user.first_name
    )
    
    text = await format_user_profile(user)
    keyboard = await profile_keyboard(user)
    
    try:
        await message.answer(text, reply_markup=keyboard)
    except TelegramBadRequest as e:
        logger.error(f"Ошибка при отправке профиля: {e}")
        await message.answer(text, reply_markup=keyboard)
