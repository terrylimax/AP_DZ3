# import asyncio
# import pytest
# import pytest_asyncio
# from src.database import test_engine
# from src.links.models import create_drop_test_links_db_and_tables

# @pytest_asyncio.fixture(scope="function", autouse=True)
# async def setup_test_database():
#     # Перед запуском всех тестов – создаем таблицы в тестовой базе данных:
#     await create_test_links_db_and_tables()
#     yield
#     # После завершения всех тестов – очищаем базу (удаляем таблицы):
#     await drop_test_links_db_and_tables()