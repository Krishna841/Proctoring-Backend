import os
from pathlib import Path
from typing import Optional

from fastapi.responses import StreamingResponse


class BaseStorage:
    backend: str = "local"

    def save_video_bytes(self, key: str, data: bytes) -> str:
        raise NotImplementedError

    def save_report_bytes(self, key: str, data: bytes, content_type: str) -> str:
        raise NotImplementedError

    def open_bytes(self, key: str) -> bytes:
        raise NotImplementedError


class LocalStorage(BaseStorage):
    backend: str = "local"

    def __init__(self, video_dir: Path, report_dir: Path) -> None:
        self.video_dir = video_dir
        self.report_dir = report_dir
        self.video_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        if key.startswith("videos/"):
            return self.video_dir / key.split("/", 1)[1]
        if key.startswith("reports/"):
            return self.report_dir / key.split("/", 1)[1]
        # default: treat as reports
        return self.report_dir / key

    def save_video_bytes(self, key: str, data: bytes) -> str:
        path = self._resolve(f"videos/{key}")
        path.write_bytes(data)
        return str(path)

    def save_report_bytes(self, key: str, data: bytes, content_type: str) -> str:
        path = self._resolve(f"reports/{key}")
        path.write_bytes(data)
        return str(path)

    def open_bytes(self, key: str) -> bytes:
        path = self._resolve(key)
        return path.read_bytes()


class DetaStorage(BaseStorage):
    backend: str = "deta"

    def __init__(self) -> None:
        from deta import Deta  # type: ignore

        project_key = os.getenv("DETA_PROJECT_KEY")
        deta = Deta(project_key) if project_key else Deta()
        self.videos = deta.Drive("videos")
        self.reports = deta.Drive("reports")

    def save_video_bytes(self, key: str, data: bytes) -> str:
        self.videos.put(key, data)
        return f"videos/{key}"

    def save_report_bytes(self, key: str, data: bytes, content_type: str) -> str:
        self.reports.put(key, data)
        return f"reports/{key}"

    def open_bytes(self, key: str) -> bytes:
        drive, name = key.split("/", 1) if "/" in key else ("reports", key)
        bucket = self.reports if drive == "reports" else self.videos
        with bucket.get(name) as stream:  # type: ignore
            return stream.read()


def get_storage(video_dir: Path, report_dir: Path) -> BaseStorage:
    backend = os.getenv("STORAGE_BACKEND", "local").lower()
    if backend == "deta" or os.getenv("DETA_RUNTIME"):
        return DetaStorage()
    return LocalStorage(video_dir=video_dir, report_dir=report_dir)


