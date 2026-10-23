"""Tipe data inti yang tidak bergantung pada OpenCV atau YOLO."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Zone(str, Enum):
    LEFT = "kiri"
    CENTER = "depan"
    RIGHT = "kanan"


@dataclass(frozen=True, slots=True)
class Detection:
    label: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def center_x(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def area(self) -> int:
        return max(0, self.x2 - self.x1) * max(0, self.y2 - self.y1)


@dataclass(frozen=True, slots=True)
class Candidate:
    detection: Detection
    zone: Zone
    score: float
    display_label: str

    @property
    def key(self) -> tuple[str, Zone]:
        return self.detection.label, self.zone


@dataclass(frozen=True, slots=True)
class Alert:
    candidate: Candidate
    message: str

