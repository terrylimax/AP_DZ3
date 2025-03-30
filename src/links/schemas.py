import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import Optional

    
class LinkCreate(BaseModel):
    # id записи не указывается, так как генерируется автоматически
    user_id: Optional[uuid.UUID] = None  # для гостей - будет сохраняться как NULL
    original_link: str
    shortened_link: str
    created_at: datetime = datetime.now()
    last_used: datetime = datetime.now()
    custom_alias: bool = False
    expires_at: Optional[datetime] = None
    used_count: int = 1
    
class LinkResponse(BaseModel):
    original_link: str
    shortened_link: str
    last_used: datetime
    custom_alias: Optional[bool] = False