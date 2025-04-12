import logging
from django.contrib import admin
from ..models import FAQ

logger = logging.getLogger(__name__)

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('id', 'question', 'is_active')
    actions = ['soft_delete_selected', 'hard_delete_selected']
    delete_selected = None  # Отключаем стандартное действие

    def save_model(self, request, obj, form, change):
        if change:
            logger.info(f'FAQ изменён: {obj}')
        else:
            logger.info(f'Создан новый FAQ: {obj}')
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        logger.info(f'FAQ мягко удалён: {obj}')
        obj.soft_delete()

    def soft_delete_selected(self, request, queryset):
        for obj in queryset:
            obj.soft_delete()
        self.message_user(request, "Выбранные FAQ мягко удалены.")
    soft_delete_selected.short_description = "Мягко удалить выбранные FAQ"

    def hard_delete_selected(self, request, queryset):
        for obj in queryset:
            logger.info(f'FAQ полностью удалён: {obj}')
            obj.delete()
        self.message_user(request, "Выбранные FAQ полностью удалены.")
    hard_delete_selected.short_description = "Полностью удалить выбранные FAQ"

    def get_queryset(self, request):
        return FAQ.objects.all()
