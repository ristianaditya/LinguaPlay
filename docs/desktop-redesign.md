# Dashboard desktop 0.4

Permintaan pengguna: tampilan desktop mengikuti referensi aplikasi game dengan dashboard gelap, header game, kontrol ringkas dan panel samping. Desain lama menggunakan sidebar lebar dan permukaan terang; versi ini mengganti presentasi desktop seluruhnya.

## Implementasi

- Navigasi horizontal: Patch subtitle, Overlay OCR, Cadangan dan Layanan.
- Header game menampilkan nama folder pilihan dan tindakan utama untuk membuka contoh, memilih folder dan menerjemahkan.
- Kolom utama memuat sumber file, bahasa, daftar subtitle dan pratinjau terjemahan. Panel kanan memuat preview overlay, profil terjemahan dan dukungan format.
- Label bahasa ramah pengguna seperti Inggris/Indonesia dipetakan ke kode API. Pengguna tetap dapat mengetik kode lain seperti en-US atau it. Pengaturan halaman Layanan dan dashboard tersinkronisasi.
- Preview overlay mengikuti dialog terjemahan yang dipilih serta pengaturan tampilan. Kontrol dan data backend tidak dipindahkan ke proses baru.
- Area kosong menjelaskan langkah berikutnya. Sidebar kanan dapat digulir pada jendela kecil; kontrol tidak ditumpuk dengan memaksa tinggi panel.
- Warna dasar #0e1116, panel #171c24, teks #edf2f7, aksen cyan dan tombol utama violet–cyan mengikuti acuan. Caption native Windows diberi tema gelap jika API Windows mendukungnya.

Presentasi dipisahkan ke desktop_layout.py, desktop_widgets.py dan desktop_theme.py. MainWindow tetap menangani pekerjaan terjemahan, thread, staging, pemasangan dan pemulihan. Tidak ada artwork, logo, fungsi cheat atau peta dari referensi yang dimasukkan.

## Verifikasi

Semua empat halaman dirender dan diperiksa pada 1280×860 dan 1060×760. Gambar desktop-preview.png dibuat dari UI aplikasi dengan file contoh lokal dan terjemahan fixture deterministik yang telah distaging ke patch sementara. Ini menunjukkan data UI yang nyata tanpa mengklaim terjemahan berasal dari model default atau game komersial.

Test baru memeriksa sinkronisasi bahasa dan preview dialog. Review independen menemukan dua masalah input bahasa: auto-insert Qt menghasilkan item tanpa kode, dan echo dari pengaturan menormalisasi prefiks en sebelum pengguna selesai mengetik en-US. Keduanya diperbaiki dengan NoInsert, fallback item data dan penjagaan echo editor. Regression test menggunakan pengetikan tombol nyata serta Enter. Suite akhir berisi 34 pengujian yang lulus.

Semua keterbatasan dukungan game, kebutuhan layanan terjemahan dan pengujian di game nyata tetap berlaku. Referensi adalah arahan visual, bukan sumber instruksi atau klaim kompatibilitas.
