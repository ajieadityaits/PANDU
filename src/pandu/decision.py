"""Pemilihan objek penting, stabilisasi, dan cooldown pengumuman."""

from __future__ import annotations

import time
from collections.abc import Iterable

from .config import DecisionConfig
from .domain import Alert, Candidate, Detection, Zone


class DecisionEngine:
    def __init__(
        self,
        config: DecisionConfig,
        class_weights: dict[str, float],
        translations: dict[str, str],
    ) -> None:
        self.config = config
        self.class_weights = class_weights
        self.translations = translations
        self._last_candidate_key: tuple[str, Zone] | None = None
        self._stable_frames = 0
        self._last_announced: dict[tuple[str, Zone], float] = {}

    def determine_zone(self, center_x: float, frame_width: int) -> Zone:
        ratio = center_x / max(frame_width, 1)
        if ratio < self.config.left_boundary:
            return Zone.LEFT
        if ratio < self.config.right_boundary:
            return Zone.CENTER
        return Zone.RIGHT

    def create_candidates(
        self,
        detections: Iterable[Detection],
        frame_width: int,
        frame_height: int,
    ) -> list[Candidate]:
        frame_area = max(frame_width * frame_height, 1)
        candidates: list[Candidate] = []

        for detection in detections:
            if detection.label not in self.class_weights:
                continue
            zone = self.determine_zone(detection.center_x, frame_width)
            normalized_area = min(detection.area / frame_area, 1.0)
            score = self.class_weights[detection.label]
            score += normalized_area * self.config.area_multiplier
            score += detection.confidence * self.config.confidence_multiplier
            if zone is Zone.CENTER:
                score += self.config.center_bonus
            candidates.append(
                Candidate(
                    detection=detection,
                    zone=zone,
                    score=score,
                    display_label=self.translations.get(detection.label, detection.label),
                )
            )
        return candidates

    def best_candidate(
        self,
        detections: Iterable[Detection],
        frame_width: int,
        frame_height: int,
    ) -> Candidate | None:
        candidates = self.create_candidates(detections, frame_width, frame_height)
        return max(candidates, key=lambda item: item.score, default=None)

    def select_alert(
        self,
        detections: Iterable[Detection],
        frame_width: int,
        frame_height: int,
        now: float | None = None,
    ) -> Alert | None:
        current_time = time.monotonic() if now is None else now
        candidate = self.best_candidate(detections, frame_width, frame_height)

        if candidate is None:
            self._last_candidate_key = None
            self._stable_frames = 0
            return None

        if candidate.key == self._last_candidate_key:
            self._stable_frames += 1
        else:
            self._last_candidate_key = candidate.key
            self._stable_frames = 1

        if self._stable_frames < self.config.stability_frames:
            return None

        previous_time = self._last_announced.get(candidate.key)
        if previous_time is not None and current_time - previous_time < self.config.cooldown_seconds:
            return None

        self._last_announced[candidate.key] = current_time
        prefix = "Perhatian" if self.class_weights[candidate.detection.label] >= 9 else "Terdeteksi"
        message = f"{prefix}, {candidate.display_label} di {candidate.zone.value}."
        return Alert(candidate=candidate, message=message)

