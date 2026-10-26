"""Dukungan sumber video jaringan, misalnya kamera HP lewat aplikasi DroidCam."""

from __future__ import annotations

import threading
import time
from typing import Any


DROIDCAM_DEFAULT_PORT = 4747
DROIDCAM_DEFAULT_PATH = "/video"
NETWORK_SCHEMES = ("http://", "https://", "rtsp://", "rtmp://")


def is_network_source(source: int | str) -> bool:
    return isinstance(source, str) and source.strip().lower().startswith(NETWORK_SCHEMES)


def droidcam_url(value: str) -> str:
    """Bangun URL stream DroidCam dari IP, ``IP:port``, atau URL lengkap.

    Contoh: ``192.168.1.5`` -> ``http://192.168.1.5:4747/video``.
    """
    text = value.strip()
    if not text:
        raise ValueError("Alamat DroidCam kosong. Contoh: --droidcam 192.168.1.5")
    if is_network_source(text):
        return text
    host, _, rest = text.partition("/")
    if ":" not in host:
        host = f"{host}:{DROIDCAM_DEFAULT_PORT}"
    path = f"/{rest}" if rest else DROIDCAM_DEFAULT_PATH
    return f"http://{host}{path}"


class LatestFrameReader:
    """Membaca stream di thread terpisah dan hanya menyimpan frame terbaru.

    Deteksi YOLO di CPU biasanya lebih lambat daripada laju frame kamera HP.
    Tanpa ini, frame menumpuk di buffer dan tampilan/suara tertinggal beberapa
    detik dari kondisi sebenarnya.
    """

    def __init__(self, capture: Any, read_timeout_seconds: float = 2.0) -> None:
        self._capture = capture
        self._timeout = read_timeout_seconds
        self._condition = threading.Condition()
        self._frame: Any = None
        self._frame_id = 0
        self._last_returned_id = 0
        self._stopped = False
        self._thread = threading.Thread(target=self._run, name="pandu-stream", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while True:
            with self._condition:
                if self._stopped:
                    return
            ok, frame = self._capture.read()
            with self._condition:
                if self._stopped:
                    return
                if ok and frame is not None:
                    self._frame = frame
                    self._frame_id += 1
                    self._condition.notify_all()
            if not ok:
                time.sleep(0.05)

    def isOpened(self) -> bool:  # noqa: N802 - meniru API cv2.VideoCapture
        return self._capture.isOpened()

    def read(self) -> tuple[bool, Any]:
        """Kembalikan frame baru, atau ``(False, None)`` jika tidak ada dalam batas waktu."""
        with self._condition:
            self._condition.wait_for(
                lambda: self._stopped or self._frame_id != self._last_returned_id,
                timeout=self._timeout,
            )
            if self._stopped or self._frame_id == self._last_returned_id:
                return False, None
            self._last_returned_id = self._frame_id
            return True, self._frame

    def release(self) -> None:
        with self._condition:
            self._stopped = True
            self._condition.notify_all()
        self._thread.join(timeout=3.0)
        # Jangan release saat thread masih di dalam read() (bisa crash di OpenCV);
        # thread daemon akan ikut berhenti ketika program keluar.
        if not self._thread.is_alive():
            self._capture.release()
