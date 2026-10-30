from fastapi.testclient import TestClient

from tests.conftest import JPEG_BYTES, MAX_IMAGE_BYTES, FakeStorage

AUTH = {"X-Internal-Token": "test-token"}


def create(client: TestClient, title: str = "Кружка", image: bytes = JPEG_BYTES, headers=None):
    return client.post(
        "/api/products",
        data={"title": title},
        files={"image": ("photo.jpg", image, "image/jpeg")},
        headers=headers if headers is not None else AUTH,
    )


def test_catalog_is_empty_initially(client: TestClient) -> None:
    response = client.get("/api/products")

    assert response.status_code == 200
    assert response.json() == []


def test_created_product_appears_in_catalog(client: TestClient, storage: FakeStorage) -> None:
    created = create(client, title="  Кружка  ")

    assert created.status_code == 201
    body = created.json()
    assert body["title"] == "Кружка"
    assert body["image_url"].startswith("/media/") and body["image_url"].endswith(".jpg")
    assert len(storage.objects) == 1
    assert [p["id"] for p in client.get("/api/products").json()] == [body["id"]]


def test_create_requires_internal_token(client: TestClient) -> None:
    assert create(client, headers={}).status_code == 401
    assert create(client, headers={"X-Internal-Token": "wrong"}).status_code == 401


def test_same_idempotency_key_creates_product_once(
    client: TestClient, storage: FakeStorage
) -> None:
    headers = {**AUTH, "Idempotency-Key": "tg:1:100"}

    first = create(client, headers=headers)
    second = create(client, headers=headers)

    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert len(client.get("/api/products").json()) == 1
    assert len(storage.objects) == 1


def test_rejects_file_that_is_not_an_image(client: TestClient, storage: FakeStorage) -> None:
    response = create(client, image=b"<script>alert(1)</script>")

    assert response.status_code == 415
    assert storage.objects == {}


def test_rejects_too_large_image(client: TestClient) -> None:
    response = create(client, image=JPEG_BYTES + b"\x00" * MAX_IMAGE_BYTES)

    assert response.status_code == 413


def test_rejects_blank_title(client: TestClient) -> None:
    assert create(client, title="   ").status_code == 422


def test_limit_is_bounded(client: TestClient) -> None:
    assert client.get("/api/products?limit=0").status_code == 422
    assert client.get("/api/products?limit=101").status_code == 422
