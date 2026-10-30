from typing import Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product


class DuplicateProductError(Exception):
    pass


class ProductRepository(Protocol):
    async def list_latest(self, limit: int) -> list[Product]: ...

    async def get_by_idempotency_key(self, key: str) -> Product | None: ...

    async def add(self, product: Product) -> Product: ...


class SqlProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_latest(self, limit: int) -> list[Product]:
        result = await self._session.scalars(
            select(Product)
            .order_by(Product.created_at.desc(), Product.id.desc())
            .limit(limit)
        )
        return list(result)

    async def get_by_idempotency_key(self, key: str) -> Product | None:
        return await self._session.scalar(
            select(Product).where(Product.idempotency_key == key)
        )

    async def add(self, product: Product) -> Product:
        self._session.add(product)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise DuplicateProductError from exc
        await self._session.refresh(product)
        return product
