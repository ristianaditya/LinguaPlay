"""The Sims 4 string tables: STBL resources inside DBPF 2.1 packages (Strings_ENG_US.package).

Every original byte is kept; changed string tables are appended (zlib) together with a new index,
and the header is pointed at that index. Unchanged resources keep their original offsets.
"""
from pathlib import Path
import re
import struct
import zlib
from .adapters import Entry, digest, register_adapter

MAX_PACKAGE_SIZE = 64 * 1024 * 1024
STBL_TYPE = 0x220557DA
ZLIB, REFPACK, DELETED = 0x5A42, 0xFFFF, 0xFFE0
SOURCE_NAME = 'strings_eng_us.package'


def refpack(data):
    """EA RefPack/QFS decompression (the 'internal' compression of Sims 4 packages)."""
    if len(data) < 5 or data[1] != 0xFB:
        raise ValueError('Kompresi RefPack tidak dikenali.')
    flags = data[0]; size_len = 4 if flags & 0x80 else 3; pos = 2 + (size_len if flags & 0x01 else 0)
    size = int.from_bytes(data[pos:pos + size_len], 'big'); pos += size_len
    out = bytearray()
    try:
        while pos < len(data):
            b0 = data[pos]
            if b0 < 0x80:
                b1 = data[pos + 1]; plain = b0 & 3; copy = ((b0 & 0x1C) >> 2) + 3; offset = ((b0 & 0x60) << 3) + b1 + 1; pos += 2
            elif b0 < 0xC0:
                b1, b2 = data[pos + 1], data[pos + 2]; plain = b1 >> 6; copy = (b0 & 0x3F) + 4; offset = ((b1 & 0x3F) << 8) + b2 + 1; pos += 3
            elif b0 < 0xE0:
                b1, b2, b3 = data[pos + 1:pos + 4]; plain = b0 & 3; copy = ((b0 & 0x0C) << 6) + b3 + 5; offset = ((b0 & 0x10) << 12) + (b1 << 8) + b2 + 1; pos += 4
            elif b0 < 0xFC:
                plain = ((b0 & 0x1F) << 2) + 4; copy = 0; offset = 0; pos += 1
            else:
                plain = b0 & 3; copy = 0; offset = 0; pos += 1
            out += data[pos:pos + plain]; pos += plain
            if copy:
                if offset > len(out): raise ValueError('Data RefPack rusak.')
                for _ in range(copy): out.append(out[-offset])
            if b0 >= 0xFC: break
    except IndexError as exc:
        raise ValueError('Data RefPack terpotong.') from exc
    if len(out) != size: raise ValueError('Ukuran RefPack tidak cocok.')
    return bytes(out)


class Package:
    def __init__(self, raw):
        if len(raw) < 96 or raw[:4] != b'DBPF' or struct.unpack_from('<II', raw, 4) != (2, 1):
            raise ValueError('Bukan paket DBPF 2.1 (The Sims 4).')
        self.raw = raw
        count, legacy_offset, index_size = struct.unpack_from('<III', raw, 36)
        offset = struct.unpack_from('<Q', raw, 64)[0] or legacy_offset
        if not 0 < offset <= len(raw) - 4 or offset + index_size > len(raw) or count > 1_000_000:
            raise ValueError('Index paket DBPF tidak valid.')
        pos = offset; flags = struct.unpack_from('<I', raw, pos)[0]; pos += 4
        constant = {}
        for bit, name in enumerate(('type', 'group', 'inst_hi')):
            if flags & (1 << bit): constant[name] = struct.unpack_from('<I', raw, pos)[0]; pos += 4
        if flags & ~0x7: raise ValueError('Format index DBPF belum didukung.')
        self.entries = []
        for _ in range(count):
            entry = {}
            for name in ('type', 'group', 'inst_hi'):
                if name in constant: entry[name] = constant[name]
                else: entry[name] = struct.unpack_from('<I', raw, pos)[0]; pos += 4
            entry['inst_lo'], entry['offset'], size_flags, entry['mem'] = struct.unpack_from('<IIII', raw, pos); pos += 16
            if not size_flags >> 31: raise ValueError('Entri DBPF tanpa info kompresi belum didukung.')
            entry['size'] = size_flags & 0x7FFFFFFF
            entry['comp'], entry['committed'] = struct.unpack_from('<HH', raw, pos); pos += 4
            if entry['comp'] != DELETED and entry['offset'] + entry['size'] > len(raw): raise ValueError('Resource DBPF terpotong.')
            self.entries.append(entry)
        if pos > offset + index_size: raise ValueError('Ukuran index DBPF tidak cocok.')

    def read(self, entry):
        data = self.raw[entry['offset']:entry['offset'] + entry['size']]
        if entry['comp'] == ZLIB:
            try: data = zlib.decompress(data)
            except zlib.error as exc: raise ValueError('Resource zlib rusak.') from exc
        elif entry['comp'] == REFPACK: data = refpack(data)
        elif entry['comp'] != 0: raise ValueError('Kompresi resource belum didukung.')
        if len(data) != entry['mem']: raise ValueError('Ukuran resource tidak cocok.')
        return data

    def rebuild(self, replacements):
        """replacements: {entry index: new uncompressed bytes}."""
        if not replacements: return self.raw
        body = bytearray(self.raw); entries = [dict(e) for e in self.entries]
        for index, data in replacements.items():
            packed = zlib.compress(data, 9); entries[index].update(offset=len(body), size=len(packed), mem=len(data), comp=ZLIB, committed=1)
            body += packed
        index_offset = len(body)
        index = struct.pack('<I', 0) + b''.join(
            struct.pack('<IIIIIIIHH', e['type'], e['group'], e['inst_hi'], e['inst_lo'], e['offset'], e['size'] | 0x80000000, e['mem'], e['comp'], e['committed'])
            for e in entries)
        body += index
        if len(body) >= 1 << 32: raise ValueError('Paket terlalu besar.')
        struct.pack_into('<III', body, 36, len(entries), 0 if struct.unpack_from('<I', self.raw, 40)[0] == 0 else index_offset, len(index))
        struct.pack_into('<Q', body, 64, index_offset)
        return bytes(body)


