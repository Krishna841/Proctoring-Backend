import uuid
from datetime import datetime
from pathlib import Path
from typing import List
import shutil
import os

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse

from .database import sessions_collection, events_collection
from .models import Session, Event
from .schemas import (
    CreateSessionRequest,
    SessionResponse,
    SessionWithEventsResponse,
    LogEventRequest,
    EventResponse,
    ReportResponse,
    ImportVideoRequest,
)
from .report import (
    summarize_events,
    compute_integrity_score,
    write_html_report,
    write_csv_report,
    build_html_report_content,
    build_csv_report_content,
)
from .storage import get_storage, LocalStorage

# Storage paths
DATA_DIR = Path("data")
VIDEO_DIR = DATA_DIR / "videos"
REPORT_DIR = DATA_DIR / "reports"
VIDEO_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)
storage = get_storage(VIDEO_DIR, REPORT_DIR)

app = FastAPI(title="Proctoring Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if isinstance(storage, LocalStorage):
    app.mount("/videos", StaticFiles(directory=str(VIDEO_DIR), html=False), name="videos")
    app.mount("/reports", StaticFiles(directory=str(REPORT_DIR), html=False), name="reports")


@app.post("/sessions", response_model=SessionResponse)
async def create_session(payload: CreateSessionRequest):
    session_id = str(uuid.uuid4())
    session_data = Session(
        id=session_id,
        candidate_name=payload.candidate_name,
        start_time=datetime.utcnow(),
    )

    # Store with Mongo _id as our string UUID
    session_doc = {
        "_id": session_id,
        "candidate_name": session_data.candidate_name,
        "start_time": session_data.start_time,
        "end_time": session_data.end_time,
        "video_path": session_data.video_path,
    }
    await sessions_collection.insert_one(session_doc)

    return SessionResponse(
        id=session_id,
        candidate_name=session_data.candidate_name,
        start_time=session_data.start_time,
        end_time=session_data.end_time,
        video_path=session_data.video_path,
    )


@app.get("/sessions", response_model=List[SessionResponse])
async def list_sessions():
    cursor = sessions_collection.find().sort("start_time", -1)
    sessions = []
    async for doc in cursor:
        sessions.append(SessionResponse(
            id=str(doc["_id"]),
            candidate_name=doc["candidate_name"],
            start_time=doc["start_time"],
            end_time=doc.get("end_time"),
            video_path=doc.get("video_path"),
        ))
    return sessions


@app.get("/sessions/{session_id}", response_model=SessionWithEventsResponse)
async def get_session(session_id: str):
    session_doc = await sessions_collection.find_one({"_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get events for this session
    events_cursor = events_collection.find({"session_id": session_id}).sort("timestamp", 1)
    events = []
    async for event_doc in events_cursor:
        events.append(EventResponse(
            id=str(event_doc["_id"]),
            event_type=event_doc["event_type"],
            message=event_doc.get("message"),
            timestamp=event_doc["timestamp"],
        ))

    return SessionWithEventsResponse(
        id=str(session_doc["_id"]),
        candidate_name=session_doc["candidate_name"],
        start_time=session_doc["start_time"],
        end_time=session_doc.get("end_time"),
        video_path=session_doc.get("video_path"),
        events=events,
    )


@app.post("/sessions/{session_id}/events", response_model=EventResponse)
async def log_event(session_id: str, payload: LogEventRequest):
    session_doc = await sessions_collection.find_one({"_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")

    timestamp = payload.timestamp or datetime.utcnow()
    event_id = str(uuid.uuid4())
    event_data = Event(
        id=event_id,
        session_id=session_id,
        event_type=payload.event_type,
        message=payload.message,
        timestamp=timestamp,
    )

    # Store with _id
    event_doc = {
        "_id": event_id,
        "session_id": event_data.session_id,
        "event_type": event_data.event_type,
        "message": event_data.message,
        "timestamp": event_data.timestamp,
    }
    await events_collection.insert_one(event_doc)

    return EventResponse(
        id=event_id,
        event_type=event_data.event_type,
        message=event_data.message,
        timestamp=event_data.timestamp,
    )


@app.post("/sessions/{session_id}/end", response_model=SessionResponse)
async def end_session(session_id: str):
    session_doc = await sessions_collection.find_one({"_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")

    if session_doc.get("end_time") is None:
        now = datetime.utcnow()
        await sessions_collection.update_one(
            {"_id": session_id},
            {"$set": {"end_time": now}}
        )
        session_doc["end_time"] = now

    return SessionResponse(
        id=str(session_doc["_id"]),
        candidate_name=session_doc["candidate_name"],
        start_time=session_doc["start_time"],
        end_time=session_doc.get("end_time"),
        video_path=session_doc.get("video_path"),
    )


@app.post("/sessions/{session_id}/video", response_model=SessionResponse)
async def upload_video(session_id: str, file: UploadFile = File(...)):
    session_doc = await sessions_collection.find_one({"_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")

    suffix = Path(file.filename).suffix if file.filename else ".webm"
    filename = f"{session_id}{suffix}"
    content = await file.read()
    saved_ref = storage.save_video_bytes(filename, content)

    await sessions_collection.update_one(
        {"_id": session_id},
        {"$set": {"video_path": str(saved_ref)}}
    )

    return SessionResponse(
        id=str(session_doc["_id"]),
        candidate_name=session_doc["candidate_name"],
        start_time=session_doc["start_time"],
        end_time=session_doc.get("end_time"),
        video_path=str(saved_ref),
    )


@app.post("/sessions/{session_id}/video/import", response_model=SessionResponse)
async def import_video(session_id: str, payload: ImportVideoRequest):
    session_doc = await sessions_collection.find_one({"_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")

    source_dir = Path("frontend") / "data"
    src_path = source_dir / payload.filename
    if not src_path.exists() or not src_path.is_file():
        raise HTTPException(status_code=404, detail="Source video not found")

    suffix = src_path.suffix or ".webm"
    filename = f"{session_id}{suffix}"
    saved_ref = storage.save_video_bytes(filename, src_path.read_bytes())

    await sessions_collection.update_one(
        {"_id": session_id},
        {"$set": {"video_path": str(saved_ref)}}
    )

    return SessionResponse(
        id=str(session_doc["_id"]),
        candidate_name=session_doc["candidate_name"],
        start_time=session_doc["start_time"],
        end_time=session_doc.get("end_time"),
        video_path=str(saved_ref),
    )


@app.get("/sessions/{session_id}/report", response_model=ReportResponse)
async def get_report(session_id: str):
    session_doc = await sessions_collection.find_one({"_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get events for this session
    events_cursor = events_collection.find({"session_id": session_id}).sort("timestamp", 1)
    events = []
    async for event_doc in events_cursor:
        events.append(Event(
            id=event_doc["_id"],
            session_id=event_doc["session_id"],
            event_type=event_doc["event_type"],
            message=event_doc.get("message"),
            timestamp=event_doc["timestamp"],
        ))

    counts = summarize_events(events)
    integrity_score = compute_integrity_score(counts)

    duration_seconds = 0
    if session_doc.get("start_time") and session_doc.get("end_time"):
        duration_seconds = int((session_doc["end_time"] - session_doc["start_time"]).total_seconds())

    # Create session object for report generation
    session_obj = Session(
        id=session_doc["_id"],
        candidate_name=session_doc["candidate_name"],
        start_time=session_doc["start_time"],
        end_time=session_doc.get("end_time"),
        video_path=session_doc.get("video_path"),
    )

    # Save HTML report via storage
    html = build_html_report_content(session_obj, counts, integrity_score)
    storage.save_report_bytes(f"report_{session_id}.html", html.encode("utf-8"), "text/html")

    suspicious_total = sum([
        counts.get("multiple_faces", 0),
        counts.get("phone_detected", 0),
        counts.get("notes_detected", 0),
        counts.get("device_detected", 0),
    ])

    return ReportResponse(
        candidate_name=session_doc["candidate_name"],
        session_id=str(session_doc["_id"]),
        interview_duration_seconds=duration_seconds,
        focus_lost_count=counts.get("focus_lost", 0),
        looking_away_count=counts.get("looking_away", 0),
        no_face_segments=counts.get("no_face", 0),
        multiple_faces_count=counts.get("multiple_faces", 0),
        phone_detected_count=counts.get("phone_detected", 0),
        notes_detected_count=counts.get("notes_detected", 0),
        device_detected_count=counts.get("device_detected", 0),
        suspicious_events_count=suspicious_total,
        integrity_score=integrity_score,
    )


@app.get("/sessions/{session_id}/report.csv")
async def download_report_csv(session_id: str):
    session_doc = await sessions_collection.find_one({"_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")

    events_cursor = events_collection.find({"session_id": session_id}).sort("timestamp", 1)
    events = []
    async for event_doc in events_cursor:
        events.append(Event(
            id=event_doc["_id"],
            session_id=event_doc["session_id"],
            event_type=event_doc["event_type"],
            message=event_doc.get("message"),
            timestamp=event_doc["timestamp"],
        ))

    counts = summarize_events(events)
    integrity_score = compute_integrity_score(counts)

    session_obj = Session(
        id=session_doc["_id"],
        candidate_name=session_doc["candidate_name"],
        start_time=session_doc["start_time"],
        end_time=session_doc.get("end_time"),
        video_path=session_doc.get("video_path"),
    )

    csv_content = build_csv_report_content(session_obj, counts, integrity_score)
    storage.save_report_bytes(f"report_{session_id}.csv", csv_content.encode("utf-8"), "text/csv")
    return StreamingResponse(
        iter([csv_content.encode("utf-8")]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=report_{session_id}.csv"},
    )


@app.get("/videos/{name}")
async def get_video(name: str):
    if isinstance(storage, LocalStorage):
        raise HTTPException(status_code=404, detail="Use /videos static mount")
    data = storage.open_bytes(f"videos/{name}")
    return StreamingResponse(iter([data]), media_type="video/webm")


@app.get("/reports/{name}")
async def get_report_file(name: str):
    if isinstance(storage, LocalStorage):
        raise HTTPException(status_code=404, detail="Use /reports static mount")
    data = storage.open_bytes(f"reports/{name}")
    media = "text/html" if name.endswith(".html") else "text/csv"
    return StreamingResponse(iter([data]), media_type=media)


@app.get("/")
def root():
    return {"status": "ok", "message": "Proctoring backend running"}
