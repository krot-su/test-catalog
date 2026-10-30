from dataclasses import dataclass
from uuid import uuid4

from app.models import Product
from app.repository import DuplicateProductError, ProductRepository
from app.schemas import ProductOut
from app.storage import ImageStorage


class UnsupportedImageError(Exception):
    pass


class ImageTooLargeError(Exception):
    pass


@dataclass(frozen=True)
class NewProduct:
    title: str
    image: bytes
    idempotency_key: str | None = None


_IMAGE_SIGNATURES = (
    (b"\xff\xd8\xff", "jpg", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "png", "image/png"),
)


def detect_image_type(data: bytes) -> tuple[str, str] | None:
    """Returns (extension, content type) by file signature, not by client-declared type."""
    for signature, extension, content_type in _IMAGE_SIGNATURES:
        if data.startswith(signature):
            return extension, content_type
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp", "image/webp"
    return None


class ProductService:
    def __init__(
        self,
        repository: ProductRepository,
        storage: ImageStorage,
        media_base_url: str,
        max_image_bytes: int,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._media_base_url = media_base_url.rstrip("/")
        self._max_image_bytes = max_image_bytes

    @property
    def max_image_bytes(self) -> int:
        return self._max_image_bytes

    async def list_products(self, limit: int) -> list[ProductOut]:
        products = await self._repository.list_latest(limit)
        return [self._to_out(product) for product in products]

    async def create_product(self, new: NewProduct) -> ProductOut:
        if new.idempotency_key:
            existing = await self._repository.get_by_idempotency_key(new.idempotency_key)
            if existing is not None:
                return self._to_out(existing)

        if len(new.image) > self._max_image_bytes:
            raise ImageTooLargeError
        image_type = detect_image_type(new.image)
        if image_type is None:
            raise UnsupportedImageError
        extension, content_type = image_type

        image_key = f"{uuid4().hex}.{extension}"
        await self._storage.put(image_key, new.image, content_type)
        try:
            product = await self._repository.add(
                Product(
                    title=new.title,
                    image_key=image_key,
                    idempotency_key=new.idempotency_key,
                )
            )
        except DuplicateProductError:
            # Concurrent request with the same key won the race.
            await self._storage.delete(image_key)
            existing = await self._repository.get_by_idempotency_key(new.idempotency_key or "")
            if existing is None:
                raise
            return self._to_out(existing)
        except Exception:
            await self._storage.delete(image_key)
            raise
        return self._to_out(product)

    def _to_out(self, product: Product) -> ProductOut:
        return ProductOut(
            id=product.id,
            title=product.title,
            image_url=f"{self._media_base_url}/{product.image_key}",
            created_at=product.created_at,
        )
