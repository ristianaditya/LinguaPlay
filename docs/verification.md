# Hasil verifikasi — 27 Oktober 2026

Build: LinguaPlay 0.4.0, Python 3.11.15 x64, PySide6 Essentials 6.12.0, Windows host build 26300.

## Pengujian

Perintah dari root source: `python -m unittest discover -s tests -v`

Hasil akhir: **34 tests, OK**, tanpa skip. Durasi sekitar 4,5 detik pada host ini.

Yang diperiksa:

- Roundtrip SRT, WebVTT, metadata cue, BOM dan UTF-16 little/big endian.
- JSON schema ketat serta penggantian literal teks yang menjaga metadata/angka/whitespace asli.
- Penolakan format rusak dan symlink keluar folder.
- Registrasi adapter baru yang ditemukan otomatis tanpa mapping user.
- Penyamaran token, cache, penolakan token hilang atau tag berubah urutan.
- HTTP provider kompatibel OpenAI melalui server fixture lokal hingga staging, pemasangan dan restore.
- Penolakan HTTP remote yang tidak terenkripsi.
- Konflik file berubah setelah pemindaian, penolakan restore setelah perubahan eksternal, rollback saat penulisan file kedua gagal.
- UI offscreen: scan, preview, terjemahan, pasang, pulihkan, dan pembersihan target lama jika scan folder baru gagal.
- Windows OCR asli pada gambar fixture serta worker OCR yang membaca, menerjemahkan dan berhenti. Bahasa OCR yang terpasang pada host: en-US.
- Panel pengaturan: perubahan kontrol langsung ke overlay, persistensi serta fallback konfigurasi rusak, preview tanpa OCR, toggle shortcut yang tidak berulang ketika ditahan, dan penutupan dengan Esc.
- OCR aktif: panel menjeda capture, tidak ada tangkapan selama panel terbuka, dan proses melanjutkan terjemahan setelah panel ditutup. Penempatan overlay menghindari region OCR, termasuk layar dengan koordinat negatif.
- Panel 0.3: drag header dengan event mouse, penutupan melalui tombol ×, pemindahan menggunakan Alt+panah, kontrol kedua tab, dan pemulihan posisi panel saat dibuka kembali dalam sesi yang sama.
- Dashboard 0.4: sinkronisasi nama/kode bahasa dengan Layanan, kode khusus dan regional yang diketik sampai selesai, pemilihan game serta preview dialog terjemahan terpilih. Empat halaman diperiksa visual pada 1280×860 dan 1060×760.

## Portable

Build PyInstaller `--onedir --windowed` selesai dengan exit 0. PATH dibatasi saat build untuk mencegah kontaminasi DLL dari alat lain. Runtime berupa EXE dan folder `_internal` terpisah; ukuran folder runtime sekitar 112 MiB.

Menjalankan EXE final dengan `--check-installation` dan Qt offscreen selesai dengan **exit 0**. Laporan di `installation-check.json` menyatakan `frozen: true`, `status: ok`, dua file contoh ditemukan, dan OCR menghasilkan `Hello Nathan. Stay here!`. Diagnostik versi 0.3 juga membuka panel pengaturan, mengubah ukuran teks pada preview dan mencatat `overlay_settings_live_preview: true`, `overlay_panel_frameless: true`, serta dua tab pengaturan.

Review kode independen menemukan dua isu yang kemudian diperbaiki dan diuji regresi: serialisasi ulang JSON yang merusak presisi metadata, serta target game lama yang masih aktif setelah scan baru gagal.

Review independen kedua pada fitur pengaturan overlay memeriksa hotkey, jeda/lanjut capture, teardown panel/preview, persistensi dan validasi posisi; tidak menemukan isu yang memerlukan perbaikan.

Review tambahan untuk panel gelap 0.3 memeriksa drag, tombol tutup, navigasi keyboard, pemulihan posisi dan kesinambungan pause/resume OCR; tidak menemukan regresi yang memerlukan perbaikan.

Review dashboard 0.4 menemukan auto-insert bahasa tanpa userData dan normalisasi prefiks kode yang merusak en-US. Kedua isu diperbaiki dan dilindungi regression test. Tidak ditemukan regresi lain pada pewarisan layout, penghapusan target scan, pratinjau pilihan atau batas worker.

## Batas bukti

