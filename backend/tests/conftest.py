import pytest
import os

# Force SQLite test database BEFORE any app imports
os.environ["DATABASE_URL"] = "sqlite:///test_signaldach.db"
os.environ["SIGNALDACH_DATABASE_URL"] = "sqlite:///test_signaldach.db"
os.environ["SIGNALDACH_OPENAI_API_KEY"] = ""
os.environ["SIGNALDACH_AUTH_ENABLED"] = "false"

# Override DB_PATH in database module
import app.database as db_module
db_module.DB_PATH = "test_signaldach.db"


@pytest.fixture(autouse=True)
def clean_db():
    """Fresh DB for each test."""
    # Re-point to test DB
    db_module.DB_PATH = "test_signaldach.db"
    db_module.init_db()
    yield
    # cleanup
    try:
        os.remove("test_signaldach.db")
    except OSError:
        pass
    try:
        os.remove("test_signaldach.db-shm")
    except OSError:
        pass
    try:
        os.remove("test_signaldach.db-wal")
    except OSError:
        pass
