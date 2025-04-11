import logging
from asgiref.sync import sync_to_async
from django_app.shop.models import TelegramUser

logger = logging.getLogger(__name__)

@sync_to_async(thread_sensitive=True)
def get_or_create_user(user_id: int, **kwargs) -> tuple[TelegramUser, bool]:
    """
    Получение пользователя по его Telegram ID или создание нового, если он не существует.
    
    Args:
        user_id (int): Telegram ID пользователя
        **kwargs: Дополнительные данные (first_name, last_name, username, language_code)
    
    Returns:
        tuple[TelegramUser, bool]: Объект пользователя и флаг создания (True если создан)
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
