# LinguaPlay 0.6 — penerjemah game untuk Windows

Aplikasi desktop dengan dua mode: terjemahkan file subtitle sebelum bermain, atau baca subtitle layar melalui overlay OCR. Tidak ada pemrosesan audio.

## Mulai dari library game

1. Ekstrak seluruh paket ZIP dan buka **Jalankan.cmd**.
2. Di **Library game**, pilih **Deteksi Steam** atau **Tambah game**. Penambahan manual memerlukan nama, file EXE, dan folder instalasi; cover bersifat opsional.
3. Klik game untuk membuka detail. **Siapkan terjemahan** membuka pemindaian subtitle pada folder game tersebut. Terjemahkan dan tinjau hasilnya.
4. Pada detail game pilih **Mainkan versi asli** atau **Mainkan dengan terjemahan**, lalu **Play**. Mode terjemahan tersedia setelah ada patch. Mengubah dropdown saja belum mengubah file.
5. Untuk format subtitle yang belum didukung, gunakan versi asli dan **Buka overlay OCR**. Jalankan game terlebih dahulu, lalu pilih area subtitle ketika game sudah tampil.

## Library dan cara kerja Play

Library menyimpan game di `%LOCALAPPDATA%/LinguaPlay/library.json`. Deteksi Steam membaca manifest instalasi lokal, bukan akun atau riwayat cloud. Steam harus terpasang untuk meluncurkan game Steam. Deteksi launcher lain belum tersedia; tambahkan EXE-nya secara manual. Lokasi game Steam mengikuti manifest dan tidak bisa diubah melalui editor.

**Atur game** dapat mengganti nama serta cover lokal. Untuk game EXE, pilih folder instalasi yang mencakup EXE dan file subtitle; misalnya pilih folder game induk jika EXE ada di `bin/`. File cover disalin ke folder data LinguaPlay. Tanpa cover, tampil inisial judul. Aplikasi tidak mengunduh gambar atau memakai latar ilustrasi AI.

Status hanya mencerminkan patch yang dikelola LinguaPlay, bukan pemeriksaan semua mod atau terjemahan dari program lain. Status dibaca dari jurnal patch: **Versi asli**, **Patch siap dimainkan**, **Terjemahan terpasang**, atau **Perlu pemulihan**. Filter “Dengan patch” juga mencakup patch tersimpan yang belum aktif. Library tidak menyatakan suatu game didukung hanya karena EXE berhasil ditambahkan.

**Play versi asli** memulihkan patch LinguaPlay yang aktif pada game tersebut sebelum menjalankan EXE/Steam. **Play dengan terjemahan** menggunakan patch terbaru, memasangnya bila perlu, dan memeriksa hash file patch aktif. Patch yang sudah dipulihkan dapat dipasang kembali tanpa menerjemahkan ulang. Pemasangan/pemulihan juga dapat dilakukan melalui halaman Terjemahan/Cadangan. Game yang terdeteksi masih berjalan atau file yang diubah update/mod lain membuat perubahan ditolak. Proses yang tidak dapat diperiksa oleh Windows dapat membatasi deteksi; tetap tutup game sebelum mengubah subtitle.

Pemilihan mode adalah perubahan file yang bertahan setelah game ditutup. Bila peluncuran game ditolak launcher/DRM, patch yang sudah diterapkan tetap mengikuti mode pilihan; lihat status dan Cadangan. Game dipasang oleh Steam bisa membuka launcher tambahan. Tombol Play hanya mengirim permintaan peluncuran dan tidak menjamin game selesai dimuat.

Menghapus game dari library tidak menghapus instalasi, cover tersimpan, atau cadangan patch, dan tidak otomatis memulihkan subtitle aktif. Jika library rusak, salinan byte aslinya dipertahankan sebagai `library-unreadable-*.json`; game dapat ditambahkan kembali. Contoh dalam gambar/laporan uji menggunakan EXE uji, bukan game yang dipasang diam-diam pada perangkat Anda.

## Paket offline

Paket lengkap menyertakan model OPUS-MT Inggris → Indonesia, tokenizer, dan runtime CPU. Tidak perlu memasang Qwen, Ollama, Python, atau memakai API key di perangkat tujuan. Jangan memindahkan EXE sendiri; folder `_internal` harus tetap di sebelahnya. Windows 10/11 x64 diperlukan. Paket bahasa Windows OCR untuk bahasa sumber harus tersedia bila memakai OCR. Build belum ditandatangani secara digital.

