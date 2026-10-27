"""PSARC (zlib) archives holding Naughty Dog text tables, e.g. Uncharted PS4 core.psarc.

English text1/ps4/2.subtitles (dialogue) and 2.common (menus, HUD, prompts, objectives,
items) tables are exposed; the identical 7.* English variant follows. Every other member is copied
byte for byte; changed members are appended at the end with their own block entries, so
the original data layout (including padding between members) is never rewritten.
"""
from pathlib import Path
import math
import re
import struct
import zlib
from .adapters import Entry, digest, register_adapter

MAX_ARCHIVE_SIZE = 512 * 1024 * 1024
SOURCE_PREFIX = 'text1/ps4/2.'    # English
MIRROR_PREFIX = 'text1/ps4/7.'    # second English variant, patched where identical
TABLES = {'sub': 'subtitles', 'ui': 'common'}   # multiplayer 'networking'/'web' tables are left alone
SOURCE_TABLE = SOURCE_PREFIX + TABLES['sub']
SENTINEL = b'UNTRANSLATED STRING!!!'

def _header(head):
    if len(head) < 32 or head[:4] != b'PSAR':
        raise ValueError('Bukan arsip PSARC.')
    _, version, compression, toc_length, entry_size, count, block_size, flags = struct.unpack('>4sI4sIIIII', head[:32])
    if version != 0x00010004 or compression != b'zlib' or entry_size != 30 or block_size != 65536 or not 1 < count < 100000 or toc_length < 32 + count * entry_size:
        raise ValueError('Versi/kompresi PSARC belum didukung.')
    return toc_length, count, block_size

class Psarc:
    def __init__(self, raw):
        self.raw = raw
        self.toc_length, count, self.block_size = _header(raw)
        toc = raw[32:self.toc_length]
        self.entries = []
        for i in range(count):
            item = toc[i*30:(i+1)*30]
            self.entries.append([item[:16], struct.unpack('>I', item[16:20])[0], int.from_bytes(item[20:25], 'big'), int.from_bytes(item[25:30], 'big')])
        table = toc[count*30:]
        if len(table) % 2:
            raise ValueError('Tabel blok PSARC tidak valid.')
        self.blocks = [int.from_bytes(table[i:i+2], 'big') for i in range(0, len(table), 2)]
        names = self.read(0).decode('utf-8').split('\n')
        if len(names) != count - 1:
            raise ValueError('Manifest PSARC tidak cocok dengan TOC.')
        self.names = {name: i + 1 for i, name in enumerate(names)}

    def read(self, index):
        _, block, size, offset = self.entries[index]
        out = bytearray()
        while len(out) < size:
            if block >= len(self.blocks):
                raise ValueError('Blok PSARC terpotong.')
            stored = self.blocks[block] or self.block_size
            expected = min(self.block_size, size - len(out))
            chunk = self.raw[offset:offset+stored]
            if len(chunk) != stored:
                raise ValueError('Data PSARC terpotong.')
            if stored != expected:
                try: chunk = zlib.decompress(chunk)
                except zlib.error as exc: raise ValueError('Blok PSARC rusak.') from exc
                if len(chunk) != expected: raise ValueError('Ukuran blok PSARC tidak cocok.')
            out += chunk; offset += stored; block += 1
        return bytes(out)

    def rebuild(self, replacements):
        """Return a new archive with members in `replacements` ({name: bytes}) replaced."""
        if not replacements:
            return self.raw
        blocks = list(self.blocks); entries = [list(e) for e in self.entries]
        appended = []
        for name, data in replacements.items():
            entry = entries[self.names[name]]
            entry[1] = len(blocks); entry[2] = len(data)
            for start in range(0, len(data), self.block_size):
                piece = data[start:start+self.block_size]
                packed = zlib.compress(piece, 9)
                stored = packed if len(packed) < len(piece) else piece
                blocks.append(0 if len(stored) == self.block_size else len(stored))
                appended.append((entry, stored))
        toc_length = 32 + len(entries) * 30 + len(blocks) * 2
        shift = toc_length - self.toc_length
        body_end = len(self.raw) + shift
        for entry in entries:
            entry[3] += shift
        seen = set()
        for entry, stored in appended:
            if id(entry) not in seen:
                entry[3] = body_end; seen.add(id(entry))
            body_end += len(stored)
        header = bytearray(self.raw[:32]); header[12:16] = struct.pack('>I', toc_length)
        toc = b''.join(md5 + struct.pack('>I', block) + size.to_bytes(5, 'big') + offset.to_bytes(5, 'big') for md5, block, size, offset in entries)
        toc += b''.join(value.to_bytes(2, 'big') for value in blocks)
        if body_end >= 1 << 40:
            raise ValueError('Arsip PSARC terlalu besar.')
        return bytes(header) + toc + self.raw[self.toc_length:] + b''.join(stored for _, stored in appended)

