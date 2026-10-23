# PANDU

PANDU adalah prototipe pendeteksi objek dari webcam/video yang memberikan informasi arah **kiri, depan, atau kanan** melalui tampilan dan suara. Proyek ini ditujukan sebagai alat bantu eksperimental bagi penyandang disabilitas penglihatan.

> **Batas keselamatan:** aplikasi ini belum merupakan alat bantu mobilitas tervalidasi dan tidak menggantikan tongkat putih, anjing pemandu, pendamping, atau perangkat keselamatan resmi. Kata “depan” hanya menunjukkan sektor tengah gambar kamera, bukan jarak maupun jalur yang aman.

## Fitur MVP

- Deteksi objek menggunakan model Ultralytics `yolo11n.pt`.
- Penyaringan kelas yang relevan lewat `config.yaml`.
- Pembagian sektor kiri/depan/kanan berdasarkan titik tengah bounding box.
- Pemilihan satu objek terpenting berdasarkan kelas, sektor, luas box, dan confidence.
- Stabilisasi beberapa frame dan cooldown agar suara tidak berulang terus-menerus.
- Windows SAPI langsung pada thread terpisah agar ucapan berulang stabil dan loop kamera tetap berjalan.
- Pemulihan otomatis backend TTS jika driver suara mengalami error.
- Bounding box, confidence, arah, status pesan, dan FPS.
- Tombol `S` untuk menyimpan screenshot bukti pengujian ke folder `captures/`.
- Mendukung webcam maupun file video.
- Pemilihan Logitech berdasarkan nama perangkat dan USB Vendor ID `046D`.
- Pemindaian nama, VID/PID, indeks, dan backend kamera Windows.
- Tidak fallback diam-diam ke integrated webcam jika Logitech tidak ditemukan.

## Struktur proyek

```text
PANDU/
├── main.py                    # entry point
├── config.yaml                # model, threshold, kelas, dan pengaturan TTS
├── requirements.txt           # dependensi runtime
├── requirements-dev.txt       # dependensi unit test
├── setup_windows.bat          # setup otomatis Python Windows
├── run_windows.bat            # menjalankan aplikasi di Windows
├── src/pandu/
│   ├── app.py                 # loop webcam/video dan input keyboard
│   ├── camera.py              # pemindaian dan pemilihan webcam
│   ├── config.py              # membaca dan memvalidasi YAML
│   ├── decision.py            # zona, skor prioritas, stabilitas, cooldown
│   ├── detector.py            # adaptor inferensi YOLO
│   ├── domain.py              # tipe data Detection/Candidate/Alert
│   ├── speech.py              # antrean dan worker TTS
│   └── visualizer.py          # anotasi frame
└── tests/
    └── test_decision.py       # unit test logika inti
```

## Persyaratan

- Windows 10/11 64-bit.
- Python **3.10–3.12 64-bit**. Python 3.12 direkomendasikan.
- Webcam (untuk mode real-time).
- Koneksi internet pada eksekusi pertama untuk mengunduh bobot model.

GPU tidak wajib. Ultralytics dapat menggunakan CPU; performanya bergantung pada perangkat. Jangan mencantumkan FPS sebagai hasil laporan sebelum benar-benar diukur pada laptop pengujian.

## Instalasi Windows

### Cara otomatis

1. Buka folder `D:\PANDU`.
2. Klik dua kali `setup_windows.bat`.
3. Setelah instalasi selesai, klik dua kali `run_windows.bat`.

### Cara melalui PowerShell

