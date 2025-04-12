import logging
from django.contrib import admin
from ..models import Cart, CartItem

logger = logging.getLogger(__name__)

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 1

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'created_at', 'is_active')
    inlines = [CartItemInline]
    actions = ['soft_delete_selected', 'hard_delete_selected']
    delete_selected = None  # Отключаем стандартное действие

    def save_model(self, request, obj, form, change):
        if change:
            logger.info(f'Корзина изменена: {obj}')
        else:
            logger.info(f'Создана новая корзина: {obj}')
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        logger.info(f'Корзина мягко удалена: {obj}')
        obj.soft_delete()

    def soft_delete_selected(self, request, queryset):
        for obj in queryset:
            obj.soft_delete()
        self.message_user(request, "Выбранные корзины мягко удалены.")
    soft_delete_selected.short_description = "Мягко удалить выбранные корзины"

    def hard_delete_selected(self, request, queryset):
        for obj in queryset:
            logger.info(f'Корзина полностью удалена: {obj}')
            obj.delete()
        self.message_user(request, "Выбранные корзины полностью удалены.")
    hard_delete_selected.short_description = "Полностью удалить выбранные корзины"

    def get_queryset(self, request):
        return Cart.objects.all()