def parse_stbl(data):
    if len(data) < 21 or data[:4] != b'STBL': raise ValueError('Resource STBL tidak valid.')
    version, compressed = struct.unpack_from('<HB', data, 4)
    if version != 5 or compressed != 0: raise ValueError('Versi STBL belum didukung.')
    count = struct.unpack_from('<Q', data, 7)[0]; declared = struct.unpack_from('<I', data, 17)[0]; pos = 21; rows = []
    try:
        for _ in range(count):
            key, flags, length = struct.unpack_from('<IBH', data, pos); pos += 7
            rows.append((key, flags, data[pos:pos + length].decode('utf-8'))); pos += length
    except (struct.error, UnicodeError) as exc:
        raise ValueError('Isi STBL rusak.') from exc
    if pos != len(data) or declared != sum(len(t.encode()) + 1 for _, _, t in rows): raise ValueError('Panjang STBL tidak cocok.')
    return rows


def render_stbl(rows):
    strings = [t.encode('utf-8') for _, _, t in rows]
    head = b'STBL' + struct.pack('<HBQ', 5, 0, len(rows)) + b'\0\0' + struct.pack('<I', sum(len(s) + 1 for s in strings))
    return head + b''.join(struct.pack('<IBH', key, flags, len(s)) + s for (key, flags, _), s in zip(rows, strings))


def translatable(text):
    if not text.strip() or not any(c.isalpha() for c in text): return False
    # Internal identifiers such as Debug_Interaction_Name or tuning keys are left untouched.
    return not (' ' not in text and ('_' in text or text.isupper() and len(text) > 12))


class StringPackageDocument:
    format = 'The Sims 4 string table (STBL)'

    def __init__(self, path, raw, package, tables):
        self.path = Path(path); self.raw = raw; self.package = package; self.tables = tables  # [(entry index, rows)]
        self.entries = []; self.locations = {}
        for table_number, (_, rows) in enumerate(tables):
            seen = {}
            for row_number, (key, _, text) in enumerate(rows):
                if not translatable(text): continue
                base = f't{table_number}:{key:08x}'; seen[base] = seen.get(base, 0) + 1
                identity = base if seen[base] == 1 else f'{base}#{seen[base]}'
                self.entries.append(Entry(identity, text)); self.locations[identity] = (table_number, row_number)

    @property
    def sha256(self):
        return digest(self.raw)

    def check_translation(self, entry_id, value):
        if not isinstance(value, str) or not value.strip() or '\x00' in value: raise ValueError('Terjemahan kosong atau tidak valid.')
        if len(value.encode('utf-8')) > 65535: raise ValueError('Terjemahan terlalu panjang untuk STBL.')

    def render(self, translations):
        if set(translations) - set(self.locations): raise ValueError('ID terjemahan tidak dikenal.')
        if not translations: return self.raw
        changed = {}
        for entry_id, value in translations.items():
            self.check_translation(entry_id, value)
            table_number, row_number = self.locations[entry_id]
            changed.setdefault(table_number, {})[row_number] = value
        replacements = {}
        for table_number, values in changed.items():
            entry_index, rows = self.tables[table_number]
            replacements[entry_index] = render_stbl([(k, f, values.get(i, t)) for i, (k, f, t) in enumerate(rows)])
        return self.package.rebuild(replacements)


def read_string_package(path):
    path = Path(path)
    # Staged copies keep the name as a suffix (e.g. "0.Strings_ENG_US.package").
    if not path.name.lower().endswith(SOURCE_NAME):
        if path.name.lower().startswith('strings_'): raise ValueError('Hanya Strings_ENG_US.package (bahasa Inggris) yang diterjemahkan.')
        raise ValueError('Paket ini bukan tabel teks The Sims 4.')
    raw = path.read_bytes(); package = Package(raw)
    tables = [(index, parse_stbl(package.read(entry))) for index, entry in enumerate(package.entries)
              if entry['type'] == STBL_TYPE and entry['comp'] != DELETED]
    if not tables: raise ValueError('Paket ini tidak berisi tabel teks.')
    return StringPackageDocument(path, raw, package, tables)

register_adapter('sims4-stbl', ('.package',), read_string_package, max_size=MAX_PACKAGE_SIZE)