Jika menjalankan dari sumber tanpa portable, gunakan Python 3.11 x64 dan `requirements.txt`. Model ada di `models/opus-mt-en-id-int8`. Launcher membuat `.venv` dan memasang dependensi bila perlu; tahap pemasangan dependensi memerlukan internet.

## Penerjemah lokal OPUS-MT

Pilih **OPUS-MT lokal** untuk memproses teks sepenuhnya di PC. Model hanya mendukung **Inggris (en) → Indonesia (id)**; pasangan lain ditolak dengan pesan, tanpa fallback ke layanan internet. Endpoint, model API, dan kunci API tidak dipakai. Riwayat pengaturan provider API tetap tersedia saat beralih kembali.

Ukuran paket model INT8 beserta tokenizer sekitar **73,4 MiB**.

Model sumber: [Helsinki-NLP/opus-mt-en-id](https://huggingface.co/Helsinki-NLP/opus-mt-en-id), lisensi Apache-2.0. Bobot dikonversi ke CTranslate2 INT8, tanpa pelatihan ulang. Runtime memakai dua thread CPU saat menerjemahkan. Model dimuat pada permintaan pertama dan tinggal di memori sampai aplikasi ditutup; tidak ada server terjemahan terpisah untuk mode ini. Saat diam tidak ada proses inferensi berulang. Model tetap memakai RAM selama aplikasi terbuka.

Variabel, tag, dan pemisah baris ditahan di luar model. Teks di antaranya diterjemahkan sebagai fragmen; ini menjaga format, tetapi dapat mengurangi konteks kalimat. Potongan dengan lebih dari 480 token ditolak agar teks tidak dipotong diam-diam. Cache dibedakan dari provider lain. Kualitas hasil tetap perlu diperiksa, terutama nama, istilah game, dan dialog yang bergantung konteks.

Uji delapan teks pendek tanpa game berjalan: pemuatan/terjemahan pertama sekitar **1,1 detik**, permintaan berikutnya **0,02–0,08 detik**. Working set seluruh proses uji sekitar **131 MiB**, bukan pengukuran RAM seluruh aplikasi desktop. Pengukuran ini bukan jaminan latency atau FPS saat game berjalan.

Metadata sumber, revisi, dan checksum ada di `models/opus-mt-en-id-int8/provenance.json`. Laporan pengujian aktual disertakan di `docs/opus-model-check.json`.

## Provider API opsional

- **OpenAI compatible**: gunakan endpoint seperti `http://127.0.0.1:11434/v1` untuk Ollama dengan model yang sudah dipasang, atau endpoint HTTPS layanan cloud Anda.
- **LibreTranslate**: endpoint misalnya `http://localhost:5000`; kunci API sesuai konfigurasi server.

Qwen/Ollama tidak dibundel ke ZIP. Pada PC ini Qwen dari pengaturan sebelumnya tetap terpasang, tetapi OPUS-MT tidak memakainya. `Jalankan.cmd` hanya menyalakan runtime Ollama yang sudah dikonfigurasi bila provider tersimpan adalah OpenAI compatible dengan endpoint localhost port 11434. Membuka EXE langsung melewati langkah startup Ollama. LibreTranslate tidak dijalankan otomatis.

Kunci API hanya di memori sampai aplikasi ditutup. Endpoint, model API, dan bahasa dapat disimpan. Provider API mengirim teks ke endpoint pilihan Anda. HTTP hanya diizinkan untuk localhost; endpoint luar komputer wajib HTTPS. Pengalihan HTTP ditolak agar kredensial tidak diteruskan ke host lain. OCR gambar berjalan lokal. Aplikasi tidak mengunggah folder game atau diagnostik otomatis.

## Patch subtitle

1. Tutup game. Pilih folder instalasi, atau subfolder bahasa, dan klik **Pindai**.
2. Periksa daftar file. Hapus centang file bahasa yang tidak ingin diganti. Pemindaian tidak menyimpulkan bahasa sumber; Anda menentukan kode bahasa di Layanan.
3. Klik **Terjemahkan pilihan**. Aplikasi membuat patch terpisah; file asli belum berubah.
4. Tinjau hasil di pratinjau (maksimal 500 dialog per file ditampilkan; semua dialog dalam file pilihan tetap diproses).
5. Klik **Pasang patch**. Buka game dan pilih slot bahasa yang file-nya diganti, misalnya English bila sumbernya English.
6. Buka **Cadangan**, pilih patch dan klik **Pulihkan pilihan** untuk mengembalikan byte asli.

Cadangan disimpan di `%LOCALAPPDATA%/LinguaPlay/patches`; jangan hapus sebelum memulihkan game. Cache terjemahan ada di `cache.sqlite`. Ulangi pemindaian setelah pemasangan/pemulihan atau update game. Patch disiapkan hanya untuk file yang dipilih. Pemasangan memeriksa checksum file asli, dan rollback jika salah satu penulisan gagal. Jurnal pemasangan/pemulihan terhenti tetap tersedia di Cadangan setelah aplikasi dibuka kembali. Jika file berubah akibat update/mod lain, aplikasi menolak menimpanya. Periksa konflik secara manual dengan backup; jangan mengganti hash di manifest.

Setiap file ditulis menggunakan penggantian atomik, tetapi satu paket multi-file tidak dapat menjadi satu transaksi filesystem. Game harus ditutup selama proses. File sementara dan jurnal dapat tertinggal jika listrik mati. Pemulihan dapat diulang selama file game masih cocok dengan hash asli atau hash patch. Folder game harus bisa ditulis oleh akun Windows Anda.

## Dukungan format saat ini

| Format | Batas dukungan |
|---|---|
| `.srt` | Cue bernomor dan timestamp valid |
| `.vtt` | Header WEBVTT, cue, metadata NOTE/STYLE/REGION dipertahankan |
| `.json` | Objek root `strings` berisi pasangan ID dan teks string; JSON umum tidak diproses |

UTF-8, UTF-8 BOM, UTF-16 dengan BOM. Batas 8 MiB per file dan 50.000 file per pemindaian. Arsip `.pak`, `.pck`, `.assets`, `.bundle`, `.loc`, `.dat`, dan format biner lain hanya masuk laporan kandidat belum didukung. Tidak ada dekripsi, ekstraksi arsip atau injeksi proses.

**Ini dukungan format, bukan jaminan kompatibilitas setiap game. Uncharted: Legacy of Thieves Collection belum didukung.** Game yang menyimpan subtitle dalam format tersebut dapat dipindai, tetapi penerimaan hasil patch, font, layout, dan integritas game perlu diuji pada game nyata. Teks dalam gambar/video tidak diganti. Metadata locale JSON tetap sama karena aplikasi mengganti isi slot bahasa yang ada. Writer hanya mengganti literal teks terpilih; whitespace, urutan ID dan representasi metadata lainnya dipertahankan persis.

Variabel, tag dan pemisah baris umum disamarkan sebelum dikirim, lalu diperiksa sebelum menyimpan. Sintaks engine yang tidak umum memerlukan adapter khusus. Terjemahan otomatis dapat salah konteks dan perlu ditinjau. Cache dibedakan menurut endpoint, provider, model serta pasangan bahasa; perubahan model dengan nama sama tidak otomatis membatalkan cache.

## Overlay OCR

1. Pastikan subtitle sumber di game aktif. Gunakan **borderless/windowed**.
2. Buka **Overlay OCR**. Pilih paket bahasa OCR yang cocok dengan teks sumber.
3. Klik **Pilih area & mulai**, lalu tarik area subtitle pada **layar utama**. Esc membatalkan pemilihan.
4. Overlay berada di luar area OCR untuk mencegah pembacaan hasil terjemahannya sendiri.
5. Tekan **Ctrl+Alt+F10**, atau kembali ke aplikasi dan klik **Hentikan OCR**.

### Pengaturan tampilan saat bermain

Tekan **Ctrl+Alt+O** untuk membuka atau menutup panel pengaturan di atas game. Aplikasi harus tetap berjalan. Panel ini juga dapat dibuka lewat **Atur tampilan overlay** dan tersedia sebagai pratinjau meskipun OCR belum aktif.

Versi 0.3 memakai menu gelap tanpa bingkai sistem, mengikuti acuan overlay game. Seret header **LinguaPlay** untuk memindahkan panel; posisi panel diingat selama aplikasi berjalan. Alternatif keyboard: **Alt + tombol panah** ketika panel aktif. Posisi panel dibatasi agar tetap berada di layar. Tombol **×**, Esc, atau Ctrl+Alt+O menutup panel dan melanjutkan OCR.

Tab **Subtitle** berisi pengaturan font, ukuran/warna teks dan latar. Tab **Posisi** berisi ukuran serta posisi subtitle. Memindahkan panel pengaturan berbeda dari memindahkan subtitle; posisi subtitle tetap diatur lewat tab Posisi.

- Ubah font, ukuran dan warna teks, warna/kepekatan latar, lebar, tinggi, serta posisi horizontal/vertikal.
- Perubahan langsung terlihat dan disimpan otomatis di `%LOCALAPPDATA%/LinguaPlay/overlay-settings.json`.
- Saat panel terbuka, OCR dijeda sebelum panel ditampilkan agar panel tidak dibaca sebagai subtitle. Menutup dengan Esc, Ctrl+Alt+O atau tombol **Kembali ke game** melanjutkan OCR otomatis.
- Subtitle tetap click-through sehingga klik di atas subtitle diteruskan ke game. Panel pengaturan menerima klik saat dibuka.
- Posisi overlay otomatis disesuaikan jika akan menutupi area OCR; jika tidak ada ruang, kecilkan ukuran overlay atau area tangkapan.

Panel mengubah tampilan **overlay LinguaPlay**, bukan font/posisi subtitle bawaan game yang sudah dipatch. Gunakan pengaturan game untuk subtitle bawaan. Overlay dan panel ditujukan untuk borderless/windowed; fullscreen eksklusif tidak dijamin. Fokus keyboard dapat berpindah dari game saat berinteraksi dengan panel; aplikasi tidak menjeda game secara otomatis.

Bahasa OCR yang tersedia mengikuti paket OCR Windows. Jika daftar kosong, tambahkan paket bahasa/OCR melalui Settings Windows. HDR, scaling, capture protection, font dekoratif, subtitle animasi, atau fullscreen eksklusif dapat mengganggu pembacaan. Multi-monitor awal ini hanya mendukung pemilihan area pada layar utama. OCR menunggu dua pembacaan yang sama; teks pendek dapat terlewat. Teks baru diterjemahkan berurutan; model lambat dapat menampilkan hasil yang terlambat. Ini belum memiliki jaminan latency. Pembatalan menunggu permintaan jaringan berjalan selesai atau timeout maksimal sekitar 30 detik per permintaan.

## Menambahkan dukungan game

Baca `docs/adapters.md`. Pengembang menambahkan adapter dengan pemeriksaan signature/versi, reader dan writer, serta fixture roundtrip. User tidak perlu mapping manual. Format baru tidak diproses berdasarkan tebakan. **Ekspor diagnostik** menghasilkan JSON lokal berisi nama/path relatif kandidat, signature 16 byte, executable yang ditemukan, dan alasan penolakan; laporan ini belum menambahkan adapter otomatis.

## Pengembangan dan verifikasi

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe main.py
```

OCR fixture memerlukan Windows dan paket English OCR; test tersebut akan dilewati bila paket English tidak tersedia. Pengujian integrasi memakai HTTP server lokal fixture, bukan layanan terjemahan komersial. Lihat `docs/verification.md` untuk hasil build yang diberikan.

Untuk build portable: instal `pyinstaller`, lalu dari folder ini jalankan:

```powershell
./build.ps1
python tools/collect_notices.py
```

Runtime pihak ketiga memiliki lisensi masing-masing. Qt/PySide6 menggunakan LGPL/GPL/commercial sesuai komponennya; notice distribusi disertakan di folder portable.

`build.ps1` membatasi PATH saat bundling agar DLL dari aplikasi lain tidak ikut terambil. Jika startup gagal, lihat `%LOCALAPPDATA%/LinguaPlay/startup-error.log`. Untuk memeriksa runtime tanpa game atau jaringan, jalankan `LinguaPlay.exe --check-installation C:\path\hasil`; laporan JSON dan gambar jendela disimpan ke folder tersebut. Setelah rebuild, sertakan kembali notice dependensi saat mendistribusikan paket.
# LinguaPlay

LinguaPlay adalah launcher penerjemah game offline untuk Windows. Profil game, glossary, translation memory, dan laporan kompatibilitas disimpan lokal. Scanner menandai game yang bisa dipatch dan game yang hanya aman dipakai dengan OCR; format proprietary tidak dibongkar secara otomatis.