def parse_table(data):
    if len(data) < 4:
        raise ValueError('Tabel teks terpotong.')
    count = struct.unpack('>I', data[:4])[0]
    base = 4 + count * 8
    if not 0 < count < 200000 or len(data) <= base or not data[base:].startswith(SENTINEL + b'\0') or not data.endswith(b'\0'):
        raise ValueError('Tabel teks Naughty Dog tidak dikenali.')
    pairs = [struct.unpack('>II', data[4+i*8:12+i*8]) for i in range(count)]
    hashes = [h for h, _ in pairs]
    if hashes != sorted(hashes) or len(set(hashes)) != count:
        raise ValueError('Hash tabel teks tidak berurutan.')
    rows = []
    for key, offset in pairs:
        end = data.find(b'\0', base + offset)
        if offset >= len(data) - base or end < 0:
            raise ValueError('Offset tabel teks tidak valid.')
        try: rows.append((key, offset, data[base+offset:end].decode('utf-8')))
        except UnicodeError as exc: raise ValueError('Tabel teks bukan UTF-8.') from exc
    return rows

def render_table(rows, values):
    """rows from parse_table; values maps hash -> raw game string."""
    blob = bytearray(SENTINEL + b'\0'); placed = {}; offsets = {}
    for key, offset, text in sorted(rows, key=lambda row: row[1]):
        if offset == 0:
            offsets[key] = 0; continue
        encoded = values.get(key, text).encode('utf-8')
        if encoded not in placed:
            placed[encoded] = len(blob); blob += encoded + b'\0'
        offsets[key] = placed[encoded]
    head = struct.pack('>I', len(rows)) + b''.join(struct.pack('>II', key, offsets[key]) for key, _, _ in rows)
    return head + bytes(blob)

# Game markup: "_" is a non-breaking space, "\" separates speakers/lines, |C| is a controller
# button glyph and [#NAME] a number the game fills in. Buttons and [#..] are shown as {..}
# tokens so the translator keeps them (like [TEXT], [A] and %d, which it already protects).
BUTTON = re.compile(r'\|([A-Za-z0-9]+)\|')
GAME_VALUE = re.compile(r'\[#[^\]\r\n]*\]')
SHOWN_BUTTON = re.compile(r'\{\|([A-Za-z0-9]+)\|\}')
SHOWN_VALUE = re.compile(r'\{(\[#[^\]\r\n]*\])\}')

def to_display(text):
    text = GAME_VALUE.sub(lambda m: '{' + m.group() + '}', BUTTON.sub(lambda m: '{|' + m.group(1) + '|}', text))
    return '\n'.join(part.strip() for part in text.replace('_', ' ').split('\\'))

def to_game(text):
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    if '\\' in text or '_' in text or '\x00' in text:
        raise ValueError('Terjemahan tidak boleh berisi \\, _ atau NUL.')
    text = SHOWN_VALUE.sub(lambda m: m.group(1), SHOWN_BUTTON.sub(lambda m: '|' + m.group(1) + '|', text))
    if '|' in BUTTON.sub('', text):
        raise ValueError('Terjemahan mengubah penanda tombol kontroler.')
    return ' \\ '.join(line.strip() for line in text.split('\n'))

def translatable(kind, text):
    if not text.strip() or not any(c.isalpha() for c in text):
        return False
    if '|' in BUTTON.sub('', text):
        return False  # unknown pipe markup: leave the line untouched
    # Single-token names with "_" (e.g. Marco_Polo, Tetram_-_Gas_Mask_Soldier) are internal labels.
    return not (kind == 'ui' and '_' in text and ' ' not in text)

