from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ListeningEvent:
    artist: str
    album: str
    track: str
    listened_at: datetime
