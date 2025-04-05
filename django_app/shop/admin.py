import logging
from django.contrib import admin
from django.utils.html import format_html
from mptt.admin import MPTTModelAdmin, DraggableMPTTAdmin
from .models import Category, Product, FAQ, Cart, CartItem, Order, OrderItem, TelegramUser

logger = logging.getLogger(__name__)
logger.info('Инициализация admin.py для приложения shop.')

# Глобальный JavaScript для клика по строке
CLICKABLE_ROW_JS = """
<script type="text/javascript">
(function($) {
    $(document).ready(function() {
        $('.results tr').each(function() {
            var $row = $(this);
            var link = $row.find('th a').attr('href');
            if (link) {
                $row.css('cursor', 'pointer');
                $row.click(function(e) {
                    if (!$(e.target).is('a') && !$(e.target).is('input')) {
                        window.location.href = link;
                    }
                });
            }
        });
    });
})(django.jQuery);
</script>
"""

@admin.register(Category)
class CategoryAdmin(DraggableMPTTAdmin):
    list_display = ('tree_actions', 'indented_title', 'created_at', 'is_active')
    list_display_links = ('indented_title',)
    search_fields = ('name',)
    list_filter = ('is_active',)
    actions = ['soft_delete_selected', 'hard_delete_selected']

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

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['extra_js'] = CLICKABLE_ROW_JS
        return super().changelist_view(request, extra_context=extra_context)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'category', 'price', 'created_at', 'is_active')
    search_fields = ('name', 'description')
    list_filter = ('category', 'is_active')
    actions = ['soft_delete_selected', 'hard_delete_selected']

    def save_model(self, request, obj, form, change):
        if change:
            logger.info(f'Товар изменён: {obj}')
        else:
            logger.info(f'Создан новый товар: {obj}')
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        logger.info(f'Товар мягко удалён: {obj}')
        obj.soft_delete()

    def soft_delete_selected(self, request, queryset):
        for obj in queryset:
            obj.soft_delete()
        self.message_user(request, "Выбранные товары мягко удалены.")
    soft_delete_selected.short_description = "Мягко удалить выбранные товары"

    def hard_delete_selected(self, request, queryset):
        for obj in queryset:
            logger.info(f'Товар полностью удалён: {obj}')
            obj.delete()
        self.message_user(request, "Выбранные товары полностью удалены.")
    hard_delete_selected.short_description = "Полностью удалить выбранные товары"

    def get_queryset(self, request):
        return Product.objects.all()

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['extra_js'] = CLICKABLE_ROW_JS
        return super().changelist_view(request, extra_context=extra_context)

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('id', 'question', 'is_active')
    actions = ['soft_delete_selected', 'hard_delete_selected']

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

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['extra_js'] = CLICKABLE_ROW_JS
        return super().changelist_view(request, extra_context=extra_context)

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 1

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'created_at', 'is_active')
    inlines = [CartItemInline]
    actions = ['soft_delete_selected', 'hard_delete_selected']

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

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['extra_js'] = CLICKABLE_ROW_JS
        return super().changelist_view(request, extra_context=extra_context)

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'created_at', 'is_paid', 'total', 'is_active')
    search_fields = ('user__username',)
    inlines = [OrderItemInline]
    actions = ['soft_delete_selected', 'hard_delete_selected']

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
        extra_context['extra_js'] = CLICKABLE_ROW_JS
        return super().changelist_view(request, extra_context=extra_context)

@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'first_name', 'username', 'created_at', 'is_active')
    search_fields = ('telegram_id', 'username')
    readonly_fields = ('created_at', 'last_activity')
    actions = ['soft_delete_selected', 'hard_delete_selected']

    def save_model(self, request, obj, form, change):
        if change:
            logger.info(f'Пользователь Telegram изменён: {obj}')
        else:
            logger.info(f'Создан новый пользователь Telegram: {obj}')
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        logger.info(f'Пользователь Telegram мягко удалён: {obj}')
        obj.soft_delete()

    def soft_delete_selected(self, request, queryset):
        for obj in queryset:
            obj.soft_delete()
        self.message_user(request, "Выбранные пользователи мягко удалены.")
    soft_delete_selected.short_description = "Мягко удалить выбранных пользователей"

    def hard_delete_selected(self, request, queryset):
        for obj in queryset:
            logger.info(f'Пользователь Telegram полностью удалён: {obj}')
            obj.delete()
        self.message_user(request, "Выбранные пользователи полностью удалены.")
    hard_delete_selected.short_description = "Полностью удалить выбранных пользователей"

    def get_queryset(self, request):
        return TelegramUser.objects.all()

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['extra_js'] = CLICKABLE_ROW_JS
        return super().changelist_view(request, extra_context=extra_context)

# Глобальная настройка админки
admin.site.site_header = "Админ-панель Telegram-магазина"
admin.site.site_title = "Админ-панель"
admin.site.index_title = "Добро пожаловать в админ-панель"
