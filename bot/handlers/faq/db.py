# File: bot/handlers/faq/db.py
import logging
from asgiref.sync import sync_to_async
from django_app.shop.models import FAQ#, UserQuestion
from bot.core.utils import get_or_create_user

from bot.core.config import FAQ_PER_PAGE, FAQ_SEARCH_PER_PAGE

logger = logging.getLogger(__name__)

@sync_to_async
def get_faq_page(page: int = 1):
    """Получение списка FAQ с пагинацией."""
    faq_page = list(FAQ.objects.all()[(page - 1) * FAQ_PER_PAGE: page * FAQ_PER_PAGE])
    logger.debug(f"Получено {len(faq_page)} FAQ для страницы {page}.")
    return faq_page


@sync_to_async
def get_faq_count():
    """Получение общего количества FAQ."""
    count = FAQ.objects.count()
    logger.debug(f"Общее количество FAQ: {count}.")
    return count


@sync_to_async
def get_faq_item(item_id: int):
    """Получение отдельного FAQ по его ID."""
    try:
        faq_item = FAQ.objects.get(id=item_id)
        logger.debug(f"Получен FAQ с ID {item_id}: {faq_item.question}")
        return faq_item
    except FAQ.DoesNotExist:
        logger.warning(f"FAQ с ID {item_id} не найден.")
        return None


@sync_to_async
def search_faq(query: str, page: int = 1):
    """Поиск FAQ по запросу с учетом регистра, возвращает результаты и их глобальные индексы."""
    logger.debug(f"Поиск FAQ по запросу: '{query}', страница {page}.")
    start = (page - 1) * FAQ_SEARCH_PER_PAGE
    end = start + FAQ_SEARCH_PER_PAGE

    q_lower = query.lower()
    q_capital = q_lower.capitalize()

    qs_lower = FAQ.objects.filter(question__icontains=q_lower)
    qs_capital = FAQ.objects.filter(question__icontains=q_capital)

    combined = (qs_lower | qs_capital).distinct()
    # Получаем все ID вопросов в порядке их появления в базе
    all_ids = list(FAQ.objects.all().values_list('id', flat=True))
    # Получаем результаты поиска
    results = list(combined[start:end])
    # Для каждого результата определяем его глобальный индекс
    indices = [all_ids.index(item.id) + 1 for item in results]
    logger.debug(f"Найдено {len(results)} результатов для запроса '{query}' на странице {page}.")
    return results, indices  # Возвращаем только results и indices


@sync_to_async
def get_search_count(query: str):
    """Получение общего количества результатов поиска по запросу."""
    logger.debug(f"Получение количества результатов поиска для запроса: '{query}'.")
    q_lower = query.lower()
    q_capital = q_lower.capitalize()

    qs_lower = FAQ.objects.filter(question__icontains=q_lower)
    qs_capital = FAQ.objects.filter(question__icontains=q_capital)

    combined = (qs_lower | qs_capital).distinct()
    count = combined.count()
    logger.debug(f"Общее количество результатов поиска для '{query}': {count}.")
    return count


@sync_to_async
def save_user_question(user_id: int, question: str, **user_data):
    """Сохранение вопроса пользователя в базе."""
    user, _ = get_or_create_user(user_id, **user_data)
    user_question = UserQuestion.objects.create(user=user, question=question)
    logger.info(f"Сохранён вопрос от пользователя {user_id}: '{question}'.")
    return user_question
