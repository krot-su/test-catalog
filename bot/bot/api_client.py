from typing import Any

import aiohttp


class CatalogApiError(Exception):
    pass


class CatalogApi:
    def __init__(self, base_url: str, token: str, session: aiohttp.ClientSession) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._session = session

    async def create_product(
        self, title: str, image: bytes, idempotency_key: str
    ) -> dict[str, Any]:
        form = aiohttp.FormData()
        form.add_field("title", title)
        form.add_field("image", image, filename="photo.jpg", content_type="image/jpeg")
        headers = {"X-Internal-Token": self._token, "Idempotency-Key": idempotency_key}

        async with self._session.post(
            f"{self._base_url}/api/products",
            data=form,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as response:
            if response.status != 201:
                raise CatalogApiError(f"{response.status}: {await response.text()}")
            return await response.json()
