"""Enumerasi dan pembukaan webcam berdasarkan identitas perangkat."""

from __future__ import annotations

from dataclasses import dataclass
import sys
from typing import Any, Callable, Iterable

from .config import AppConfig


@dataclass(frozen=True, slots=True)
class CameraInfo:
    index: int
    name: str
    backend: str
    backend_code: int | None = None
    vid: int | None = None
    pid: int | None = None
    width: int = 0
    height: int = 0


@dataclass(slots=True)
class OpenedCamera:
    capture: Any
    index: int
    name: str
    backend: str


def parse_usb_id(value: int | str | None) -> int | None:
    """Ubah VID/PID integer atau heksadesimal (mis. ``046D``) menjadi integer."""
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip().lower()
    if text.startswith("0x"):
        text = text[2:]
    return int(text, 16)


def camera_candidates(
    configured_index: int | str,
    scan_max_index: int,
    prefer_external: bool,
) -> list[int]:
    """Fallback lama ketika enumerasi nama perangkat tidak tersedia."""
    if isinstance(configured_index, int):
        return [configured_index]
    if str(configured_index).lower() != "auto":
        raise ValueError("camera_index harus berupa bilangan bulat atau 'auto'.")

    external_indices = list(range(1, scan_max_index + 1))
    if prefer_external:
        return [*external_indices, 0]
    return [0, *external_indices]


def _backend_options(cv2: Any, requested: str) -> list[tuple[int | None, str]]:
    requested = requested.lower()
    if not sys.platform.startswith("win") or requested == "default":
        return [(None, "default")]

    options: list[tuple[int | None, str]] = []
    if requested in {"auto", "dshow"} and hasattr(cv2, "CAP_DSHOW"):
        options.append((cv2.CAP_DSHOW, "DirectShow"))
    if requested in {"auto", "msmf"} and hasattr(cv2, "CAP_MSMF"):
        options.append((cv2.CAP_MSMF, "Media Foundation"))
    if requested == "auto":
        options.append((None, "default"))
    return options


def _enumeration_backends(cv2: Any, requested: str) -> list[int]:
    if not sys.platform.startswith("win"):
        return [getattr(cv2, "CAP_ANY", 0)]
    requested = requested.lower()
    if requested == "dshow":
        return [cv2.CAP_DSHOW]
    if requested == "msmf":
        return [cv2.CAP_MSMF]
    if requested == "default":
        return [getattr(cv2, "CAP_ANY", 0)]
    return [cv2.CAP_DSHOW, cv2.CAP_MSMF]


def _backend_name(cv2: Any, backend_code: int | None) -> str:
    if backend_code is None:
        return "default"
    try:
        return str(cv2.videoio_registry.getBackendName(backend_code))
    except (AttributeError, TypeError, ValueError):
        if backend_code == getattr(cv2, "CAP_DSHOW", object()):
            return "DirectShow"
        if backend_code == getattr(cv2, "CAP_MSMF", object()):
            return "Media Foundation"
        return str(backend_code)


def enumerate_camera_devices(
    cv2: Any,
    config: AppConfig,
    enumerator: Callable[[int], Iterable[Any]] | None = None,
) -> list[CameraInfo]:
    """Ambil nama dan identitas webcam dengan backend yang sesuai."""
    if enumerator is None:
        try:
            from cv2_enumerate_cameras import enumerate_cameras
        except ImportError:
            return []
        enumerator = enumerate_cameras

    found: list[CameraInfo] = []
    seen: set[tuple[int, int | None, str]] = set()
    for backend_code in _enumeration_backends(cv2, config.camera_backend):
        try:
            devices = enumerator(backend_code)
        except Exception as exc:
            print(f"[PERINGATAN] Enumerasi kamera gagal pada backend {backend_code}: {exc}")
            continue
        for device in devices:
            actual_backend = getattr(device, "backend", backend_code)
            name = str(getattr(device, "name", "Kamera tanpa nama"))
            index = int(getattr(device, "index"))
            key = (index, actual_backend, name.casefold())
            if key in seen:
                continue
            seen.add(key)
            found.append(
                CameraInfo(
                    index=index,
                    name=name,
                    backend=_backend_name(cv2, actual_backend),
                    backend_code=actual_backend,
                    vid=getattr(device, "vid", None),
                    pid=getattr(device, "pid", None),
                )
            )
    return found


