# Menambahkan dukungan format / game

User memilih folder; registry adapter memilih pemroses menurut ekstensi kandidat, kemudian **reader wajib memvalidasi isi/signature dan versi**. Ekstensi hanya menyaring kandidat. Reader boleh menolak dengan `ValueError`; file tidak pernah dipasang jika validasi gagal.

Adapter bawaan berada di `linguaplay/adapters.py`. API ekstensi pengembang:

```python
from linguaplay.adapters import register_adapter, Document, Entry

def read_custom(path):
    raw = path.read_bytes()
    # Periksa signature, versi, struktur dan batas ukuran terlebih dahulu.
    # Parse ID, teks dan metadata; jangan menebak semua string sebagai dialog.
    # Untuk format teks berbasis span:
    text = raw.decode('utf-8')
    if not text.startswith('DIALOG/1\n'):
        raise ValueError('Signature/versi tidak didukung')
    return Document(path, 'Example dialog v1', raw, text, 'utf-8',
                    [Entry('cue:1', text[9:])], [(9, len(text))])

register_adapter('example-dialog-v1', ('.dialog',), read_custom)
```

Import modul pendaftaran di startup aplikasi, lalu rilis build baru. Registry tidak mengunduh atau menjalankan plugin dari internet. Contoh di atas menjelaskan protokol; bukan adapter untuk sebuah game nyata.

Untuk kontainer biner, buat kelas document dengan atribut `path`, `format`, `raw`, `entries`, properti `sha256`, serta metode `render(mapping) -> bytes`. Writer harus mempertahankan ID, metadata, kompresi, offset, encoding dan checksum kontainer. Reader harus dapat membaca hasil writer dari file staging dengan ekstensi aslinya. Sistem patch menggunakan antarmuka ini tanpa mengetahui format internal. Tidak ada dukungan kontainer biner yang dibundel dalam 0.1.

Sebelum mengaktifkan adapter untuk game:

1. Kumpulkan fixture kecil yang boleh digunakan, beserta versi game.
2. Uji penolakan signature/versi yang salah dan input terpotong.
3. Uji `render({})` identik byte dengan sumber.
4. Uji perubahan dialog, tanpa mengubah ID, timing dan variabel.
5. Baca ulang hasil writer dan cocokkan semua ID/teks.
6. Uji pasang, rollback dan restore dengan file yang berubah.
7. Uji game sungguhan memuat hasil; cek font, panjang teks, konteks dan update game.

Adapter identitas game dapat memakai fingerprint executable dan versi untuk membatasi dukungan. Registry awal masih berbasis format; daftar executable di diagnostik adalah petunjuk, bukan klaim game telah dikenali/disertifikasi.

Format ambigu atau build baru harus ditolak dengan penjelasan. User dapat tetap menggunakan OCR. Ekspor diagnostik adalah alat bantu pengembang, bukan generator otomatis reader/writer.
