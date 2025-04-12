# bot/handlers/cart/states.py
from aiogram.fsm.state import State, StatesGroup

class OrderState(StatesGroup):
    waiting_for_address = State()
    waiting_for_phone = State()
    waiting_for_wishes = State()
    waiting_for_delivery_time = State()
    waiting_for_confirmation = State()
    waiting_for_edit_choice = State()
