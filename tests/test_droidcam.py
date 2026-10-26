import unittest
from pathlib import Path
from unittest import mock
import sys


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from pandu import camera as camera_module
from pandu.camera import CameraInfo, _read_first_frame, open_camera
from pandu.config import AppConfig
from pandu.stream import LatestFrameReader, droidcam_url, is_network_source


class FakeFrame:
    shape = (480, 640, 3)


class ScriptedCapture:
    """Capture palsu yang mengembalikan hasil read() sesuai skrip."""

    def __init__(self, reads, opened=True):
        self.reads = list(reads)
        self.opened = opened
        self.set_calls = []
        self.released = False

    def isOpened(self):
        return self.opened

    def set(self, prop, value):
        self.set_calls.append((prop, value))
        return True

    def read(self):
        if self.reads:
            ok = self.reads.pop(0)
        else:
            ok = False
        return (True, FakeFrame()) if ok else (False, None)

    def release(self):
        self.released = True


class ScriptedCv2:
    CAP_PROP_FRAME_WIDTH = 3
    CAP_PROP_FRAME_HEIGHT = 4
    CAP_DSHOW = 700
    CAP_MSMF = 1400
    CAP_ANY = 0

    def __init__(self, factory):
        self.factory = factory
        self.calls = []

    def VideoCapture(self, index, backend=None):
        self.calls.append((index, backend))
        return self.factory(index, backend, len(self.calls))


class DroidCamUrlTests(unittest.TestCase):
    def test_ip_only_gets_default_port_and_path(self):
        self.assertEqual(droidcam_url("192.168.1.5"), "http://192.168.1.5:4747/video")

    def test_custom_port_is_kept(self):
        self.assertEqual(droidcam_url("192.168.1.5:5000"), "http://192.168.1.5:5000/video")

    def test_custom_path_is_kept(self):
        self.assertEqual(droidcam_url("10.0.0.2/mjpegfeed"), "http://10.0.0.2:4747/mjpegfeed")

    def test_full_url_is_unchanged(self):
        url = "http://192.168.1.5:4747/video"
        self.assertEqual(droidcam_url(url), url)

    def test_empty_value_is_rejected(self):
        with self.assertRaises(ValueError):
            droidcam_url("  ")

    def test_network_source_detection(self):
        self.assertTrue(is_network_source("http://192.168.1.5:4747/video"))
        self.assertTrue(is_network_source("RTSP://cam/stream"))
        self.assertFalse(is_network_source("D:\\video.mp4"))
        self.assertFalse(is_network_source(0))


class WarmupTests(unittest.TestCase):
    def test_empty_first_frames_are_tolerated(self):
        capture = ScriptedCapture([False, False, False, True])
        self.assertTrue(_read_first_frame(capture, attempts=5, sleep=lambda _s: None))

    def test_gives_up_after_attempts(self):
        capture = ScriptedCapture([False] * 10)
        self.assertFalse(_read_first_frame(capture, attempts=3, sleep=lambda _s: None))


class ResolutionRetryTests(unittest.TestCase):
    def test_reopens_without_forced_resolution_when_hd_gives_no_frames(self):
        captures = []

        def factory(index, backend, call_number):
            # Percobaan pertama (resolusi dipaksa) tidak pernah memberi frame,
            # percobaan kedua (tanpa set resolusi) langsung berhasil.
            cap = ScriptedCapture([] if call_number == 1 else [True])
            captures.append(cap)
            return cap

        fake_cv2 = ScriptedCv2(factory)
        config = AppConfig(camera_name="DroidCam", camera_vendor_id=None)
        devices = [CameraInfo(1, "DroidCam Source 3", "DirectShow", 700)]

        with mock.patch.object(camera_module, "WARMUP_READ_ATTEMPTS", 2), \
                mock.patch.object(camera_module, "WARMUP_READ_DELAY_SECONDS", 0):
            opened = open_camera(fake_cv2, config, name_override="DroidCam", devices=devices)

        self.assertIsNotNone(opened)
        self.assertEqual(len(captures), 2)
        self.assertTrue(captures[0].set_calls)
        self.assertTrue(captures[0].released)
        self.assertEqual(captures[1].set_calls, [])


class AlternateBackendTests(unittest.TestCase):
    def test_falls_back_to_media_foundation_when_directshow_fails(self):
        def factory(index, backend, _call_number):
            return ScriptedCapture([True], opened=(backend == ScriptedCv2.CAP_MSMF))

        fake_cv2 = ScriptedCv2(factory)
        config = AppConfig(camera_name="DroidCam", camera_vendor_id=None, camera_backend="dshow")

        def fake_enumerate(_cv2, _config, enumerator=None, backends=None):
            if backends == [ScriptedCv2.CAP_MSMF]:
                return [CameraInfo(0, "DroidCam Video", "Media Foundation", 1400)]
            return [CameraInfo(1, "DroidCam Video", "DirectShow", 700)]

        with mock.patch.object(camera_module.sys, "platform", "win32"), \
                mock.patch.object(camera_module, "enumerate_camera_devices", fake_enumerate):
            opened = open_camera(fake_cv2, config, name_override="DroidCam")

        self.assertIsNotNone(opened)
        self.assertEqual(opened.backend, "Media Foundation")
        self.assertEqual(fake_cv2.calls, [(1, 700), (0, 1400)])


class LatestFrameReaderTests(unittest.TestCase):
    def test_returns_frames_and_releases(self):
        capture = ScriptedCapture([True] * 1000)
        reader = LatestFrameReader(capture, read_timeout_seconds=1.0)
        try:
            ok, frame = reader.read()
            self.assertTrue(ok)
            self.assertIsInstance(frame, FakeFrame)
        finally:
            reader.release()
        self.assertTrue(capture.released)

    def test_times_out_when_stream_stalls(self):
        capture = ScriptedCapture([])
        reader = LatestFrameReader(capture, read_timeout_seconds=0.2)
        try:
            self.assertEqual(reader.read(), (False, None))
        finally:
            reader.release()


if __name__ == "__main__":
    unittest.main()
