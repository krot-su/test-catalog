from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_product_service, get_session, require_internal_token
from app.schemas import ProductOut
from app.service import ImageTooLargeError, NewProduct, ProductService, UnsupportedImageError

router = APIRouter(prefix="/api")

ServiceDep = Annotated[ProductService, Depends(get_product_service)]


@router.get("/health")
async def health(session: Annotated[AsyncSession, Depends(get_session)]) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.get("/products", response_model=list[ProductOut])
async def list_products(
    service: ServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[ProductOut]:
    return await service.list_products(limit)


@router.post(
    "/products",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_internal_token)],
)
async def create_product(
    service: ServiceDep,
    title: Annotated[str, Form(max_length=200)],
    image: Annotated[UploadFile, File()],
    idempotency_key: Annotated[str | None, Header(max_length=100)] = None,
) -> ProductOut:
    clean_title = title.strip()
    if not clean_title:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Title is empty")

    data = await image.read(service.max_image_bytes + 1)
    try:
        return await service.create_product(
            NewProduct(title=clean_title, image=data, idempotency_key=idempotency_key)
        )
    except ImageTooLargeError:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image is too large"
        ) from None
    except UnsupportedImageError:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only JPEG, PNG or WebP images"
        ) from None
