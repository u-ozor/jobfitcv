# app/api/main.py

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routers import jobs, variants, cover_letters, wizard
from app.api.routers import rewrites, chunk_review, default_cv
from app.api.routers.default_cv import seed_default_rows
from app.core.profile_loader import load_profile
from app.core.experience_loader import load_experience
from app.logging.logging_config import setup_logging
from app.database.session import engine

setup_logging()


def _migrate_db():
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN role_match REAL DEFAULT NULL"))
            conn.commit()
        except Exception:
            pass  # column already exists


_migrate_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_default_rows()
    yield


app = FastAPI(title="jobfitcv", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # lock down to EC2 domain on deploy
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router,          prefix="/jobs",          tags=["jobs"])
app.include_router(variants.router,      prefix="/variants",      tags=["variants"])
app.include_router(rewrites.router,      prefix="/variants",      tags=["rewrites"])
app.include_router(chunk_review.router,  prefix="/variants",      tags=["chunk_review"])
app.include_router(cover_letters.router, prefix="/jobs",          tags=["cover_letters"])
app.include_router(wizard.router,                                  tags=["wizard"])
app.include_router(default_cv.router,    prefix="/default-cv",     tags=["default_cv"])


@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/profile")
def get_profile():
    return load_profile()


@app.get("/experience")
def get_experience():
    return load_experience()
