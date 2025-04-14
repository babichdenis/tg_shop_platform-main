# bot/handlers/start/__init__.py
from .commands import router as commands_router
from .callbacks import router as callbacks_router
from .handlers import router as handlers_router

__all__ = ['commands_router', 'callbacks_router', 'handlers_router']
