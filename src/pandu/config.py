"""Konfigurasi aplikasi dan pemuatan berkas YAML."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class AppConfig:
    window_title: str = "PANDU - Tekan Q untuk keluar"
    camera_index: int | str = "auto"
    camera_scan_max_index: int = 5
    prefer_external_camera: bool = True
    camera_backend: str = "dshow"
    camera_name: str | None = "Logitech"
    camera_vendor_id: int | str | None = "046D"
    allow_camera_fallback: bool = False
    frame_width: int = 1280
    frame_height: int = 720
    show_fps: bool = True


@dataclass(slots=True)
class ModelConfig:
    name: str = "yolo11n.pt"
    confidence_threshold: float = 0.45
    image_size: int = 640
    device: str | int | None = None


@dataclass(slots=True)
class DecisionConfig:
    left_boundary: float = 0.33
    right_boundary: float = 0.67
    cooldown_seconds: float = 6.0
    stability_frames: int = 3
    center_bonus: float = 2.0
    area_multiplier: float = 10.0
    confidence_multiplier: float = 1.0


@dataclass(slots=True)
class SpeechConfig:
    enabled: bool = True
    backend: str = "auto"
    rate: int = 175
    volume: float = 1.0
    queue_size: int = 3


@dataclass(slots=True)
class Config:
    app: AppConfig = field(default_factory=AppConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    decision: DecisionConfig = field(default_factory=DecisionConfig)
    speech: SpeechConfig = field(default_factory=SpeechConfig)
    classes: dict[str, float] = field(default_factory=dict)
    translations: dict[str, str] = field(default_factory=dict)


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ValueError(f"Bagian '{name}' pada konfigurasi harus berupa mapping.")
    return value


def load_config(path: str | Path) -> Config:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Berkas konfigurasi tidak ditemukan: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        raise ValueError("Isi konfigurasi harus berupa mapping YAML.")

    config = Config(
        app=AppConfig(**_section(raw, "app")),
        model=ModelConfig(**_section(raw, "model")),
        decision=DecisionConfig(**_section(raw, "decision")),
        speech=SpeechConfig(**_section(raw, "speech")),
        classes={str(k): float(v) for k, v in _section(raw, "classes").items()},
        translations={str(k): str(v) for k, v in _section(raw, "translations").items()},
    )
    validate_config(config)
    return config


def validate_config(config: Config) -> None:
    camera_index = config.app.camera_index
    if not isinstance(camera_index, int) and str(camera_index).lower() != "auto":
        raise ValueError("camera_index harus berupa bilangan bulat atau 'auto'.")
    if config.app.camera_scan_max_index < 0:
        raise ValueError("camera_scan_max_index tidak boleh negatif.")
    if config.app.camera_backend.lower() not in {"auto", "dshow", "msmf", "default"}:
        raise ValueError("camera_backend harus auto, dshow, msmf, atau default.")
    if config.app.camera_name is not None and not isinstance(config.app.camera_name, str):
        raise ValueError("camera_name harus berupa teks atau null.")
    if config.app.camera_vendor_id is not None:
        try:
            raw_vendor_id = config.app.camera_vendor_id
            text = str(raw_vendor_id).strip().lower().removeprefix("0x")
            vendor_id = raw_vendor_id if isinstance(raw_vendor_id, int) else int(text, 16)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "camera_vendor_id harus berupa VID heksadesimal, misalnya '046D'."
            ) from exc
        if not 0 <= int(vendor_id) <= 0xFFFF:
            raise ValueError("camera_vendor_id harus berada antara 0000 dan FFFF.")
    if not 0.0 <= config.model.confidence_threshold <= 1.0:
        raise ValueError("confidence_threshold harus berada di antara 0 dan 1.")
    if not 0.0 < config.decision.left_boundary < config.decision.right_boundary < 1.0:
        raise ValueError("Batas zona harus memenuhi 0 < kiri < kanan < 1.")
    if config.decision.stability_frames < 1:
        raise ValueError("stability_frames minimal 1.")
    if config.decision.cooldown_seconds < 0:
        raise ValueError("cooldown_seconds tidak boleh negatif.")
    if config.speech.queue_size < 1:
        raise ValueError("queue_size minimal 1.")
    if config.speech.backend.lower() not in {"auto", "sapi", "pyttsx3"}:
        raise ValueError("speech.backend harus auto, sapi, atau pyttsx3.")
