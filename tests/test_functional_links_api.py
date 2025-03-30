import httpx
import uuid
import json
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from src.main import app
from typing import cast
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from unittest.mock import MagicMock
import asyncio
import pytest_asyncio
from src.auth.users import current_active_user, get_optional_current_user
from src.auth.db import get_async_session
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient, ASGITransport
from typing import AsyncGenerator
from config import DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_NAME, TEST_DB_NAME
from sqlalchemy import text

# Фиктивный пользователь для тестов, требующих авторизации
class DummyUser:
    id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    email = "dummy@example.com"

def override_current_active_user():
    return DummyUser()

def override_optional_current_user():
    return DummyUser()

# Настройка тестовой базы данных
TEST_DATABASE_URL = f"postgresql+asyncpg://{DB_USER}@{DB_HOST}:{DB_PORT}/{TEST_DB_NAME}"

@pytest_asyncio.fixture(scope="function")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    yield engine
    await engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def create_drop_test_links_db_and_tables(test_engine):
    from src.links.models import Link
    async with test_engine.begin() as conn:
        await conn.run_sync(Link.metadata.create_all)
    yield test_engine
    async with test_engine.begin() as conn:
        await conn.run_sync(Link.metadata.drop_all)

app.dependency_overrides[current_active_user] = override_current_active_user
app.dependency_overrides[get_optional_current_user] = override_optional_current_user

async def override_get_async_session_override():
    from sqlalchemy.ext.asyncio import async_sessionmaker
    engine = create_async_engine(TEST_DATABASE_URL, echo=True)
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session_maker() as session:
         yield session
    await engine.dispose()

app.dependency_overrides[get_async_session] = override_get_async_session_override

@pytest.fixture
def mock_redis():
    redis_mock = MagicMock()
    return redis_mock

@pytest.mark.asyncio
async def test_database_connection(test_engine, create_drop_test_links_db_and_tables):
    async_session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with async_session_maker() as session:
         result = await session.execute(text("SELECT 1"))
         assert result.scalar_one() == 1

# Тестирование POST /links/shorten
@pytest.mark.asyncio
async def test_shorten_url_success_without_custom_alias(create_drop_test_links_db_and_tables):
    """
    Проверяем успешное создание короткого URL без кастомного alias.
    Ожидаем статус "success" и сгенерированный код длины 6.
    """
    original_link = "https://example1.com/without_alias"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/links/shorten", 
            params={"original_link": original_link}
        )
        assert response.status_code == 200, f"Ожидается статус 200, получено {response.status_code}. Ответ: {response.text}"
        try:
            data = response.json()
        except ValueError:
            pytest.fail(f"Response is not valid JSON: {response.text}")
        
        assert data["status"] == "success"
        assert len(data["short_url"]) == 6

@pytest.mark.asyncio
async def test_shorten_url_success_with_custom_alias(create_drop_test_links_db_and_tables):
    original_link = "https://example.com/with_alias"
    custom_alias = "myalias1"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/links/shorten", 
            params={"original_link": original_link, "custom_alias": custom_alias}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["short_url"] == custom_alias

@pytest.mark.asyncio
async def test_shorten_url_fail_duplicate_original(create_drop_test_links_db_and_tables):
    original_link = "https://example.com/duplicate"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.post("/links/shorten", params={"original_link": original_link, "custom_alias": "unique1"})
        assert res1.status_code == 200
        res2 = await client.post("/links/shorten", params={"original_link": original_link})
        assert res2.status_code == 409
        data = res2.json()
        assert "short_code" in data.get("detail", {}).get("error", "")

@pytest.mark.asyncio
async def test_shorten_url_fail_duplicate_custom_alias(create_drop_test_links_db_and_tables):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.post("/links/shorten", params={"original_link": "https://example.com/first", "custom_alias": "custom1"})
        assert res1.status_code == 200
        res2 = await client.post("/links/shorten", params={"original_link": "https://example.com/second", "custom_alias": "custom1"})
        assert res2.status_code == 409
        data = res2.json()
        assert "Custom alias provided already exists" in data.get("detail", "")

@pytest.mark.asyncio
async def test_search_links_success(create_drop_test_links_db_and_tables):
    original_link = "https://example.com/searchable"
    custom_alias = "search1"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.post("/links/shorten", params={"original_link": original_link, "custom_alias": custom_alias})
        assert res1.status_code == 200
        res2 = await client.get("/links/search", params={"original_url": original_link})
        assert res2.status_code == 200
        data = res2.json()
        assert isinstance(data, list)
        assert data[0]["original_link"] == original_link
        assert data[0]["shortened_link"] == custom_alias

@pytest.mark.asyncio
async def test_search_links_not_found(create_drop_test_links_db_and_tables):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/links/search", params={"original_url": "https://example.com/doesnotexist"})
        assert res.status_code == 404

@pytest.mark.asyncio
async def test_redirect_to_original_success(create_drop_test_links_db_and_tables):
    original_link = "https://example.com/redirect"
    custom_alias = "redir1"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.post("/links/shorten", params={"original_link": original_link, "custom_alias": custom_alias})
        assert res1.status_code == 200
        res2 = await client.get(f"/links/{custom_alias}", follow_redirects=False)
        assert res2.status_code == 307
        assert res2.headers["location"] == original_link