```powershell
cd D:\PANDU
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

Jika PowerShell memblokir aktivasi virtual environment, jalankan langsung:

```powershell
.\.venv\Scripts\python.exe main.py
```

## Cara menjalankan

Webcam otomatis dan suara aktif. Konfigurasi bawaan mencari kamera Logitech berdasarkan nama perangkat atau USB Vendor ID `046D`:

```powershell
python main.py
```

Untuk melihat **nama perangkat, VID/PID, indeks, dan backend** kamera:

```powershell
python main.py --list-cameras
```

Pilih Logitech berdasarkan sebagian nama yang muncul, misalnya `C920`:

```powershell
python main.py --camera-name "C920"
```

Pemilihan indeks tetap tersedia untuk diagnostik, tetapi nama lebih aman karena urutan indeks dapat berbeda antar-backend:

```powershell
python main.py --camera-index 2
```

Tanpa suara (berguna untuk pengujian awal):

```powershell
python main.py --no-speech
```

Cara lama melalui `--source` juga tetap didukung:

```powershell
python main.py --source 1
```

File video:

```powershell
python main.py --source "D:\video-uji.mp4"
```

Model lain yang kompatibel dengan Ultralytics:

```powershell
python main.py --model yolo11s.pt
```

Kontrol aplikasi:

| Tombol | Fungsi |
|---|---|
| `Q` atau `Esc` | Keluar dengan aman |
| `S` | Simpan frame beranotasi ke `captures/` |

## Pengaturan penting

Semua pengaturan utama berada di `config.yaml`:

- `confidence_threshold`: confidence minimum deteksi.
- `camera_name`: sebagian nama kamera pilihan, default `"Logitech"`.
- `camera_vendor_id`: VID USB Logitech, default `"046D"`.
- `allow_camera_fallback`: jika `false`, integrated webcam tidak dipakai saat Logitech gagal ditemukan.
- `camera_index`: fallback lama atau pilihan eksplisit melalui CLI.
- `camera_scan_max_index`: indeks tertinggi yang diperiksa.
- `prefer_external_camera`: jika `true`, indeks `1` ke atas dicoba sebelum indeks `0`.
- `camera_backend`: default `dshow` agar nama dan indeks berasal dari backend yang sama.
- `image_size`: ukuran input inferensi YOLO.
- `cooldown_seconds`: waktu tunggu sebelum kelas+arah yang sama boleh diumumkan lagi.
- `stability_frames`: jumlah frame berturut-turut sebelum pengumuman.
- `classes`: kelas COCO yang ditampilkan dan bobot prioritasnya.
- `translations`: nama kelas dalam pesan bahasa Indonesia.
- `speech.enabled`: aktif/nonaktif TTS.
- `speech.backend`: `auto` menggunakan SAPI langsung di Windows; `pyttsx3` menjadi fallback lintas platform.

Hanya kelas yang tercantum pada bagian `classes` yang diumumkan. Konfigurasi bawaan juga mencakup objek uji umum seperti botol, gelas, buku, laptop, telepon genggam, meja, sofa, dan tanaman.

Bobot prioritas bukan pengukuran risiko ilmiah; nilainya adalah heuristik prototipe dan perlu dievaluasi bersama pengguna sasaran.

## Menjalankan unit test

```powershell
pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Unit test hanya memverifikasi logika program. Pengujian kamera, kualitas deteksi, FPS, dan TTS tetap harus dilakukan di perangkat aktual.

## Skenario uji awal

1. **Kursi di tengah:** pastikan label, box, arah “depan”, dan suara muncul.
2. **Webcam eksternal:** cabut/pasang Logitech, jalankan `--list-cameras`, lalu pastikan indeks yang dipilih menampilkan kamera Logitech.
3. **Geser objek:** pindahkan objek ke kiri/tengah/kanan dan periksa perubahan sektor.
4. **Cooldown:** tahan objek lebih dari 10 detik dan catat interval suara.
5. **Dua objek:** tampilkan kursi dan kendaraan (bisa memakai video) lalu periksa prioritas.
6. **Mode senyap:** jalankan `--no-speech` dan pastikan visual tetap bekerja.
7. **Sumber salah:** jalankan `--source 99` dan pastikan program memberi error tanpa crash panjang.
8. **Kondisi sulit:** uji pencahayaan redup, objek kecil, dan occlusion; dokumentasikan kegagalannya.

Tekan `S` pada setiap skenario penting untuk menyimpan bukti visual. Catat perangkat, resolusi kamera, model, threshold, FPS terlihat, kondisi cahaya, hasil aktual, dan kendala. Jangan membuat angka hasil yang belum diukur.

## Keterbatasan saat ini

- Model COCO bawaan tidak secara khusus mengenali lubang, kaca, permukaan tidak rata, atau tepi trotoar.
- Ukuran bounding box tidak diubah menjadi jarak meter.
- Tidak ada depth estimation, navigasi GPS, maupun penentuan jalur aman.
- Pembagian arah hanya berdasarkan posisi horizontal pada citra.
- Bahasa/voice TTS bergantung pada voice yang tersedia di Windows.
- Akurasi dipengaruhi pencahayaan, sudut kamera, occlusion, dan domain data.

## Data dan penggunaan bertanggung jawab

MVP menggunakan bobot pralatih dan label dataset COCO yang didistribusikan melalui Ultralytics; proyek ini tidak melatih model dengan dataset baru. Hindari merekam atau membagikan wajah dan lingkungan privat tanpa izin. Jika screenshot/video demonstrasi melibatkan orang lain, mintalah persetujuan dan lakukan penyamaran bila diperlukan.
