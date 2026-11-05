"""SakayApp API entry point.                               (IMPERATIVE PARADIGM)

On startup: load the network from PostgreSQL and assert it into Prolog.
Run from backend/:  uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import services
from .routers import network, trips

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    services.reload_network()
    yield


app = FastAPI(title="SakayApp API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(network.router)
app.include_router(trips.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    net = services.planner().network
    return {"status": "ok", "stops": len(net.stops), "routes": len(net.routes)}
