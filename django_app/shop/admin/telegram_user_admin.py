import logging
from django.contrib import admin
from ..models import TelegramUser
from .base import BaseAdmin  # Импортируем BaseAdmin

logger = logging.getLogger(__name__)

@admin.register(TelegramUser)
class TelegramUserAdmin(BaseAdmin):
    list_display = ('telegram_id', 'first_name_colored', 'username', 'created_at', 'is_active')
    search_fields = ('telegram_id', 'username')
    readonly_fields = ('created_at', 'last_activity')
    list_filter = ('is_active',)

    def first_name_colored(self, obj):
        return self.name_colored(obj)
    first_name_colored.short_description = 'Имя'

    def save_model(self, request, obj, form, change):
        if change:
            logger.info(f'Пользователь Telegram изменён: {obj}')
        else:
            logger.info(f'Создан новый пользователь Telegram: {obj}')
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        return TelegramUser.objects.filter(is_active=True)
