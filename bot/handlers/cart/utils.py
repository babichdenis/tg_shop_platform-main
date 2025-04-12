# bot/handlers/cart/utils.py
import logging
from decimal import Decimal
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, CallbackQuery, InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.text_decorations import html_decoration as html

from .models import get_cart_items, get_cart_details, get_cart_quantity, get_cart_total
from .keyboards import generate_cart_keyboard
from bot.core.config import CART_ITEMS_PER_PAGE  # Исправляем импорт

logger = logging.getLogger(__name__)

async def show_cart(user, message: Message | CallbackQuery, page: int = 1):
    """
    Показывает корзину пользователю с поддержкой пагинации.

    :param user: Объект TelegramUser.
    :param message: Сообщение или callback-запрос.
    :param page: Текущая страница пагинации.
    """
    items = await get_cart_items(user)

    if not items:
        text = "🛒 Ваша корзина пуста"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
        ])
    else:
        # Получаем данные корзины
        cart_quantity = await get_cart_quantity(user)
        cart_total = await get_cart_total(user)
        items_text, _, first_item_photo = await get_cart_details(items[0].cart.id)

        # Форматируем сумму: проверяем, является ли cart_total целым числом
        formatted_total = f"{int(cart_total)}" if cart_total == int(cart_total) else f"{cart_total:.2f}"

        # Формируем текст корзины
        text = (
            f"{html.bold('Корзина:')}\n\n"
            f"{items_text}\n\n"
            f"{html.bold(f'{formatted_total} ₽')} * {cart_quantity} шт. = {html.bold(f'{formatted_total} ₽')}"
        )

        # Генерируем клавиатуру с пагинацией, передаём cart_quantity и cart_total
        kb = generate_cart_keyboard(
            user,
            items,
            cart_quantity=cart_quantity,  # Добавляем
            cart_total=cart_total,        # Добавляем
            page=page,
            items_per_page=CART_ITEMS_PER_PAGE  # Исправляем на CART_ITEMS_PER_PAGE
        )

    # Отображаем корзину
    try:
        if isinstance(message, Message):
            if items and first_item_photo:
                await message.answer_photo(
                    photo=first_item_photo,
                    caption=text,
                    reply_markup=kb,
                    parse_mode=ParseMode.HTML
                )
            else:
                await message.answer(
                    text,
                    reply_markup=kb,
                    parse_mode=ParseMode.HTML
                )
        else:
            if items and first_item_photo:
                media = InputMediaPhoto(
                    media=first_item_photo,
                    caption=text,
                    parse_mode=ParseMode.HTML
                )
                try:
                    await message.message.edit_media(media=media, reply_markup=kb)
                except TelegramBadRequest:
                    await message.message.delete()
                    await message.message.answer_photo(
                        photo=first_item_photo,
                        caption=text,
                        reply_markup=kb,
                        parse_mode=ParseMode.HTML
                    )
            else:
                try:
                    await message.message.edit_text(
                        text,
                        reply_markup=kb,
                        parse_mode=ParseMode.HTML
                    )
                except TelegramBadRequest:
                    await message.message.delete()
                    await message.message.answer(
                        text,
                        reply_markup=kb,
                        parse_mode=ParseMode.HTML
                    )
            await message.answer()

    except TelegramBadRequest as e:
        logger.error(f"Ошибка при отображении корзины: {e}")
        if isinstance(message, Message):
            await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        else:
            await message.message.delete()
            await message.message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