class PsarcTextDocument:
    format = 'Naughty Dog PSARC (subtitle + teks game)'

    def __init__(self, path, raw, archive, tables):
        """tables: {kind: rows} for the English source tables found in the archive."""
        self.path = Path(path); self.raw = raw; self.archive = archive; self.tables = tables
        self.rows = tables['sub']
        self.entries = [Entry(f'{kind}:{key:08x}', to_display(text))
                        for kind, rows in tables.items() for key, offset, text in rows if offset and translatable(kind, text)]
        self.mirrors = {}
        for kind in tables:
            name = MIRROR_PREFIX + TABLES[kind]
            if name in archive.names:
                try: self.mirrors[kind] = (name, parse_table(archive.read(archive.names[name])))
                except ValueError: pass

    @property
    def sha256(self):
        return digest(self.raw)

    def check_translation(self, entry_id, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError('Terjemahan kosong atau tidak valid.')
        to_game(value)

    def render(self, translations):
        known = {e.id for e in self.entries}
        if set(translations) - known:
            raise ValueError('ID terjemahan tidak dikenal.')
        if not translations:
            return self.raw
        values = {kind: {} for kind in self.tables}
        for entry_id, value in translations.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError('Terjemahan kosong atau tidak valid.')
            kind, key = entry_id.split(':')
            values[kind][int(key, 16)] = to_game(value)
        replacements = {}
        for kind, rows in self.tables.items():
            if not values[kind]: continue
            replacements[SOURCE_PREFIX + TABLES[kind]] = render_table(rows, values[kind])
            if kind in self.mirrors:
                # Only replace lines that are the same English text as the source table.
                name, mirror_rows = self.mirrors[kind]; source = {key: text for key, _, text in rows}
                mirrored = {key: values[kind][key] for key, _, text in mirror_rows if key in values[kind] and source.get(key) == text}
                if mirrored: replacements[name] = render_table(mirror_rows, mirrored)
        return self.archive.rebuild(replacements)

def read_psarc_text(path):
    path = Path(path)
    with path.open('rb') as stream:
        toc_length, _, _ = _header(stream.read(32))
    raw = _read_if_text_archive(path, toc_length)
    archive = Psarc(raw)
    if SOURCE_TABLE not in archive.names:
        raise ValueError('PSARC ini tidak berisi tabel subtitle.')
    tables = {kind: parse_table(archive.read(archive.names[SOURCE_PREFIX + table]))
              for kind, table in TABLES.items() if SOURCE_PREFIX + table in archive.names}
    return PsarcTextDocument(path, raw, archive, tables)

def _read_if_text_archive(path, toc_length):
    # Only the manifest is inflated first, so big audio/texture archives are rejected cheaply.
    with path.open('rb') as stream:
        head = stream.read(toc_length)
        if len(head) != toc_length:
            raise ValueError('TOC PSARC terpotong.')
        count = struct.unpack('>I', head[20:24])[0]
        first = head[32:62]
        block = struct.unpack('>I', first[16:20])[0]; size = int.from_bytes(first[20:25], 'big'); offset = int.from_bytes(first[25:30], 'big')
        table = head[32+count*30:]
        blocks = [int.from_bytes(table[i:i+2], 'big') for i in range(0, len(table) - 1, 2)]
        manifest = bytearray()
        stream.seek(offset)
        while len(manifest) < size and block < len(blocks):
            stored = blocks[block] or 65536; expected = min(65536, size - len(manifest))
            chunk = stream.read(stored)
            try: manifest += zlib.decompress(chunk) if stored != expected else chunk
            except zlib.error as exc: raise ValueError('Manifest PSARC rusak.') from exc
            block += 1
        if SOURCE_TABLE.encode() not in manifest.split(b'\n'):
            raise ValueError('PSARC ini tidak berisi tabel subtitle.')
        stream.seek(0)
        return stream.read()

register_adapter('naughty-dog-psarc', ('.psarc',), read_psarc_text, max_size=MAX_ARCHIVE_SIZE)
