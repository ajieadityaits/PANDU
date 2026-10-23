"""TTS tahan-gagal pada thread terpisah agar loop kamera tidak terblokir."""

from __future__ import annotations

import queue
import sys
import threading
from collections.abc import Callable
from typing import Any, Protocol


class SpeechBackend(Protocol):
    def speak(self, message: str) -> None: ...

    def close(self) -> None: ...


class WindowsSapiBackend:
    """Akses SAPI langsung untuk menghindari antrean pyttsx3 yang macet di Windows."""

    def __init__(self, rate: int, volume: float) -> None:
        import pythoncom
        from win32com.client import Dispatch

        self._pythoncom = pythoncom
        self._voice: Any = None
        self._com_initialized = False
        pythoncom.CoInitialize()
        self._com_initialized = True
        try:
            self._voice = Dispatch("SAPI.SpVoice")
            # Rentang SAPI adalah -10..10, sedangkan konfigurasi memakai perkiraan WPM.
            self._voice.Rate = max(-10, min(10, round((rate - 175) / 20)))
            self._voice.Volume = max(0, min(100, round(volume * 100)))
        except Exception:
            self.close()
            raise

    def speak(self, message: str) -> None:
        if self._voice is None:
            raise RuntimeError("Windows SAPI belum siap.")
        # Flag 0 = sinkron. Pemanggilan tetap berada di worker, bukan loop kamera.
        self._voice.Speak(message, 0)

    def close(self) -> None:
        self._voice = None
        if self._com_initialized:
            self._pythoncom.CoUninitialize()
            self._com_initialized = False


class Pyttsx3Backend:
    """Fallback lintas platform ketika Windows SAPI langsung tidak digunakan."""

    def __init__(self, rate: int, volume: float) -> None:
        import pyttsx3

        self._engine = pyttsx3.init()
        self._engine.setProperty("rate", rate)
        self._engine.setProperty("volume", volume)

    def speak(self, message: str) -> None:
        self._engine.say(message)
        self._engine.runAndWait()

    def close(self) -> None:
        try:
            self._engine.stop()
        except Exception:
            pass


BackendFactory = Callable[[str, int, float], SpeechBackend]


def create_speech_backend(backend: str, rate: int, volume: float) -> SpeechBackend:
    selected = backend.lower()
    if selected == "auto":
        selected = "sapi" if sys.platform.startswith("win") else "pyttsx3"
    if selected == "sapi":
        if not sys.platform.startswith("win"):
            raise RuntimeError("Backend SAPI hanya tersedia di Windows.")
        return WindowsSapiBackend(rate, volume)
    if selected == "pyttsx3":
        return Pyttsx3Backend(rate, volume)
    raise ValueError(f"Backend TTS tidak dikenal: {backend}")


class SpeechWorker:
    def __init__(
        self,
        enabled: bool = True,
        rate: int = 175,
        volume: float = 1.0,
        queue_size: int = 3,
        backend: str = "auto",
        on_error: Callable[[str], None] | None = None,
        backend_factory: BackendFactory | None = None,
    ) -> None:
        self.enabled = enabled
        self.rate = rate
        self.volume = volume
        self.backend = backend
        self.on_error = on_error or (lambda message: print(message))
        self._backend_factory = backend_factory or create_speech_backend
        self._queue: queue.Queue[str | None] = queue.Queue(maxsize=queue_size)
        self._thread: threading.Thread | None = None
        self._started = False
        self._state_lock = threading.Lock()

    @property
    def selected_backend(self) -> str:
        if self.backend.lower() != "auto":
            return self.backend.lower()
        return "sapi" if sys.platform.startswith("win") else "pyttsx3"

    def start(self) -> None:
        if not self.enabled:
            return
        with self._state_lock:
            if self._started and self._thread is not None and self._thread.is_alive():
                return
            self._started = True
            self._thread = threading.Thread(
                target=self._run,
                name="pandu-tts",
                daemon=True,
            )
            self._thread.start()

    def say(self, message: str) -> bool:
        if not self.enabled:
            return False
        if self._thread is None or not self._thread.is_alive():
            self.start()
        try:
            self._queue.put_nowait(message)
            return True
        except queue.Full:
            self.on_error("[PERINGATAN TTS] Antrean suara penuh; pesan dilewati.")
            return False

    def stop(self) -> None:
        if not self.enabled:
            return
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            # Buang pesan tertua agar sentinel penghentian dapat dimasukkan.
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                pass
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        with self._state_lock:
            self._started = False

    def _run(self) -> None:
        speech_backend: SpeechBackend | None = None
        try:
            while True:
                message = self._queue.get()
                try:
                    if message is None:
                        break
                    # Satu kegagalan tidak boleh mematikan worker. Backend dibuat ulang
                    # dan pesan yang sama dicoba sekali lagi.
                    for attempt in range(2):
                        try:
                            if speech_backend is None:
                                speech_backend = self._backend_factory(
                                    self.backend,
                                    self.rate,
                                    self.volume,
                                )
                            speech_backend.speak(message)
                            break
                        except Exception as exc:
                            self.on_error(
                                f"[PERINGATAN TTS] Percobaan {attempt + 1} gagal: {exc}"
                            )
                            if speech_backend is not None:
                                speech_backend.close()
                            speech_backend = None
                finally:
                    self._queue.task_done()
        finally:
            if speech_backend is not None:
                speech_backend.close()
            with self._state_lock:
                self._started = False
