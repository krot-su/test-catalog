from aiogram.fsm.state import State, StatesGroup


class CreateProduct(StatesGroup):
    waiting_for_photo = State()
