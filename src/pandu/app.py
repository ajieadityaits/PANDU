"""Loop aplikasi webcam PANDU."""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

from .camera import open_camera, scan_cameras
from .config import Config, load_config
from .decision import DecisionEngine
from .detector import YoloDetector
from .speech import SpeechWorker
from .stream import LatestFrameReader, droidcam_url, is_network_source
from .visualizer import draw_frame


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="PANDU - deteksi objek dan informasi arah melalui suara."
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Lokasi berkas konfigurasi YAML.",
    )
    parser.add_argument(
        "--source",
        help="Indeks kamera (mis. 0), path video, atau URL stream (mis. http://IP:4747/video).",
    )
    parser.add_argument(
        "--droidcam",
        metavar="IP",
        help="Pakai kamera HP lewat Wi-Fi dari aplikasi DroidCam, mis. --droidcam 192.168.1.5",
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        help="Pilih indeks webcam secara eksplisit (fallback/diagnostik).",
    )
    parser.add_argument(
        "--camera-name",
        help='Pilih webcam berdasarkan sebagian nama, misalnya "C920" atau "Logitech".',
    )
    parser.add_argument(
        "--list-cameras",
        action="store_true",
        help="Cari webcam yang tersedia lalu keluar.",
    )
    parser.add_argument("--model", help="Override model, mis. yolo11n.pt.")
    parser.add_argument("--no-speech", action="store_true", help="Matikan keluaran suara.")
    return parser


def parse_source(value: str | None, default_camera: int | str) -> int | str:
    if value is None:
        return default_camera
    try:
        return int(value)
    except ValueError:
        return value


def run(
    config: Config,
    source: int | str,
    model_override: str | None = None,
    camera_index_override: int | None = None,
    camera_name_override: str | None = None,
) -> int:
    try:
        import cv2
    except ImportError:
        print("[ERROR] OpenCV belum terpasang. Jalankan: pip install -r requirements.txt")
        return 2

    is_camera_source = isinstance(source, int) or str(source).lower() == "auto"
    if is_camera_source:
        explicit_index = camera_index_override
        if explicit_index is None and isinstance(source, int):
            explicit_index = source
        opened_camera = open_camera(
            cv2,
            config.app,
            index_override=explicit_index,
            name_override=camera_name_override,
        )
        if opened_camera is None:
            requested = explicit_index
            if requested is None:
                requested = camera_name_override or config.app.camera_name or "otomatis"
            print(f"[ERROR] Webcam tidak ditemukan/dapat dibuka (pilihan: {requested}).")
            print("[SARAN] Jalankan: python main.py --list-cameras")
            print("[SARAN] Tutup Camera/Zoom/Teams, cabut-pasang webcam, lalu coba lagi.")
            if "droid" in str(requested).lower():
                print_droidcam_hints()
            return 3
        capture = opened_camera.capture
        print(
            f"[INFO] Webcam aktif: {opened_camera.name} | indeks {opened_camera.index} "
            f"| backend {opened_camera.backend}."
        )
    elif is_network_source(source):
        print(f"[INFO] Menghubungkan ke stream {source} ...")
        raw_capture = cv2.VideoCapture(source)
        if not raw_capture.isOpened():
            print(f"[ERROR] Stream tidak dapat dibuka: {source}")
            raw_capture.release()
            print_droidcam_hints()
            return 3
        capture = LatestFrameReader(raw_capture)
        print("[INFO] Stream aktif.")
    else:
        capture = cv2.VideoCapture(source)
        if not capture.isOpened():
            print(f"[ERROR] File video tidak dapat dibuka: {source}")
            capture.release()
            return 3

    # Sumber langsung (webcam/stream) boleh sesekali gagal baca, misalnya saat
    # sinyal Wi-Fi DroidCam tersendat. File video berhenti di frame gagal pertama.
    is_live_source = is_camera_source or is_network_source(source)
    max_consecutive_failures = 30 if is_live_source else 1
    consecutive_failures = 0

    model_name = model_override or config.model.name
    print(f"[INFO] Memuat model {model_name}...")
    try:
        detector = YoloDetector(
            model_name=model_name,
            confidence_threshold=config.model.confidence_threshold,
            image_size=config.model.image_size,
            device=config.model.device,
        )
    except Exception:
        capture.release()
        raise
    engine = DecisionEngine(config.decision, config.classes, config.translations)
    speaker = SpeechWorker(
        enabled=config.speech.enabled,
        backend=config.speech.backend,
        rate=config.speech.rate,
        volume=config.speech.volume,
        queue_size=config.speech.queue_size,
    )

    speaker.start()
    if config.speech.enabled:
        print(f"[INFO] Backend suara: {speaker.selected_backend}.")
    status_message = "PANDU siap"
    previous_time = time.perf_counter()
    smoothed_fps = 0.0
    print("[INFO] Aplikasi berjalan. Tekan Q atau Esc untuk keluar, S untuk menyimpan gambar.")

    try:
        while True:
            ok, frame = capture.read()
            if not ok or frame is None:
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    if is_live_source:
                        print("[ERROR] Kamera/stream berhenti mengirim gambar.")
                    else:
                        print("[INFO] Frame berakhir atau tidak dapat dibaca.")
                    break
                if (cv2.waitKey(30) & 0xFF) in (ord("q"), 27):
                    break
                continue
            consecutive_failures = 0

            detections = detector.detect(frame)
            height, width = frame.shape[:2]
            candidates = engine.create_candidates(detections, width, height)
            alert = engine.select_alert(detections, width, height)
            if alert is not None:
                status_message = alert.message
                queued = speaker.say(alert.message)
                queue_status = "TTS masuk antrean" if queued else "TTS tidak masuk antrean"
                print(f"[ALERT] {alert.message} [{queue_status}]")

            current_time = time.perf_counter()
            instant_fps = 1.0 / max(current_time - previous_time, 1e-9)
            smoothed_fps = instant_fps if smoothed_fps == 0 else (0.9 * smoothed_fps + 0.1 * instant_fps)
            previous_time = current_time

            annotated = draw_frame(
                frame=frame,
                detections=detections,
                candidates=candidates,
                left_boundary=config.decision.left_boundary,
                right_boundary=config.decision.right_boundary,
                fps=smoothed_fps,
                status_message=status_message,
                show_fps=config.app.show_fps,
            )
            cv2.imshow(config.app.window_title, annotated)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("s"):
                saved_path = save_capture(annotated)
                status_message = f"Gambar disimpan: {saved_path.name}"
                print(f"[INFO] {status_message}")
    except KeyboardInterrupt:
        print("\n[INFO] Dihentikan oleh pengguna.")
    finally:
        capture.release()
        cv2.destroyAllWindows()
        speaker.stop()
    return 0


