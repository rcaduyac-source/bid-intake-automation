from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import api.routes as routes_mod
from api.routes import router
from config import get_settings
from core.db import init_databases
from core.gmail import gmail_poll_loop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_databases()
    routes_mod.SERVER_STARTED = datetime.utcnow()
    stop = asyncio.Event()
    poller = asyncio.create_task(gmail_poll_loop(stop))
    logger.info("Bid intake API ready (ai_mode=%s)", settings.ai_mode)
    try:
        yield
    finally:
        stop.set()
        poller.cancel()
        try:
            await poller
        except asyncio.CancelledError:
            pass


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Byrdson Bid Intake", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
