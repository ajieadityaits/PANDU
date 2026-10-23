"""Adaptor Ultralytics YOLO untuk mengubah hasil model menjadi Detection."""

from __future__ import annotations

from typing import Any

from .domain import Detection


class YoloDetector:
    def __init__(
        self,
        model_name: str,
        confidence_threshold: float,
        image_size: int,
        device: str | int | None = None,
    ) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "Ultralytics belum terpasang. Jalankan: pip install -r requirements.txt"
            ) from exc

        self.model = YOLO(model_name)
        self.confidence_threshold = confidence_threshold
        self.image_size = image_size
        self.device = device

    def detect(self, frame: Any) -> list[Detection]:
        predict_args: dict[str, Any] = {
            "source": frame,
            "conf": self.confidence_threshold,
            "imgsz": self.image_size,
            "verbose": False,
        }
        if self.device is not None:
            predict_args["device"] = self.device

        result = self.model.predict(**predict_args)[0]
        names = result.names
        detections: list[Detection] = []
        if result.boxes is None:
            return detections

        for box in result.boxes:
            class_id = int(box.cls[0].item())
            confidence = float(box.conf[0].item())
            x1, y1, x2, y2 = (int(value) for value in box.xyxy[0].tolist())
            detections.append(
                Detection(
                    label=str(names[class_id]),
                    confidence=confidence,
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                )
            )
        return detections

