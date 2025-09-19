from datetime import datetime
from pathlib import Path
from typing import Dict, List

from .models import Event, Session


EVENT_WEIGHTS = {
    "focus_lost": 2,
    "looking_away": 2,
    "no_face": 5,
    "multiple_faces": 10,
    "phone_detected": 10,
    "notes_detected": 5,
    "device_detected": 8,
}


def summarize_events(events: List[Event]) -> Dict[str, int]:
    counts: Dict[str, int] = {
        "focus_lost": 0,
        "looking_away": 0,
        "no_face": 0,
        "multiple_faces": 0,
        "phone_detected": 0,
        "notes_detected": 0,
        "device_detected": 0,
    }
    for e in events:
        key = e.event_type if e.event_type in counts else None
        if key:
            counts[key] += 1
    return counts


def compute_integrity_score(counts: Dict[str, int]) -> int:
    score = 100
    for k, v in counts.items():
        weight = EVENT_WEIGHTS.get(k, 0)
        score -= v * weight
    return max(0, score)


def write_html_report(session: Session, counts: Dict[str, int], integrity_score: int, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / f"report_{session.id}.html"
    duration_seconds = 0
    if session.end_time and session.start_time:
        duration_seconds = int((session.end_time - session.start_time).total_seconds())

    html = f"""
    <!doctype html>
    <html>
    <head>
        <meta charset='utf-8' />
        <title>Proctoring Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 24px; }}
            h1 {{ margin-top: 0; }}
            .grid {{ display: grid; grid-template-columns: 240px 1fr; gap: 8px 16px; }}
            .card {{ border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin-top: 16px; }}
        </style>
    </head>
    <body>
        <h1>Proctoring Report</h1>
        <div class='grid'>
            <div><strong>Candidate Name</strong></div><div>{session.candidate_name}</div>
            <div><strong>Session ID</strong></div><div>{session.id}</div>
            <div><strong>Start Time</strong></div><div>{session.start_time}</div>
            <div><strong>End Time</strong></div><div>{session.end_time or ''}</div>
            <div><strong>Duration (s)</strong></div><div>{duration_seconds}</div>
            <div><strong>Integrity Score</strong></div><div>{integrity_score}</div>
        </div>

        <div class='card'>
            <h3>Event Summary</h3>
            <ul>
                <li>Focus lost: {counts.get('focus_lost', 0)}</li>
                <li>Looking away: {counts.get('looking_away', 0)}</li>
                <li>No face: {counts.get('no_face', 0)}</li>
                <li>Multiple faces: {counts.get('multiple_faces', 0)}</li>
                <li>Phone detected: {counts.get('phone_detected', 0)}</li>
                <li>Notes detected: {counts.get('notes_detected', 0)}</li>
                <li>Extra device detected: {counts.get('device_detected', 0)}</li>
            </ul>
        </div>
    </body>
    </html>
    """
    file_path.write_text(html, encoding="utf-8")
    return file_path

