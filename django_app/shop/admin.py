import logging
from django.contrib import admin
from .admin import (
    CategoryAdmin,
    ProductAdmin,
    FAQAdmin,
    CartAdmin,
    OrderAdmin,
    TelegramUserAdmin,
)

logger = logging.getLogger(__name__)
logger.info('Инициализация admin.py для приложения shop.')

# Глобальная настройка админки
admin.site.site_header = "Админ-панель Telegram-магазина"
admin.site.site_title = "Админ-панель"
admin.site.index_title = "Добро пожаловать в админ-панель"
