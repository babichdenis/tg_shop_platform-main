import logging
from django.contrib import admin
from django.urls import path
from django.http import HttpResponse, HttpResponseRedirect
from ..models import Order, OrderItem
from ..tasks import export_orders_to_excel

logger = logging.getLogger(__name__)

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'created_at', 'status_display', 'total', 'is_active')
    search_fields = ('user__username',)
    list_filter = ('status', 'is_active')
    inlines = [OrderItemInline]
    actions = ['soft_delete_selected', 'hard_delete_selected', 'export_to_excel']
    delete_selected = None  # Отключаем стандартное действие

    def status_display(self, obj):
        return obj.get_status_display()
    status_display.short_description = "Статус"

    def export_to_excel(self, request, queryset):
        file_path = export_orders_to_excel(queryset=queryset)
        if file_path:
            with open(file_path, 'rb') as excel_file:
                response = HttpResponse(
                    excel_file.read(),
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                response['Content-Disposition'] = 'attachment; filename="orders_export.xlsx"'
                return response
        else:
            self.message_user(request, "Ошибка при экспорте заказов.", level='error')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/admin/shop/order/'))

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'export-excel/',
                self.admin_site.admin_view(self.export_excel_view),
                name='order-export-excel'
            ),
        ]
        return custom_urls + urls

    def export_excel_view(self, request):
        file_path = export_orders_to_excel()
        if file_path:
            with open(file_path, 'rb') as excel_file:
                response = HttpResponse(
                    excel_file.read(),
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                response['Content-Disposition'] = 'attachment; filename="orders_export.xlsx"'
                return response
        else:
            self.message_user(request, "Ошибка при экспорте заказов.", level='error')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/admin/shop/order/'))

    def save_model(self, request, obj, form, change):
        if change:
            logger.info(f'Заказ изменён: {obj}')
        else:
            logger.info(f'Создан новый заказ: {obj}')
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        logger.info(f'Заказ мягко удалён: {obj}')
        obj.soft_delete()

    def soft_delete_selected(self, request, queryset):
        for obj in queryset:
            obj.soft_delete()
        self.message_user(request, "Выбранные заказы мягко удалены.")
    soft_delete_selected.short_description = "Мягко удалить выбранные заказы"

    def hard_delete_selected(self, request, queryset):
        for obj in queryset:
            logger.info(f'Заказ полностью удалён: {obj}')
            obj.delete()
        self.message_user(request, "Выбранные заказы полностью удалены.")
    hard_delete_selected.short_description = "Полностью удалить выбранные заказы"

    def get_queryset(self, request):
        return Order.objects.all()

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_export_button'] = True
        return super().changelist_view(request, extra_context=extra_context)
