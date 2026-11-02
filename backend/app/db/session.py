import os
from collections.abc import Generator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.getenv("PET_AGENT_DATABASE_URL", "sqlite:///./pet_agent.db")
MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"
ALEMBIC_CONFIG_PATH = MIGRATIONS_DIR.parent / "alembic.ini"
engine = create_engine(
    DATABASE_URL,
    connect_args=(
        {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
    ),
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db(database_url: str = DATABASE_URL) -> None:
    config = Config(str(ALEMBIC_CONFIG_PATH))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, "head")


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