@pytest.mark.asyncio
async def test_update_short_code_success(create_drop_test_links_db_and_tables):
    original_link = "https://example.com/update"
    initial_alias = "initalias"
    new_alias = "newalias"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.post("/links/shorten", params={"original_link": original_link, "custom_alias": initial_alias})
        assert res1.status_code == 200
        res2 = await client.put(f"/links/{initial_alias}", params={"original_url": original_link, "short_code": new_alias})
        assert res2.status_code == 200
        data = res2.json()
        assert data["status"] == "success"
        res3 = await client.get(f"/links/{new_alias}", follow_redirects=False)
        assert res3.status_code == 307
        assert res3.headers["location"] == original_link

@pytest.mark.asyncio
async def test_update_short_code_fail_nonexistent_original(create_drop_test_links_db_and_tables):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.put("/links/nonexistent", params={"original_url": "https://example.com/nonexistent", "short_code": "dummy"})
        assert res.status_code == 404

@pytest.mark.asyncio
async def test_update_short_code_fail_duplicate_alias(create_drop_test_links_db_and_tables):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.post("/links/shorten", params={"original_link": "https://example.com/link1", "custom_alias": "alias1"})
        assert res1.status_code == 200
        res2 = await client.post("/links/shorten", params={"original_link": "https://example.com/link2", "custom_alias": "alias2"})
        assert res2.status_code == 200
        res3 = await client.put("/links/alias1", params={"original_url": "https://example.com/link1", "short_code": "alias2"})
        assert res3.status_code == 409

@pytest.mark.asyncio
async def test_delete_short_code_success(create_drop_test_links_db_and_tables):
    original_link = "https://example.com/delete"
    custom_alias = "todelete"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.post("/links/shorten", params={"original_link": original_link, "custom_alias": custom_alias})
        assert res1.status_code == 200
        res2 = await client.delete(f"/links/{custom_alias}")
        assert res2.status_code == 200
        data = res2.json()
        assert data["status"] == "success"
        res3 = await client.delete(f"/links/{custom_alias}")
        assert res3.status_code == 404

@pytest.mark.asyncio
async def test_get_stats_success(create_drop_test_links_db_and_tables):
    original_link = "https://example.com/stats"
    custom_alias = "stats1"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.post("/links/shorten", params={"original_link": original_link, "custom_alias": custom_alias})
        assert res1.status_code == 200
        for _ in range(3):
            await client.get(f"/links/{custom_alias}", follow_redirects=False)
        res2 = await client.get(f"/links/{custom_alias}/stats")
        assert res2.status_code == 200
        data = res2.json()
        assert data["original_link"] == original_link
        assert "created_at" in data
        assert data["used_count"] >= 3
        assert "last_used" in data

@pytest.mark.asyncio
async def test_shorten_url_with_expiration(create_drop_test_links_db_and_tables):
    original_link = "https://example.com/expire"
    custom_alias = "expire1"
    future_time = (datetime.now() + timedelta(days=1)).replace(microsecond=0)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
         res = await client.post("/links/shorten", params={
             "original_link": original_link,
             "custom_alias": custom_alias,
             "expires_at": future_time.isoformat()
         })
         assert res.status_code == 200
         data = res.json()
         assert data["short_url"] == custom_alias

@pytest.mark.asyncio
async def test_shorten_url_fail_missing_original_link(create_drop_test_links_db_and_tables):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
         res = await client.post("/links/shorten", params={"custom_alias": "missinglink"})
         assert res.status_code == 422
         data = res.json()
         assert "detail" in data
         assert data["detail"][0]["loc"] == ["query", "original_link"]

@pytest.mark.asyncio
async def test_shorten_url_fail_invalid_url(create_drop_test_links_db_and_tables):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
         res = await client.post("/links/shorten", params={"original_link": 1234, "custom_alias": "invalidurl"})
         assert res.status_code == 422

@pytest.mark.asyncio
async def test_shorten_url_fail_null_original_link(create_drop_test_links_db_and_tables):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
         res = await client.post("/links/shorten", json={"original_link": None, "custom_alias": "nullalias"})
         assert res.status_code == 422
         data = res.json()
         assert "detail" in data
         assert data["detail"][0]["loc"] == ["query", "original_link"]
         assert data["detail"][0]["msg"] == "none is not an allowed value"

@pytest.mark.asyncio
async def test_shorten_url_fail_invalid_expiration_date(create_drop_test_links_db_and_tables):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
         res = await client.post("/links/shorten", params={
             "original_link": "https://exampleexampple.com",
             "custom_alias": "invaliddate",
             "expires_at": "not-a-valid-date"
         })
         assert res.status_code == 422
         data = res.json()
         assert "detail" in data
         assert "Input should be a valid datetime or date" in data["detail"][0]["msg"]

@pytest.mark.asyncio
async def test_update_short_code_fail_invalid_short_code(create_drop_test_links_db_and_tables):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
         res = await client.put("/links/invalid!short_code", params={"original_url": "https://example.com", "short_code": "newalias"})
         assert res.status_code == 422
         data = res.json()
         assert "detail" in data
         assert data["detail"][0]["msg"] == "string does not match regex"

@pytest.mark.asyncio
async def test_search_links_fail_empty_original_url(create_drop_test_links_db_and_tables):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
         res = await client.get("/links/search", params={"original_url": ""})
         assert res.status_code == 422
         data = res.json()
         assert "detail" in data
         assert data["detail"][0]["msg"] == "ensure this value has at least 1 characters"