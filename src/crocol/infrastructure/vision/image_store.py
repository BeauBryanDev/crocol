import time
import uuid
from pathlib import Path

from config.settings import UPLOAD_DIR, UPLOAD_RETENTION_H


class LocalImageStore:
    """Sanitized uploads on local disk, deleted after the retention window."""

    def __init__(self,
                 directory: Path = UPLOAD_DIR,
                 retention_hours: float = UPLOAD_RETENTION_H
                 ) -> None:

        self._directory = directory
        self._retention_s = retention_hours * 3600

    def path_for(self, trace_id: str) -> Path:
        """Only canonical UUIDs become file names (no path tricks)."""
        canonical = str(uuid.UUID(trace_id))
        
        return self._directory / f"{canonical}.jpg"

    def save(self, trace_id: str, jpeg: bytes) -> Path:

        self._directory.mkdir(parents=True, exist_ok=True)
        target = self.path_for(trace_id)
        target.write_bytes(jpeg)
        
        return target

    def purge(self, now: float | None = None) -> int:
        """Delete stored images older than the retention window."""
        if not self._directory.exists():
            return 0

        cutoff = (now if now is not None else time.time()) - self._retention_s
        removed = 0
        
        for path in self._directory.glob("*.jpg"):
            
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
                removed += 1
                
        return removed
