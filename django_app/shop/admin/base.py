from django.contrib import admin
from django.shortcuts import render
from django.contrib import messages
from django.utils.html import format_html
import logging

logger = logging.getLogger(__name__)

class BaseAdmin(admin.ModelAdmin):
    actions = ['deactivate_selected', 'restore_selected']
    delete_selected = None

    def name_colored(self, obj):
        color = 'grey' if hasattr(obj, 'is_active') and not obj.is_active else 'black'
        return format_html('<span style="color: {};">{}</span>', color, str(obj))
    name_colored.short_description = 'Название'

    def deactivate_selected(self, request, queryset):
        updated = 0
        for obj in queryset:
            if hasattr(obj, 'soft_delete'):
                obj.soft_delete()
                updated += 1
        self.message_user(request, f"Деактивировано {updated} объектов.")
    deactivate_selected.short_description = "Деактивировать выбранные объекты"

    def restore_selected(self, request, queryset):
        if 'confirm' in request.POST:
            updated = 0
            for obj in queryset:
                if hasattr(obj, 'is_active'):
                    logger.info(f'Объект восстановлен: {obj}')
                    obj.is_active = True
                    obj.save()
                    updated += 1
            self.message_user(request, f"Восстановлено {updated} объектов.")
            return None

        context = {
            'title': 'Подтверждение восстановления',
            'queryset': queryset,
            'action': 'restore_selected',
            'opts': self.model._meta,
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
        }
        return render(request, 'admin/confirm_restore.html', context)
    restore_selected.short_description = "Восстановить выбранные объекты"

    def delete_model(self, request, obj):
        logger.info(f'Объект мягко удалён: {obj}')
        if hasattr(obj, 'soft_delete'):
            obj.soft_delete()
        else:
            obj.delete()
