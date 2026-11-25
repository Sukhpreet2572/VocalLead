from collections.abc import Generator
from pathlib import Path

from fastapi import Request
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import ROOT, Settings


class Base(DeclarativeBase):
    pass


def build_engine(settings: Settings) -> Engine:
    url = make_url(settings.database_url.get_secret_value())
    options: dict = {"pool_pre_ping": True}
    if url.drivername == "sqlite":
        if url.database and url.database != ":memory:":
            path = Path(url.database)
            path = path if path.is_absolute() else ROOT / path
            path.parent.mkdir(parents=True, exist_ok=True)
            url = url.set(database=str(path.resolve()))
        options["connect_args"] = {"check_same_thread": False, "timeout": 3}
    else:
        options["connect_args"] = {"connect_timeout": 3}
        options["pool_timeout"] = 3
    return create_engine(url, **options)


def get_session(request: Request) -> Generator[Session, None, None]:
    with request.app.state.session_factory() as session:
        yield session


def database_connected(session: Session) -> bool:
    try:
        session.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
