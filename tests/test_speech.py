import threading
import unittest
from pathlib import Path
import sys


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from pandu.speech import SpeechWorker


class RecordingBackend:
    def __init__(self, messages, completed, expected_count):
        self.messages = messages
        self.completed = completed
        self.expected_count = expected_count

    def speak(self, message):
        self.messages.append(message)
        if len(self.messages) >= self.expected_count:
            self.completed.set()

    def close(self):
        return None


class FailingBackend:
    def speak(self, _message):
        raise RuntimeError("simulasi driver audio gagal")

    def close(self):
        return None


class SpeechWorkerTests(unittest.TestCase):
    def test_worker_speaks_more_than_one_message(self):
        messages = []
        completed = threading.Event()

        def factory(_backend, _rate, _volume):
            return RecordingBackend(messages, completed, expected_count=2)

        worker = SpeechWorker(queue_size=3, backend_factory=factory)
        worker.start()
        self.assertTrue(worker.say("Terdeteksi kursi di depan."))
        self.assertTrue(worker.say("Perhatian mobil di depan."))
        self.assertTrue(completed.wait(timeout=2.0))
        worker.stop()

        self.assertEqual(
            messages,
            ["Terdeteksi kursi di depan.", "Perhatian mobil di depan."],
        )

    def test_worker_recreates_backend_and_retries_after_error(self):
        messages = []
        errors = []
        completed = threading.Event()
        factory_calls = 0

        def factory(_backend, _rate, _volume):
            nonlocal factory_calls
            factory_calls += 1
            if factory_calls == 1:
                return FailingBackend()
            return RecordingBackend(messages, completed, expected_count=1)

        worker = SpeechWorker(
            queue_size=2,
            backend_factory=factory,
            on_error=errors.append,
        )
        worker.start()
        self.assertTrue(worker.say("Terdeteksi botol di depan."))
        self.assertTrue(completed.wait(timeout=2.0))
        worker.stop()

        self.assertEqual(messages, ["Terdeteksi botol di depan."])
        self.assertEqual(factory_calls, 2)
        self.assertTrue(any("Percobaan 1 gagal" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
