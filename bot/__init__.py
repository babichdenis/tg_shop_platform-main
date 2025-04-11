import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
logger.info("Загрузка пакета bot")

__all__ = [
    'commands_router',
    'callbacks_router',
    'product_router',
    'cart_router',
    'faq_router',
    'categories_router'
]
