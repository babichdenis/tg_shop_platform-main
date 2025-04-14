import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.markdown import hbold, hunderline
from aiogram.filters import StateFilter
from aiogram.exceptions import TelegramBadRequest

from bot.core.config import FAQ_PER_PAGE, FAQ_SEARCH_PER_PAGE, SUPPORT_TELEGRAM
from .db import get_faq_page, get_faq_count, get_faq_item, search_faq, get_search_count
from .keyboards import build_faq_keyboard, build_search_keyboard, back_to_list_keyboard

router = Router()
logger = logging.getLogger(__name__)

class FAQStates(StatesGroup):
    browsing = State()
    waiting_question = State()
    viewing_item = State()
    searching = State()


async def edit_or_resend_message(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup):
    """Безопасное редактирование сообщения или отправка нового в случае ошибки."""
    try:
        await callback.message.edit_text(text=text, reply_markup=markup)
        logger.debug("Сообщение успешно отредактировано как текст.")
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e).lower():
            logger.error(f"Ошибка при редактировании текста: {e}")
            try:
                await callback.message.edit_caption(caption=text, reply_markup=markup)
                logger.debug("Сообщение успешно отредактировано как подпись.")
            except TelegramBadRequest as e:
                logger.error(f"Ошибка при редактировании подписи: {e}")
                await callback.message.delete()
                await callback.message.answer(text=text, reply_markup=markup)
                logger.info("Новое сообщение отправлено после удаления старого.")


@router.callback_query(F.data == "faq")
async def show_faq(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Пользователь {callback.from_user.id} запросил FAQ.")
    # Очищаем состояние и удаляем старое сообщение с результатами поиска, если оно есть
    data = await state.get_data()
    search_message_id = data.get('search_message_id')
    if search_message_id:
        try:
            await callback.message.bot.delete_message(
                chat_id=callback.message.chat.id,
                message_id=search_message_id
            )
            logger.debug(f"Удалено старое сообщение с результатами поиска: {search_message_id}.")
        except TelegramBadRequest as e:
            logger.warning(f"Не удалось удалить старое сообщение {search_message_id}: {e}")
    
    await state.set_state(FAQStates.browsing)
    await state.update_data(current_page=1, search_message_id=None)
    await show_faq_page(callback, 1)


async def show_faq_page(callback: CallbackQuery, page: int):
    logger.debug(f"Отображение страницы FAQ {page}.")
    faq_items = await get_faq_page(page)
    total_count = await get_faq_count()
    total_pages = max(1, (total_count - 1) // FAQ_PER_PAGE + 1)
    page = max(1, min(page, total_pages))

    start_index = (page - 1) * FAQ_PER_PAGE
    text = "❓ Часто задаваемые вопросы:\n\n"
    if faq_items:
        text += "\n".join(f"{start_index + i + 1}. {item.question}" for i, item in enumerate(faq_items))
    else:
        text = "❌ В базе пока нет вопросов\n"

    if faq_items:
        markup = build_faq_keyboard(faq_items, page, total_pages)
    else:
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
        ])
        logger.debug("FAQ пуст, добавлена кнопка возврата в главное меню.")

    await edit_or_resend_message(callback, text, markup)
    await callback.answer()
    logger.info(f"Страница FAQ {page} отображена.")


@router.callback_query(F.data.startswith("faq_page_"))
async def faq_pagination(callback: CallbackQuery, state: FSMContext):
    try:
        page = int(callback.data.split("_")[-1])
        logger.debug(f"Пагинация FAQ на страницу {page}.")
    except (ValueError, IndexError) as e:
        logger.error(f"Неверный формат данных для пагинации FAQ: {callback.data} - {e}")
        await callback.answer("Некорректные данные для пагинации.", show_alert=True)
        return

    await state.update_data(current_page=page)
    await show_faq_page(callback, page)


@router.callback_query(F.data.startswith("faq_item_"))
async def show_faq_item(callback: CallbackQuery, state: FSMContext):
    try:
        item_id = int(callback.data.split("_")[-1])
        logger.debug(f"Запрос на отображение FAQ с ID {item_id}.")
    except (ValueError, IndexError) as e:
        logger.error(f"Неверный формат данных для отображения FAQ: {callback.data} - {e}")
        await callback.answer("Некорректные данные для отображения FAQ.", show_alert=True)
        return

    faq_item = await get_faq_item(item_id)
    if not faq_item:
        logger.warning(f"FAQ с ID {item_id} не найден.")
        await callback.answer("⚠️ Вопрос не найден!", show_alert=True)
        return

    data = await state.get_data()
    current_page = data.get('current_page', 1)

    text = (
        f"{hunderline('Вопрос:')}\n{faq_item.question}\n\n"
        f"{hunderline('Ответ:')}\n{faq_item.answer}"
    )

    await edit_or_resend_message(callback, text, back_to_list_keyboard(current_page))
    await callback.answer()
    logger.info(f"FAQ с ID {item_id} отображен пользователю {callback.from_user.id}.")


@router.callback_query(F.data == "ask_question")
async def ask_question_handler(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Пользователь {callback.from_user.id} инициировал задачу вопроса.")
    await state.set_state(FAQStates.waiting_question)
    await edit_or_resend_message(
        callback,
        "✍️ Введите ваш вопрос текстом:",
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="faq")]
        ])
    )
    await callback.answer()


@router.message(F.text, StateFilter(FAQStates.waiting_question))
async def process_question(message: Message, state: FSMContext):
    query = message.text.strip()
    logger.info(f"Пользователь {message.from_user.id} задал вопрос: '{query}'.")
    await state.set_state(FAQStates.searching)
    await state.update_data(search_query=query, search_page=1)
    await show_search_results(message, state, query, 1)


