# LinguaPlay — implementasi awal

Tujuan: aplikasi desktop Windows untuk menerjemahkan sebelum bermain melalui adapter format, serta overlay OCR sebagai alternatif. Instruksi pengguna untuk melanjutkan implementasi menjadi otorisasi pelaksanaan langsung.

Keputusan implementasi: Python 3.11 + PySide6, Windows OCR lokal, layanan terjemahan kompatibel OpenAI atau LibreTranslate yang dikonfigurasi pengguna. Kunci API hanya disimpan di memori. Tidak mengunggah diagnostik otomatis.

Cakupan awal: deteksi berdasarkan isi untuk SRT, WebVTT, JSON dengan objek `strings` berisi ID dan nilai string. Format arsip game dilaporkan tetapi tidak dimodifikasi. Dukungan ini adalah dukungan format, bukan sertifikasi kompatibilitas suatu game. Uncharted belum didukung.

Alur patch: pilih folder, pindai, pilih file, terjemahkan, tinjau, pasang, pulihkan. Pertahankan encoding, newline, timestamp, ID dan token format. Periksa perubahan file sebelum memasang. Simpan backup byte asli dan jurnal; rollback jika pemasangan sebagian gagal. Pemulihan menolak file yang berubah setelah pemasangan.

OCR: pilih area pada layar utama, Windows OCR sesuai paket bahasa terpasang, baca dan terjemahkan dalam worker, tampilkan overlay click-through di luar area tangkapan, simpan cache terjemahan lokal, tombol berhenti di jendela utama. Game perlu borderless/windowed. Tidak ada audio.

Desain: permukaan terang kebiruan, sidebar biru tinta, aksen biru, Segoe UI, daftar file dan pratinjau bersebelahan. Bahasa antarmuka Indonesia. Status dukungan dan kegagalan harus eksplisit.

## Rencana
- [x] 1. Adapter dan pemindaian: uji gagal dahulu untuk roundtrip byte, timing, JSON ketat, format rusak dan symlink; implementasi `adapters.py`.
- [x] 2. Terjemahan dan transaksi: uji proteksi token, cache sesuai konfigurasi, validasi respons, patch/restore, konflik dan rollback; implementasi `translation.py`, `patches.py`.
- [x] 3. Desktop dan OCR: implementasi UI worker, pemilihan area dan overlay; uji OCR pada gambar fixture, UI offscreen dan alur patch fixture.
- [x] 4. Distribusi: panduan Indonesia, contoh data, launcher dan build portable; jalankan seluruh pengujian dan smoke executable.

## Risiko yang diuji
File berubah setelah pemindaian; variabel terjemahan rusak; respons API tidak lengkap; pemasangan berhenti separuh; restore menimpa update game. Batas ukuran/pemindaian mencegah pembacaan arsip besar. JSON sembarang tidak boleh dianggap subtitle.

## Catatan eksekusi
Workspace kosong, tidak ada checkout Git yang perlu diisolasi. Implementasi dan artefak pengguna di outputs/LinguaPlay; environment/build sementara di work. Uji layanan menggunakan server lokal fixture; kualitas terjemahan model pengguna dan kompatibilitas game nyata tidak dapat disimpulkan dari fixture.

Task 1–3 selesai: seluruh uji unit, integrasi API fixture, UI, adapter tambahan dan Windows OCR lulus. Review independen menemukan serialisasi JSON mengubah presisi metadata dan scan gagal mempertahankan target lama; keduanya diperbaiki dengan regression test. JSON sekarang menggunakan penggantian span literal teks saja. Pemindaian menghapus seluruh target/aksi lama sebelum memulai.

Ruling: serializer patch menerima mapping parsial untuk penggunaan developer, mempertahankan teks yang tidak dipetakan. UI menyiapkan seluruh entri dari setiap file pilihan. Tidak ada klaim dukungan game khusus hanya karena ekstensi cocok.

Distribusi: DLL ICU yang tidak kompatibel dari PATH alat lain sempat terambil oleh PyInstaller. Diagnosis ekspor simbol dan percobaan terkontrol memastikan penyebabnya. Build release membatasi PATH ke Python dan direktori sistem. Runtime EXE diuji ulang setelah build bersih.
