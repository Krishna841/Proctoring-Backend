from pydantic import BaseModel # type: ignore
from typing import Optional, List
from datetime import datetime

class CreateSessionRequest(BaseModel):
    candidate_name: str

class SessionResponse(BaseModel):
    id: str
    candidate_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    video_path: Optional[str] = None

class EventResponse(BaseModel):
    id: str
    event_type: str
    message: Optional[str] = None
    timestamp: datetime

class LogEventRequest(BaseModel):
    event_type: str
    message: Optional[str] = None
    timestamp: Optional[datetime] = None

class SessionWithEventsResponse(BaseModel):
    id: str
    candidate_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    video_path: Optional[str] = None
    events: List[EventResponse]

class ReportResponse(BaseModel):
    candidate_name: str
    session_id: str
    interview_duration_seconds: int
    focus_lost_count: int
    looking_away_count: int
    no_face_segments: int
    multiple_faces_count: int
    phone_detected_count: int
    notes_detected_count: int
    device_detected_count: int
    suspicious_events_count: int
    integrity_score: float
