# bot/handlers/start/handlers.py
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from bot.handlers.start.messages import welcome_message
from bot.handlers.start.keyboards import main_menu_keyboard
from bot.core.utils import get_or_create_user
from bot.handlers.start.subscriptions import check_subscriptions
from bot.core.config import SUBSCRIPTION_CHANNEL_ID, SUBSCRIPTION_GROUP_ID

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery):
    """Возвращает пользователя в главное меню."""
    user_id = callback.from_user.id
    logger.info(f"Пользователь {user_id} возвращается в главное меню.")

    user, _ = await get_or_create_user(user_id)

    # Проверка подписки (для информирования)
    subscription_message = ""
    if SUBSCRIPTION_CHANNEL_ID or SUBSCRIPTION_GROUP_ID:
        subscription_result, message_text = await check_subscriptions(callback.bot, user_id)
        if not subscription_result:
            subscription_message = (
                f"{message_text}\n\n"
                "ℹ️ После подписки вы получите доступ к каталогу, корзине и профилю.\n"
                "Команды /faq и /about доступны без подписки.\n"
            )

    # Формируем приветственное сообщение
    from bot.handlers.cart.models import get_cart_quantity
    has_cart = await get_cart_quantity(user) > 0
    welcome_text = welcome_message(callback.from_user.first_name, has_cart)
    if subscription_message:
        welcome_text += f"\n{subscription_message}"

    try:
        await callback.message.edit_text(
            welcome_text,
            reply_markup=await main_menu_keyboard(callback.bot, user_id),
            disable_web_page_preview=True,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка при возврате в главное меню: {e}")
        await callback.message.delete()
        await callback.message.answer(
            welcome_text,
            reply_markup=await main_menu_keyboard(callback.bot, user_id),
            disable_web_page_preview=True,
            parse_mode="Markdown"
        )
    await callback.answer()
