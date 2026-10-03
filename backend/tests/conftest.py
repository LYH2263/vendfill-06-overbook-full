import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def database():
    """每用例一个全新内存库：建表 + 种子数据，返回会话工厂。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.database import Base
    from app.services.seed import seed_if_empty

    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    seed_if_empty(db)
    db.close()
    yield TestingSessionLocal
    engine.dispose()


@pytest.fixture()
def client(database):
    """TestClient 与 db_session 走同一内存库；不进 lifespan，避免碰默认 Postgres。"""
    from app.database import get_db
    from app.main import app

    def override_get_db():
        db = database()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def db_session(database):
    db = database()
    try:
        yield db
    finally:
        db.close()