def print_droidcam_hints() -> None:
    print("[SARAN] Kamera HP via DroidCam:")
    print("        1. Buka aplikasi DroidCam di HP; catat 'WiFi IP' dan port (biasanya 4747).")
    print("        2. HP dan laptop harus di jaringan Wi-Fi yang sama.")
    print("        3. Cara webcam virtual: buka DroidCam Client di laptop, klik Start/Connect,")
    print('           lalu jalankan: python main.py --camera-name "DroidCam"')
    print("        4. Cara langsung (tanpa driver): TUTUP DroidCam Client di laptop, lalu")
    print("           jalankan: python main.py --droidcam IP_HP   (mis. 192.168.1.5)")
    print("        Tes dulu di browser: http://IP_HP:4747/video harus menampilkan gambar.")


def save_capture(frame: Any) -> Path:
    import cv2

    output_dir = PROJECT_ROOT / "captures"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    output_path = output_dir / f"pandu-{timestamp}.jpg"
    cv2.imwrite(str(output_path), frame)
    return output_path


def print_available_cameras(config: Config) -> int:
    try:
        import cv2
    except ImportError:
        print("[ERROR] OpenCV belum terpasang. Jalankan: pip install -r requirements.txt")
        return 2

    print("[INFO] Mengambil nama dan identitas perangkat kamera...")
    cameras = scan_cameras(cv2, config.app)
    if not cameras:
        print("[ERROR] Tidak ada webcam yang dapat menghasilkan frame.")
        return 3
    print("Kamera yang terdeteksi:")
    for camera in cameras:
        usb_id = ""
        if camera.vid is not None and camera.pid is not None:
            usb_id = f" | USB {camera.vid:04X}:{camera.pid:04X}"
        resolution = f" | {camera.width}x{camera.height}" if camera.width else ""
        print(
            f"  [{camera.backend}] indeks {camera.index}: {camera.name}"
            f"{usb_id}{resolution}"
        )
    print('Gunakan: python main.py --camera-name "SEBAGIAN NAMA"')
    print("Pilihan indeks tetap tersedia: python main.py --camera-index NOMOR")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.no_speech:
            config.speech.enabled = False
        if args.list_cameras:
            return print_available_cameras(config)
        if args.droidcam:
            source: int | str = droidcam_url(args.droidcam)
        else:
            source = parse_source(args.source, config.app.camera_index)
        return run(config, source, args.model, args.camera_index, args.camera_name)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"[ERROR] {exc}")
        return 1
