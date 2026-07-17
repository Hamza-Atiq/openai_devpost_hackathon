from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.deployment.runtime import database_engine, run_migrations, run_retention_cleanup


async def _cleanup_loop() -> None:
    interval = max(60, int(os.environ.get("CRICKOPS_RETENTION_INTERVAL_SECONDS", "3600")))
    engine = database_engine()
    try:
        run_migrations(engine)
        while True:
            await asyncio.to_thread(run_retention_cleanup, engine)
            await asyncio.sleep(interval)
    finally:
        engine.dispose()


@asynccontextmanager
async def lifespan(_application: FastAPI):
    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


app = FastAPI(title="CrickOps retention worker", lifespan=lifespan)


@app.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok", "process": "retention-worker"}
