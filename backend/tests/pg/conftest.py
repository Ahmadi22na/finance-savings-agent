"""اختبارات tests/pg/ بتشتغل على PostgreSQL فقط — تنتخطى تلقائيًا على SQLite."""
import pytest


@pytest.fixture(autouse=True)
def _require_postgres(is_postgres):
    if not is_postgres:
        pytest.skip("يحتاج TEST_DATABASE_URL يشير لقاعدة PostgreSQL")
