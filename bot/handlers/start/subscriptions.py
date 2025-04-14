# bot/handlers/start/subscriptions.py
import logging
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from bot.core.config import SUBSCRIPTION_CHANNEL_ID, SUBSCRIPTION_GROUP_ID, FREE_ACCESS_COMMANDS

logger = logging.getLogger(__name__)

async def check_subscriptions(bot: Bot, user_id: int, command: str = None) -> tuple[bool, str | None]:
    """
    Проверяет подписки пользователя.

    Args:
        bot: Экземпляр бота
        user_id: ID пользователя
        command: Выполняемая команда (если указана)

    Возвращает:
    - (True, None) если подписки есть или команда не требует подписки
    - (False, сообщение_с_требованием) если подписки нет для команды, требующей её
    - (True, None) если проверка не удалась (пропускаем проверку)
    """
    # Если команда в списке свободного доступа, пропускаем проверку
    if command in FREE_ACCESS_COMMANDS:
        logger.debug(f"Команда {command} не требует подписки для пользователя {user_id}")
        return True, None

    try:
        required_subscriptions = []
        
        if SUBSCRIPTION_CHANNEL_ID:
            required_subscriptions.append(("канал", SUBSCRIPTION_CHANNEL_ID))
            
        if SUBSCRIPTION_GROUP_ID and SUBSCRIPTION_GROUP_ID != SUBSCRIPTION_CHANNEL_ID:
            required_subscriptions.append(("группу", SUBSCRIPTION_GROUP_ID))

        if not required_subscriptions:
            logger.debug(f"Подписки не требуются для пользователя {user_id}")
            return True, None

        missing_subs = []
        
        for sub_type, chat_id in required_subscriptions:
            try:
                member = await bot.get_chat_member(chat_id, user_id)
                if member.status in ["left", "kicked"]:
                    chat_id_clean = str(chat_id).lstrip('-100')
                    missing_subs.append(
                        f"- [{sub_type.capitalize()}](https://t.me/c/{chat_id_clean})"
                    )
            except TelegramAPIError as e:
                logger.error(f"Ошибка проверки {sub_type} {chat_id} для пользователя {user_id}: {e}")
                continue

        if missing_subs:
            message = "📢 Для доступа необходимо подписаться на:\n" + "\n".join(missing_subs)
            logger.info(f"Пользователь {user_id} не подписан на: {', '.join(missing_subs)}")
            return False, message
            
        logger.debug(f"Пользователь {user_id} подписан на все необходимые каналы/группы")
        return True, None

    except Exception as e:
        logger.error(f"Ошибка проверки подписок для пользователя {user_id}: {e}", exc_info=True)
        return True, None
