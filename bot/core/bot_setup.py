# File: bot/bot_setup.py
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from bot.core.config import TELEGRAM_BOT_TOKEN, LOGGING_CONFIG

logger = logging.getLogger(__name__)

async def set_bot_commands(bot: Bot):
    """Установка команд бота"""
    commands = [
        BotCommand(command="/start", description="Запустить бота"),
        BotCommand(command="/catalog", description="Открыть каталог"),
        BotCommand(command="/cart", description="Корзина"),
        BotCommand(command="/faq", description="Частые вопросы"),
        BotCommand(command="/profile", description="Мой профиль")
    ]
    await bot.set_my_commands(commands)
    logger.info("Команды бота установлены")

async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    await set_bot_commands(bot)
    logger.info("Бот успешно запущен")

def setup_bot() -> tuple[Bot, Dispatcher]:
    """Инициализация бота и диспетчера"""
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN не найден в .env")
        raise ValueError("TELEGRAM_BOT_TOKEN не найден")

    bot = Bot(
        token=TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher()
    dp.startup.register(on_startup)
    
    # Импорт роутеров внутри функции
    from bot.handlers.start import commands_router, callbacks_router
    from bot.handlers.product import router as product_router
    from bot.handlers.cart import router as cart_router
    from bot.handlers.faq import faq_router
    from bot.handlers.catalog.views import router as catalog_router  # Новый импорт!

    # Регистрация роутеров
    dp.include_routers(
        commands_router,
        callbacks_router,
        product_router,
        cart_router,
        faq_router,
        catalog_router  # Новый роутер!
    )
    logger.info("Все роутеры зарегистрированы")
    
    return bot, dp
