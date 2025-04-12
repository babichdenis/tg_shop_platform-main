import logging
from django.contrib import admin
from mptt.admin import DraggableMPTTAdmin
from ..models import Category

logger = logging.getLogger(__name__)

@admin.register(Category)
class CategoryAdmin(DraggableMPTTAdmin):
    list_display = ('tree_actions', 'indented_title', 'created_at', 'is_active')
    list_display_links = ('indented_title',)
    search_fields = ('name',)
    list_filter = ('is_active',)
    actions = ['soft_delete_selected', 'hard_delete_selected']
    delete_selected = None  # Отключаем стандартное действие

    def save_model(self, request, obj, form, change):
        if change:
            logger.info(f'Категория изменена: {obj}')
        else:
            logger.info(f'Создана новая категория: {obj}')
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        logger.info(f'Категория мягко удалена: {obj}')
        obj.soft_delete()

    def soft_delete_selected(self, request, queryset):
        for obj in queryset:
            obj.soft_delete()
        self.message_user(request, "Выбранные категории мягко удалены.")
    soft_delete_selected.short_description = "Мягко удалить выбранные категории"

    def hard_delete_selected(self, request, queryset):
        for obj in queryset:
            logger.info(f'Категория полностью удалена: {obj}')
            obj.delete()
        self.message_user(request, "Выбранные категории полностью удалены.")
    hard_delete_selected.short_description = "Полностью удалить выбранные категории"

    def get_queryset(self, request):
        return Category.objects.all()
