import html
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.api_client import CatalogApi, CatalogApiError
from bot.config import Settings
from bot.keyboards import CREATE_PRODUCT_TEXT, catalog_keyboard
from bot.states import CreateProduct

log = logging.getLogger(__name__)

MAX_TITLE_LENGTH = 200
ASK_FOR_PRODUCT = (
    "Пришлите одним сообщением фото товара и его название в подписи к фото.\n"
    "Отмена — /cancel"
)


def create_admin_router(admin_ids: frozenset[int]) -> Router:
    router = Router(name="admin")
    router.message.filter(F.from_user.id.in_(admin_ids))

    @router.message(Command("create"))
    @router.message(F.text == CREATE_PRODUCT_TEXT)
    async def start_creation(message: Message, state: FSMContext) -> None:
        await state.set_state(CreateProduct.waiting_for_photo)
        await message.answer(ASK_FOR_PRODUCT)

    @router.message(CreateProduct.waiting_for_photo, Command("cancel"))
    async def cancel(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Добавление товара отменено.")

    @router.message(CreateProduct.waiting_for_photo, F.photo)
    async def receive_product(
        message: Message,
        state: FSMContext,
        bot: Bot,
        api: CatalogApi,
        settings: Settings,
    ) -> None:
        title = (message.caption or "").strip()
        if not title:
            await message.answer("Добавьте название товара в подпись к фото и отправьте ещё раз.")
            return
        if len(title) > MAX_TITLE_LENGTH:
            await message.answer(f"Название длиннее {MAX_TITLE_LENGTH} символов, сократите его.")
            return

        photo = await bot.download(message.photo[-1])
        try:
            product = await api.create_product(
                title=title,
                image=photo.read(),
                idempotency_key=f"tg:{message.chat.id}:{message.message_id}",
            )
        except CatalogApiError:
            log.exception("Failed to create product")
            await message.answer("Не удалось сохранить товар. Попробуйте отправить ещё раз.")
            return

        await state.clear()
        await message.answer(
            f"Товар «{html.escape(product['title'])}» добавлен в каталог.",
            reply_markup=catalog_keyboard(settings.webapp_url),
        )

    @router.message(CreateProduct.waiting_for_photo)
    async def wrong_content(message: Message) -> None:
        await message.answer(ASK_FOR_PRODUCT)

    return router
