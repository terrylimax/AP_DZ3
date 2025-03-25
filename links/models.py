import uuid
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, DateTime, String, Boolean
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from database import engine

Base = declarative_base()

class Link(Base):
    __tablename__ = "links"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    original_link = Column(String, unique=True, nullable=False)
    shortened_link = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    last_used = Column(DateTime, default=datetime.now, nullable=False)
    custom_alias = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=True)
    used_count = Column(Integer, default=1)
    
async def create_links_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Link.metadata.create_all)