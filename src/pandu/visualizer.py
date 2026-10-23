"""Penggambaran bounding box, zona, pesan, dan FPS."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .domain import Candidate, Detection, Zone


ZONE_COLORS = {
    Zone.LEFT: (255, 180, 0),
    Zone.CENTER: (0, 0, 255),
    Zone.RIGHT: (0, 200, 255),
}


def draw_frame(
    frame: Any,
    detections: Iterable[Detection],
    candidates: Iterable[Candidate],
    left_boundary: float,
    right_boundary: float,
    fps: float,
    status_message: str,
    show_fps: bool = True,
) -> Any:
    import cv2

    height, width = frame.shape[:2]
    left_x = int(width * left_boundary)
    right_x = int(width * right_boundary)
    cv2.line(frame, (left_x, 0), (left_x, height), (120, 120, 120), 1)
    cv2.line(frame, (right_x, 0), (right_x, height), (120, 120, 120), 1)
    cv2.putText(frame, "KIRI", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(frame, "DEPAN", (left_x + 20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(frame, "KANAN", (right_x + 20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    candidate_by_detection = {candidate.detection: candidate for candidate in candidates}
    for detection in detections:
        candidate = candidate_by_detection.get(detection)
        if candidate is None:
            continue
        color = ZONE_COLORS[candidate.zone]
        cv2.rectangle(frame, (detection.x1, detection.y1), (detection.x2, detection.y2), color, 2)
        label = f"{candidate.display_label} {detection.confidence:.0%} | {candidate.zone.value}"
        text_y = max(20, detection.y1 - 8)
        cv2.putText(
            frame,
            label,
            (detection.x1, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
        )

    if status_message:
        cv2.rectangle(frame, (0, height - 42), (width, height), (0, 0, 0), -1)
        cv2.putText(
            frame,
            status_message,
            (15, height - 14),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
        )
    if show_fps:
        cv2.putText(
            frame,
            f"FPS: {fps:.1f}",
            (max(10, width - 150), 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 255, 0),
            2,
        )
    return frame

