import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from logic import settings

from .routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="LinkedIn Content Generator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(router)
