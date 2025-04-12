# django_app/shop/admin/__init__.py
from .category_admin import CategoryAdmin
from .product_admin import ProductAdmin
from .faq_admin import FAQAdmin
from .cart_admin import CartAdmin
from .order_admin import OrderAdmin
from .telegram_user_admin import TelegramUserAdmin

__all__ = [
    'CategoryAdmin',
    'ProductAdmin',
    'FAQAdmin',
    'CartAdmin',
    'OrderAdmin',
    'TelegramUserAdmin',
]
