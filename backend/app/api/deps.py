import hmac
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repository import SqlProductRepository
from app.service import ProductService


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


def get_product_service(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProductService:
    settings = request.app.state.settings
    return ProductService(
        repository=SqlProductRepository(session),
        storage=request.app.state.storage,
        media_base_url=settings.media_base_url,
        max_image_bytes=settings.max_image_bytes,
    )


def require_internal_token(
    request: Request,
    x_internal_token: Annotated[str | None, Header()] = None,
) -> None:
    expected = request.app.state.settings.internal_api_token
    if not x_internal_token or not hmac.compare_digest(
        x_internal_token.encode(), expected.encode()
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