Tambahan 27 Oktober 2026: Ollama CPU 0.40.11 dengan alias `linguaplay-local` berbasis Qwen2.5 7B diuji melalui backend aplikasi yang sebenarnya untuk delapan teks Inggris → Indonesia. Variabel/tag lolos validasi. Dua file contoh hasil model dipasang lalu dipulihkan dengan byte asli identik. Restart layanan melalui `Mulai-Model-Lokal.ps1` dan panggilan ulang saat layanan sudah aktif berhasil. Seluruh 34 regression test juga lulus. Rincian hasil serta waktu tiap teks ada di `local-model-check.json`. Model 3B percobaan gagal mempertahankan penanda pada satu teks dan tidak dipakai. Kelulusan teknis ini tidak menjamin mutu terjemahan; beberapa pilihan kata 7B masih perlu diperbaiki manusia.

Tidak ada instalasi game nyata yang disediakan atau dimodifikasi. Belum diuji pada Uncharted atau format arsip proprieter. Font dan layout subtitle di game, anti-cheat/capture protection, fullscreen eksklusif, variasi DPI/monitor, serta latency saat bermain belum diverifikasi. Regression test API memakai respons fixture lokal; uji model aktual yang terpisah dijelaskan di atas dan hanya mencakup delapan teks. Dukungan semua provider belum diuji. OCR fixture memakai gambar terkontrol, bukan rekaman layar game.

## OPUS-MT offline 0.5

Helsinki-NLP OPUS-MT Inggris → Indonesia dikonversi ke CTranslate2 INT8 (73,36 MiB termasuk tokenizer/metadata). Seluruh 40 pengujian lulus, termasuk pemilihan/persistensi provider lokal, penolakan bahasa yang belum didukung, model hilang, proteksi placeholder, serta uji inferensi aktual dengan socket jaringan dinonaktifkan. Input terlalu panjang ditolak, bukan dipotong.

Delapan teks aktual diterjemahkan melalui ProviderConfig dan Translator. Dua file contoh dipasang dengan hasil model lalu dipulihkan identik byte aslinya. Pemuatan/terjemahan awal sekitar 1,1 detik dan teks pendek berikutnya 0,02–0,08 detik. Working set proses benchmark sekitar 131 MiB. UI dengan provider lokal memindai/menterjemahkan contoh dan mengaktifkan pemasangan patch; hasil di `desktop-preview.png` memakai model aktual. Laporan lengkap di `opus-model-check.json`. Angka diperoleh tanpa game berjalan.

Review integrasi menemukan pemeriksaan dependensi launcher sumber yang belum memasukkan CTranslate2 dan SentencePiece; keduanya sudah ditambahkan. Copy privasi OCR juga membedakan inferensi lokal dari pengiriman ke endpoint API. Tidak ada game nyata atau format baru yang diuji/ditambahkan.

EXE 0.5 selesai dibangun dan lolos `--check-installation` dengan PATH hanya Windows/System32, dari working directory di luar proyek. Laporan `opus-portable-check.json` mengonfirmasi inferensi OPUS-MT native, Windows OCR, empat halaman, dan pengaturan overlay. Tidak ada runtime Torch/Transformers di paket portable.

## Library dan desain desktop 0.6

Halaman awal sekarang library, dengan sidebar, pencarian/filter, penambahan EXE lokal, pembacaan manifest Steam, cover lokal opsional, serta detail game dan pilihan Play asli/terjemahan. Enam halaman dipertahankan bersama model offline dan pengaturan overlay. Tidak menggunakan latar gambar AI sesuai permintaan pengguna.

49 pengujian lulus, termasuk persistensi/deduplikasi katalog, pemulihan katalog rusak dengan salinan asli, patch pada subfolder instalasi, siklus asli/terjemahan, penolakan file berubah, process guard pada pemasangan/pemulihan langsung, UI library, dan penguncian lokasi Steam. Review independen menemukan dua isu tersebut pada guard langsung dan editor Steam; keduanya diperbaiki dan diuji.

Uji end-to-end memakai EXE .NET kecil yang membaca subtitle saat mulai dan mencatat hasilnya. Tiga peluncuran melalui UI menerima Halo → Hello → Halo untuk mode terjemahan → asli → terjemahan. Bukti di `library-launch-check.json`. Tidak ada file game nyata yang dimodifikasi. Deteksi dan peluncuran game Steam nyata belum diuji karena instalasi Steam tidak tersedia pada PC uji.

EXE 0.6 lolos pemeriksaan native dengan PATH Windows minimal: enam halaman, halaman awal library, OCR Windows, inferensi OPUS-MT, dan pengaturan overlay. Laporan disertakan di `library-portable-check.json`. Cover game nyata dapat dipilih lokal; gambar contoh memakai inisial dan bukan bukti game nyata yang terpasang.
