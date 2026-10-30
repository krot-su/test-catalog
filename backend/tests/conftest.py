import os
from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("S3_ENDPOINT", "localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY", "test")
os.environ.setdefault("S3_SECRET_KEY", "test-secret")
os.environ.setdefault("INTERNAL_API_TOKEN", "test-token")

from app.api.deps import get_product_service  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Product  # noqa: E402
from app.repository import DuplicateProductError  # noqa: E402
from app.service import ProductService  # noqa: E402

JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 64
MAX_IMAGE_BYTES = 1024


class FakeRepository:
    def __init__(self) -> None:
        self.products: list[Product] = []

    async def list_latest(self, limit: int) -> list[Product]:
        return sorted(self.products, key=lambda p: (p.created_at, p.id), reverse=True)[:limit]

    async def get_by_idempotency_key(self, key: str) -> Product | None:
        return next((p for p in self.products if p.idempotency_key == key), None)

    async def add(self, product: Product) -> Product:
        if product.idempotency_key and await self.get_by_idempotency_key(product.idempotency_key):
            raise DuplicateProductError
        product.id = len(self.products) + 1
        product.created_at = datetime.now(timezone.utc)
        self.products.append(product)
        return product


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def client(storage: FakeStorage) -> Iterator[TestClient]:
    repository = FakeRepository()
    app.dependency_overrides[get_product_service] = lambda: ProductService(
        repository, storage, "/media", MAX_IMAGE_BYTES
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
