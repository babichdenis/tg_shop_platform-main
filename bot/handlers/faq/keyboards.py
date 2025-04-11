import logging
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.core.config import FAQ_PER_PAGE, FAQ_SEARCH_PER_PAGE

logger = logging.getLogger(__name__)

def build_faq_keyboard(faq_items, page: int, total_pages: int):
    """Построение инлайн-клавиатуры для списка FAQ с пагинацией."""
    logger.debug(f"Построение клавиатуры для FAQ страницы {page} из {total_pages}.")
    buttons = []

    # Вычисляем начальный индекс для номеров кнопок
    start_index = (page - 1) * FAQ_PER_PAGE

    # Кнопки номеров вопросов с учётом глобального порядка
    number_buttons = [
        InlineKeyboardButton(text=str(start_index + i + 1), callback_data=f"faq_item_{item.id}")
        for i, item in enumerate(faq_items)
    ]
    if number_buttons:
        buttons.append(number_buttons)
        logger.debug("Добавлены кнопки номеров FAQ.")

    # Пагинация
    pagination_buttons = []
    if total_pages > 1:
        if page > 1:
            pagination_buttons.append(InlineKeyboardButton(text="←", callback_data=f"faq_page_{page - 1}"))
        pagination_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
        if page < total_pages:
            pagination_buttons.append(InlineKeyboardButton(text="→", callback_data=f"faq_page_{page + 1}"))
        buttons.append(pagination_buttons)
        logger.debug("Добавлены кнопки пагинации FAQ.")

    buttons.append([InlineKeyboardButton(text="🔍 Задать вопрос", callback_data="ask_question")])
    buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_search_keyboard(results, indices, page: int, total_pages: int, query: str):
    """Построение инлайн-клавиатуры для результатов поиска FAQ с пагинацией."""
    logger.debug(f"Построение клавиатуры для поиска FAQ по запросу '{query}', страница {page} из {total_pages}.")
    buttons = []

    # Используем глобальные индексы для нумерации кнопок
    number_buttons = [
        InlineKeyboardButton(text=str(index), callback_data=f"faq_item_{item.id}")
        for item, index in zip(results, indices)
    ]
    if number_buttons:
        buttons.append(number_buttons)
        logger.debug("Добавлены кнопки номеров найденных FAQ.")

    encoded_query = query.replace("_", "##")
    pagination_buttons = []
    if total_pages > 1:
        if page > 1:
            pagination_buttons.append(
                InlineKeyboardButton(text="←", callback_data=f"search_page_{page - 1}_{encoded_query}")
            )
        pagination_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
        if page < total_pages:
            pagination_buttons.append(
                InlineKeyboardButton(text="→", callback_data=f"search_page_{page + 1}_{encoded_query}")
            )
        buttons.append(pagination_buttons)
        logger.debug("Добавлены кнопки пагинации для поиска FAQ.")

    buttons.append([InlineKeyboardButton(text="🔙 Назад к FAQ", callback_data="faq")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_to_list_keyboard(page: int):
    """Клавиатура для возврата к списку FAQ."""
    logger.debug(f"Построение клавиатуры для возврата к списку FAQ, страница {page}.")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к списку", callback_data=f"faq_page_{page}")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
    ])
