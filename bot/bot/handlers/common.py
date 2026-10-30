from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.config import Settings
from bot.keyboards import CREATE_PRODUCT_TEXT, admin_keyboard, catalog_keyboard

GREETING = "У меня есть товар"

start_router = Router(name="start")
fallback_router = Router(name="fallback")


@start_router.message(CommandStart())
async def start(message: Message, state: FSMContext, settings: Settings) -> None:
    await state.clear()
    await message.answer(GREETING, reply_markup=catalog_keyboard(settings.webapp_url))
    if message.from_user and message.from_user.id in settings.admin_id_set:
        await message.answer(
            f"Чтобы добавить товар, нажмите «{CREATE_PRODUCT_TEXT}».",
            reply_markup=admin_keyboard(),
        )


@fallback_router.message()
async def any_message(message: Message, settings: Settings) -> None:
    await message.answer(GREETING, reply_markup=catalog_keyboard(settings.webapp_url))