def matching_camera_devices(
    devices: Iterable[CameraInfo],
    preferred_name: str | None,
    preferred_vid: int | str | None,
) -> list[CameraInfo]:
    """Urutkan perangkat yang cocok; nama lebih spesifik daripada VID vendor."""
    name_query = (preferred_name or "").strip().casefold()
    vid_query = parse_usb_id(preferred_vid)
    ranked: list[tuple[int, CameraInfo]] = []

    for device in devices:
        device_name = device.name.casefold()
        name_score = 0
        if name_query:
            if device_name == name_query:
                name_score = 30
            elif device_name.startswith(name_query):
                name_score = 20
            elif name_query in device_name:
                name_score = 10
        vid_match = vid_query is not None and device.vid == vid_query
        if name_score or vid_match:
            ranked.append((name_score + (1 if vid_match else 0), device))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [device for _, device in ranked]


def _create_capture(cv2: Any, index: int, backend_code: int | None) -> Any:
    if backend_code is None:
        return cv2.VideoCapture(index)
    return cv2.VideoCapture(index, backend_code)


def _try_open_device(
    cv2: Any,
    config: AppConfig,
    index: int,
    backend_code: int | None,
    backend_name: str,
    name: str,
) -> OpenedCamera | None:
    capture = _create_capture(cv2, index, backend_code)
    if capture.isOpened():
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.frame_width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.frame_height)
        ok, frame = capture.read()
        if ok and frame is not None:
            return OpenedCamera(capture=capture, index=index, name=name, backend=backend_name)
    capture.release()
    return None


def open_camera(
    cv2: Any,
    config: AppConfig,
    index_override: int | None = None,
    name_override: str | None = None,
    devices: list[CameraInfo] | None = None,
) -> OpenedCamera | None:
    """Buka kamera berdasarkan nama/VID, atau indeks jika di-override."""
    if index_override is None:
        available = enumerate_camera_devices(cv2, config) if devices is None else devices
        preferred_name = name_override if name_override is not None else config.camera_name
        preferred_vid = None if name_override is not None else config.camera_vendor_id
        matches = matching_camera_devices(available, preferred_name, preferred_vid)
        for device in matches:
            opened = _try_open_device(
                cv2,
                config,
                device.index,
                device.backend_code,
                device.backend,
                device.name,
            )
            if opened is not None:
                return opened

        selector_requested = bool((preferred_name or "").strip() or preferred_vid is not None)
        if selector_requested and not config.allow_camera_fallback:
            return None

    configured_index: int | str = config.camera_index if index_override is None else index_override
    indices = camera_candidates(
        configured_index,
        config.camera_scan_max_index,
        config.prefer_external_camera,
    )
    for index in indices:
        for backend_code, backend_name in _backend_options(cv2, config.camera_backend):
            opened = _try_open_device(
                cv2, config, index, backend_code, backend_name, f"kamera indeks {index}"
            )
            if opened is not None:
                return opened
    return None


def scan_cameras(cv2: Any, config: AppConfig) -> list[CameraInfo]:
    """Daftar kamera bernama; fallback ke probing indeks pada platform lama."""
    named_devices = enumerate_camera_devices(cv2, config)
    if named_devices:
        return named_devices

    found: list[CameraInfo] = []
    for index in range(config.camera_scan_max_index + 1):
        opened = open_camera(cv2, config, index_override=index, devices=[])
        if opened is None:
            continue
        width = int(opened.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(opened.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        found.append(
            CameraInfo(
                index=index,
                name=opened.name,
                width=width,
                height=height,
                backend=opened.backend,
            )
        )
        opened.capture.release()
    return found
