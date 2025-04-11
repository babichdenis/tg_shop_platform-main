import logging
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from bot.core.config import SUBSCRIPTION_CHANNEL_ID, SUBSCRIPTION_GROUP_ID

logger = logging.getLogger(__name__)

async def check_subscriptions(bot: Bot, user_id: int) -> str | None:
    """Проверка подписки на канал и/или группу"""
    try:
        is_subscribed = True
        subscription_message = "📢 Для продолжения подпишитесь на:\n"

        if SUBSCRIPTION_CHANNEL_ID:
            channel_member = await bot.get_chat_member(SUBSCRIPTION_CHANNEL_ID, user_id)
            if channel_member.status in ["left", "kicked"]:
                is_subscribed = False
                subscription_message += f"- [Официальный канал](https://t.me/{SUBSCRIPTION_CHANNEL_ID})\n"

        if SUBSCRIPTION_GROUP_ID:
            group_member = await bot.get_chat_member(SUBSCRIPTION_GROUP_ID, user_id)
            if group_member.status in ["left", "kicked"]:
                is_subscribed = False
                subscription_message += f"- [Чат поддержки](https://t.me/{SUBSCRIPTION_GROUP_ID})\n"

        if not is_subscribed:
            logger.warning(f"Пользователь {user_id} не подписан")
            return subscription_message
        return None

    except TelegramAPIError as e:
        logger.error(f"Ошибка проверки подписки для {user_id}: {e}")
        return "⚠️ Не удалось проверить подписку"
