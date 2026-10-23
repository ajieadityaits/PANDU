import unittest
from pathlib import Path
import sys


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from pandu.camera import (
    CameraInfo,
    camera_candidates,
    matching_camera_devices,
    open_camera,
    parse_usb_id,
)
from pandu.config import AppConfig, Config, validate_config


class CameraSelectionTests(unittest.TestCase):
    def test_auto_prefers_external_indices(self):
        self.assertEqual(camera_candidates("auto", 3, True), [1, 2, 3, 0])

    def test_auto_can_prefer_internal_camera(self):
        self.assertEqual(camera_candidates("auto", 2, False), [0, 1, 2])

    def test_explicit_index_only_tries_selected_camera(self):
        self.assertEqual(camera_candidates(2, 5, True), [2])

    def test_invalid_camera_index_is_rejected(self):
        config = Config(app=AppConfig(camera_index="logitech"))
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_open_camera_skips_unavailable_index(self):
        fake_cv2 = FakeCv2(working_indices={2})
        config = AppConfig(
            camera_index="auto",
            camera_scan_max_index=3,
            camera_name=None,
            camera_vendor_id=None,
            allow_camera_fallback=True,
        )
        opened = open_camera(fake_cv2, config)

        self.assertIsNotNone(opened)
        self.assertEqual(opened.index, 2)
        self.assertEqual(fake_cv2.attempted_indices, [1, 2])

    def test_open_camera_falls_back_to_internal(self):
        fake_cv2 = FakeCv2(working_indices={0})
        config = AppConfig(
            camera_index="auto",
            camera_scan_max_index=2,
            camera_name=None,
            camera_vendor_id=None,
            allow_camera_fallback=True,
        )
        opened = open_camera(fake_cv2, config)

        self.assertIsNotNone(opened)
        self.assertEqual(opened.index, 0)
        self.assertEqual(fake_cv2.attempted_indices, [1, 2, 0])

    def test_logitech_is_selected_by_usb_vendor_id(self):
        fake_cv2 = FakeCv2(working_indices={0, 1})
        config = AppConfig(camera_name="Logitech", camera_vendor_id="046D")
        devices = [
            CameraInfo(0, "Integrated Camera", "DirectShow", 700, 0x04F2, 1),
            CameraInfo(1, "HD Pro Webcam C920", "DirectShow", 700, 0x046D, 2),
        ]

        opened = open_camera(fake_cv2, config, devices=devices)

        self.assertIsNotNone(opened)
        self.assertEqual(opened.index, 1)
        self.assertEqual(opened.name, "HD Pro Webcam C920")
        self.assertEqual(fake_cv2.attempted_indices, [1])

    def test_no_fallback_to_integrated_when_logitech_is_absent(self):
        fake_cv2 = FakeCv2(working_indices={0})
        config = AppConfig(
            camera_name="Logitech",
            camera_vendor_id="046D",
            allow_camera_fallback=False,
        )
        devices = [CameraInfo(0, "Integrated Camera", "DirectShow", 700, 0x04F2, 1)]

        opened = open_camera(fake_cv2, config, devices=devices)

        self.assertIsNone(opened)
        self.assertEqual(fake_cv2.attempted_indices, [])

    def test_name_override_has_priority_over_configured_vendor(self):
        devices = [
            CameraInfo(1, "Logitech StreamCam", "DirectShow", 700, 0x046D, 1),
            CameraInfo(2, "OBS Virtual Camera", "DirectShow", 700, None, None),
        ]

        matches = matching_camera_devices(devices, "OBS", None)

        self.assertEqual([camera.index for camera in matches], [2])

    def test_usb_id_accepts_hexadecimal_text(self):
        self.assertEqual(parse_usb_id("046D"), 0x046D)
        self.assertEqual(parse_usb_id("0x046d"), 0x046D)


class FakeFrame:
    shape = (720, 1280, 3)


class FakeCapture:
    def __init__(self, index, working):
        self.index = index
        self.working = working

    def isOpened(self):
        return self.working

    def set(self, _property, _value):
        return True

    def read(self):
        return (True, FakeFrame()) if self.working else (False, None)

    def release(self):
        return None


class FakeCv2:
    CAP_PROP_FRAME_WIDTH = 3
    CAP_PROP_FRAME_HEIGHT = 4
    CAP_DSHOW = 700
    CAP_MSMF = 1400
    CAP_ANY = 0

    def __init__(self, working_indices):
        self.working_indices = working_indices
        self.attempted_indices = []

    def VideoCapture(self, index, *_args):
        self.attempted_indices.append(index)
        return FakeCapture(index, index in self.working_indices)


if __name__ == "__main__":
    unittest.main()
