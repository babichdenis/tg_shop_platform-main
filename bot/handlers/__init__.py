# File: bot/handlers/__init__.py
from .start import commands_router, callbacks_router
from .product import router as product_router
from .cart import router as cart_router
from .faq import faq_router
# from .categories import router as categories_router

__all__ = [
    'commands_router',
    'callbacks_router',
    'product_router',
    'cart_router',
    'faq_router',
    # 'categories_router'
]
