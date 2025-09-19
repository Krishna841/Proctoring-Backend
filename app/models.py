from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Session(BaseModel):
    id: Optional[str] = None
    candidate_name: str
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    video_path: Optional[str] = None


class Event(BaseModel):
    id: Optional[str] = None
    session_id: str
    event_type: str
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
