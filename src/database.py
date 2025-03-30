import os
from dotenv import load_dotenv
load_dotenv()  # Загружаем переменные окружения из файла .env
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from config import DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_NAME, TEST_DB_NAME
from sqlalchemy import create_engine
from contextlib import asynccontextmanager

# Для синхронного подключения используем драйвер psycopg2:
SYNC_DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

synchronized_engine = create_engine(SYNC_DATABASE_URL)
SyncSessionMaker = sessionmaker(bind=synchronized_engine, autocommit=False, autoflush=False)

# Настройка асинхронного движка с параметрами пула соединений
engine = create_async_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600  # Закрываем неактивные соединения, чтобы избежать аварийного разрыва
)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session  # Гарантированное закрытие сессии
        

    
# test_engine = create_async_engine(
#     TEST_DATABASE_URL,
#     pool_size=5,
#     max_overflow=10,
#     pool_pre_ping=True,
#     pool_recycle=3600,  # Аналогичная настройка для тестового движка,
#     echo=True
# )
# test_async_session_maker = async_sessionmaker(test_engine, expire_on_commit=False)