async def show_search_results(message: Message, state: FSMContext, query: str, page: int):
    logger.debug(f"Отображение результатов поиска для запроса '{query}', страница {page}.")
    await state.update_data(search_query=query, search_page=page)

    decoded_query = query.replace("##", "_")
    results, indices = await search_faq(decoded_query, page)
    total_count = await get_search_count(decoded_query)
    total_pages = max(1, (total_count - 1) // FAQ_SEARCH_PER_PAGE + 1)
    page = max(1, min(page, total_pages))

    text = f"🔍 Результаты поиска по запросу '{decoded_query}':\n\n"
    if results:
        text += "\n".join(f"{index}. {item.question}" for item, index in zip(results, indices))
        markup = build_search_keyboard(results, indices, page, total_pages, decoded_query)
    else:
        # Формируем сообщение для администратора
        user_info = (
            f"Новый вопрос от пользователя:\n"
            f"ID: {message.from_user.id}\n"
            f"Имя: {message.from_user.first_name} {message.from_user.last_name or ''}\n"
            f"Username: @{message.from_user.username or 'нет'}\n"
            f"Вопрос: {decoded_query}"
        )
        try:
            if SUPPORT_TELEGRAM:
                await message.bot.send_message(
                    chat_id=SUPPORT_TELEGRAM,
                    text=user_info
                )
                logger.info(f"Вопрос '{decoded_query}' отправлен администратору в чат {SUPPORT_TELEGRAM}.")
            else:
                logger.warning("SUPPORT_TELEGRAM не указан, вопрос не отправлен администратору.")
        except TelegramBadRequest as e:
            logger.error(f"Не удалось отправить вопрос администратору: {e}")

        text += f"❌ Ничего не найдено\nВаш вопрос отправлен администратору. Обратитесь в поддержку: {SUPPORT_TELEGRAM}"
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к FAQ", callback_data="faq")]
        ])
        logger.debug("Поиск не дал результатов, вопрос отправлен администратору.")

    # Удаляем сообщение с запросом пользователя
    try:
        await message.delete()
        logger.debug("Сообщение с запросом пользователя удалено.")
    except TelegramBadRequest as e:
        logger.warning(f"Не удалось удалить сообщение с запросом: {e}")

    # Проверяем, есть ли сохранённый search_message_id
    data = await state.get_data()
    search_message_id = data.get('search_message_id')

    if search_message_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=search_message_id,
                text=text,
                reply_markup=markup
            )
            logger.debug("Сообщение с результатами поиска успешно отредактировано.")
        except TelegramBadRequest as e:
            logger.error(f"Ошибка при редактировании сообщения с результатами поиска: {e}")
            try:
                await message.bot.delete_message(
                    chat_id=message.chat.id,
                    message_id=search_message_id
                )
                logger.debug(f"Удалено старое сообщение с результатами поиска: {search_message_id}.")
            except TelegramBadRequest as e:
                logger.warning(f"Не удалось удалить старое сообщение {search_message_id}: {e}")
            new_msg = await message.answer(text, reply_markup=markup)
            await state.update_data(search_message_id=new_msg.message_id)
            logger.info("Новое сообщение с результатами поиска отправлено после ошибки редактирования.")
    else:
        new_msg = await message.answer(text, reply_markup=markup)
        await state.update_data(search_message_id=new_msg.message_id)
        logger.info("Новое сообщение с результатами поиска отправлено.")


@router.callback_query(F.data.startswith("search_page_"))
async def search_pagination(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Пользователь {callback.from_user.id} запросил пагинацию поиска.")
    try:
        parts = callback.data.split("_")
        if len(parts) < 4:
            raise ValueError("Invalid callback data format")
        page = int(parts[2])
        query = "_".join(parts[3:]).replace("##", "_")
        logger.debug(f"Пагинация поиска FAQ на страницу {page} для запроса '{query}'.")
    except (ValueError, IndexError) as e:
        logger.error(f"Неверный формат данных для пагинации поиска FAQ: {callback.data} - {e}")
        await callback.answer("❌ Некорректные данные для пагинации поиска.", show_alert=True)
        return

    await show_search_results(callback.message, state, query, page)
    await callback.answer()
    logger.info(f"Пагинация поиска FAQ на страницу {page} завершена.")


@router.message(F.text == "/faq")
async def faq_command(message: Message, state: FSMContext) -> None:
    """
    Обработчик команды /faq.
    """
    try:
        user_id = message.from_user.id
        logger.info(f"Пользователь {user_id} вызвал команду /faq.")

        # Устанавливаем состояние и начальную страницу
        await state.set_state(FAQStates.browsing)
        await state.update_data(current_page=1, search_message_id=None)

        # Получаем FAQ для первой страницы
        faq_items = await get_faq_page(page=1)
        total_count = await get_faq_count()
        total_pages = max(1, (total_count - 1) // FAQ_PER_PAGE + 1)

        # Формируем текст
        start_index = 0  # Первая страница, индекс начинается с 0
        text = "❓ Часто задаваемые вопросы:\n\n"
        if faq_items:
            text += "\n".join(f"{start_index + i + 1}. {item.question}" for i, item in enumerate(faq_items))
        else:
            text = "❌ В базе пока нет вопросов\n"

        # Формируем клавиатуру
        if faq_items:
            markup = build_faq_keyboard(faq_items, page=1, total_pages=total_pages)
        else:
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
            ])
            logger.debug("FAQ пуст, добавлена кнопка возврата в главное меню.")

        # Отправляем сообщение
        await message.answer(
            text,
            reply_markup=markup,
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Ошибка при выполнении команды /faq: {e}")
        await message.answer("❌ Произошла ошибка при открытии FAQ")
