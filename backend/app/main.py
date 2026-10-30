from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import products
from app.config import get_settings
from app.db import create_engine, create_sessionmaker
from app.storage import create_minio_storage


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    app.state.settings = settings
    app.state.sessionmaker = create_sessionmaker(engine)
    app.state.storage = create_minio_storage(settings)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="Catalog API", lifespan=lifespan)
    app.include_router(products.router)
    return app


app = create_app()
