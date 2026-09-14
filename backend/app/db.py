from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db_models import Base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./waitlist.db")


def _create_engine(url: str) -> Engine:
    if not url.startswith("sqlite"):
        return create_engine(url)
    # SQLite connections are single-threaded by default; FastAPI runs sync
    # routes in a threadpool, so a connection may be reused from a
    # different thread than the one that opened it.
    connect_args = {"check_same_thread": False}
    if ":memory:" in url:
        # An in-memory database only exists on its one open connection, so
        # every session must share that same connection instead of the
        # pool handing out a fresh (empty) database per checkout.
        return create_engine(url, connect_args=connect_args, poolclass=StaticPool)
    return create_engine(url, connect_args=connect_args)


engine = _create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)
