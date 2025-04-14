import asyncio
import logging
import os
import sys
import django

from bot.core.config import TELEGRAM_BOT_TOKEN, LOGGING_CONFIG
from bot.core.bot_setup import setup_bot  

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
logger.info("Запуск bot/main.py")

# Настройка Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_app.config.settings")
logger.info("Инициализация Django")
django.setup()
logger.info("Django инициализирован")

async def main():
    logger.info("Вход в функцию main()")
    try:
        logger.info(f"TELEGRAM_BOT_TOKEN: {'установлен' if TELEGRAM_BOT_TOKEN else 'не установлен'}")
        bot, dp = setup_bot()
        logger.info("Запуск polling")
        await dp.start_polling(bot)
    except Exception as e:
        logger.exception(f"Ошибка при запуске бота: {e}")
        raise
    finally:
        if 'bot' in locals():
            await bot.session.close()
            logger.info("Сессия бота закрыта")

if __name__ == "__main__":
    logger.info("Начало выполнения программы")
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен вручную")
    except Exception as e:
        logger.exception(f"Необработанная ошибка: {e}")
        sys.exit(1)
