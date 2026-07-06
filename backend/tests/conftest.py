import os
os.environ["DATABASE_URL"] = "sqlite:///test_temp.db"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
get_settings().worker_enabled = False
get_settings().embedding_enabled = False

from app.database import Base, get_db
from app.main import app


# Import models to register them with Base.metadata

import os
from pathlib import Path

TEST_DATABASE_URL = "sqlite:///test_temp.db"


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    # Clean up test database file
    db_path = Path("test_temp.db")
    if db_path.exists():
        try:
            os.remove(db_path)
        except Exception:
            pass


@pytest.fixture(autouse=True)
def clean_db(engine):
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def db(engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
