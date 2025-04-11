import os
from dotenv import load_dotenv

load_dotenv()

# Общие константы
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUBSCRIPTION_CHANNEL_ID = os.getenv("SUBSCRIPTION_CHANNEL_ID", None)
SUBSCRIPTION_GROUP_ID = os.getenv("SUBSCRIPTION_GROUP_ID", None)

# Поддержка
SUPPORT_TELEGRAM = os.getenv("SUPPORT_TELEGRAM", "@SupportBot")

# Константы для FAQ
FAQ_PER_PAGE = 5  # Количество вопросов FAQ на одной странице
FAQ_SEARCH_PER_PAGE = 5  # Количество результатов поиска FAQ на одной странице

# Логирование
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    "filename": "logs/bot.log",
    "filemode": "a"
}
