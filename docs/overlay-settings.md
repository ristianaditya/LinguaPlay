# Pengaturan overlay saat bermain — 0.2

Permintaan pengguna: panel pengaturan tampilan yang dapat dipakai ketika game berjalan. Implementasi tetap native PySide6. Hotkey Ctrl+Alt+O membuka/menutup panel tool always-on-top, Esc menutup, Ctrl+Alt+F10 menghentikan OCR. Tidak ada modifikasi subtitle bawaan game untuk fitur tampilan ini.

Panel nonmodal menyediakan font, ukuran/warna teks, warna/opasitas latar, lebar/tinggi dan posisi horizontal/vertikal. Perubahan langsung diterapkan ke overlay click-through dan disimpan atomik ke settings lokal. Preview bisa dibuka tanpa OCR aktif. Konfigurasi rusak dikembalikan ke default.

Keamanan pembacaan: event pause dan lock tangkapan memastikan capture yang sudah berjalan selesai sebelum panel ditampilkan. Worker tidak melakukan capture selama pause. Setelah panel ditutup, capture dilanjutkan setelah 180 ms untuk memberi compositor waktu menutup panel. Area subtitle selalu ditempatkan di luar region OCR; posisi kandidat dibatasi layar dan dipindahkan ke sisi region terdekat yang cukup ruang. Jika tidak ada ruang, perubahan ditolak dengan pesan.

Verifikasi: tes UI mengubah kontrol nyata, memeriksa pembaruan overlay/persistensi, menutup panel dengan Esc, dan memastikan hotkey tidak toggle berulang saat tombol ditahan. Tes worker memastikan tidak ada capture selama panel dijeda. Tes penempatan mencakup layar dengan origin negatif dan region penuh yang tidak menyisakan ruang.

Batas: memerlukan aplikasi tetap berjalan, target borderless/windowed, belum diuji dengan game nyata. Panel menerima fokus/klik saat dibuka; game tidak otomatis dijeda. Hasil rendering, polling hotkey, capture protection dan exclusive fullscreen mengikuti lingkungan Windows/game.

## Penyempurnaan 0.3 berdasarkan referensi pengguna

Panel memakai permukaan gelap #142120 dan teks #e6eeec, dengan aksen teal #50d5bb. Frame Windows diganti header buatan sendiri yang dapat diseret dan tombol tutup berlabel aksesibel. Font tetap Segoe UI, kontrol memiliki fokus keyboard, icon chevron/plus/minus SVG berwarna terang. Kontrol dibagi menjadi tab Subtitle dan Posisi agar panel lebih ringkas (lebar 364 DIP). Tombol Alt+panah memindahkan panel untuk pengguna keyboard. Pemindahan dibatasi ke available geometry layar, dan posisi terakhir dipertahankan selama sesi aplikasi.

Acuan screenshot dipakai untuk bentuk menu overlay, tanpa menyalin fungsi cheat, peta, merek, atau aset game pada gambar. Ini tetap window overlay native, tanpa injeksi proses game.

Pengujian baru: event mouse men-seret header memindahkan panel, tombol tutup header menutup panel, Alt+panah memindahkan panel, kontrol di kedua tab tetap memperbarui tampilan, dan posisi panel tetap sama setelah dibuka kembali. Preview PNG berasal dari render aplikasi sendiri, bukan komposit pada screenshot game pengguna.
