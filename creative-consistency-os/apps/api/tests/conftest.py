import os
from pathlib import Path

os.environ["CCOS_DATABASE_URL"] = "sqlite:///./test_ccos.db"

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app

TEST_DB = Path("test_ccos.db")


@pytest.fixture(autouse=True)
def reset_database():
    engine.dispose()
    TEST_DB.unlink(missing_ok=True)
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()
    TEST_DB.unlink(missing_ok=True)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
