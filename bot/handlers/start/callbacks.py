import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from bot.handlers.start.messages import welcome_message, format_user_profile
from bot.handlers.start.keyboards import main_menu_keyboard, profile_keyboard, price_list_keyboard
from bot.core.utils import get_or_create_user
from bot.handlers.cart.models import get_cart_quantity, get_cart_total

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    user, _ = await get_or_create_user(
        user_id=callback.from_user.id,
        first_name=callback.from_user.first_name
    )
    has_cart = await get_cart_quantity(user) > 0
    
    try:
        await callback.message.edit_text(
            welcome_message(callback.from_user.first_name, has_cart),
            reply_markup=await main_menu_keyboard(user)
        )
    except TelegramBadRequest:
        await callback.message.answer(
            welcome_message(callback.from_user.first_name, has_cart),
            reply_markup=await main_menu_keyboard(user)
        )
    await callback.answer()

@router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    """Показ профиля"""
    user, _ = await get_or_create_user(
        user_id=callback.from_user.id,
        first_name=callback.from_user.first_name
    )
    text = await format_user_profile(user)
    keyboard = await profile_keyboard(user)
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("price_list_"))
async def show_price_list(callback: CallbackQuery):
    """Показ прайс-листа"""
    page = int(callback.data.split("_")[-1])
    user, _ = await get_or_create_user(
        user_id=callback.from_user.id,
        first_name=callback.from_user.first_name
    )
    
    from .messages import get_price_list
    price_list_text, total_pages = await get_price_list(page)
    
    try:
        await callback.message.edit_text(
            price_list_text,
            reply_markup=await price_list_keyboard(user, page, total_pages),
            parse_mode="Markdown"
        )
    except TelegramBadRequest:
        await callback.message.answer(
            price_list_text,
            reply_markup=await price_list_keyboard(user, page, total_pages),
            parse_mode="Markdown"
        )
    await callback.answer()
