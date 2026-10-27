"""Godot 4 PCK archives with gettext translations (res://.../<locale>/*.po), e.g. Pratfall.

Godot loads the languages listed in the exported project settings, so a new locale cannot simply be
added. The Indonesian text therefore replaces one existing language slot (German by default: its long
strings leave room in the UI); untranslated lines fall back to the English msgid, never to German.
The archive is never rewritten: the new .po is appended and only its directory entry is updated.
"""
from pathlib import Path
import hashlib
import re
import struct
from .adapters import Entry, digest, register_adapter
from .translation import TOKENS

MAX_PCK_SIZE = 4 * 1024 * 1024 * 1024
MARKER = 'X-Generator: LinguaPlay'
SLOT_PREFERENCE =('de', 'nl', 'pl', 'fr', 'es', 'pt_BR', 'ru', 'tr')
PO_PATH = re.compile(r'(^|/)(locali[sz]ation|locale|locales|lang|languages|translations?|i18n)/([A-Za-z]{2,3}(?:[_-][A-Za-z0-9]+)?)/[^/]+\.po$', re.I)
# Bracket tags the generic token guard does not cover (e.g. [\/p], [*]) are shown as {[..]} so they stay intact.
BRACKET = re.compile(r'\[[^\[\]\n]{1,40}\]')
SHOWN_BRACKET = re.compile(r'\{(\[[^\[\]\n]{1,40}\])\}')


class Pck:
    def __init__(self, raw):
        if len(raw) < 100 or raw[:4] != b'GDPC': raise ValueError('Bukan arsip Godot PCK.')
        self.raw = raw; self.version = struct.unpack_from('<I', raw, 4)[0]
        if self.version not in (2, 3): raise ValueError('Versi PCK Godot belum didukung (hanya Godot 4).')
        self.flags, self.file_base = struct.unpack_from('<IQ', raw, 20)
        if self.flags & 1: raise ValueError('Direktori PCK terenkripsi.')
        pos = struct.unpack_from('<Q', raw, 32)[0] if self.version == 3 else 32 + 16 * 4
        count = struct.unpack_from('<I', raw, pos)[0]; pos += 4
        if count > 2_000_000: raise ValueError('Direktori PCK tidak valid.')
        self.files = {}
        for _ in range(count):
            length = struct.unpack_from('<I', raw, pos)[0]; pos += 4
            name = raw[pos:pos + length].rstrip(b'\0').decode('utf-8'); pos += length
            offset, size = struct.unpack_from('<QQ', raw, pos); field = pos; pos += 32
            entry_flags = struct.unpack_from('<I', raw, pos)[0]; pos += 4
            if self.file_base + offset + size > len(raw): raise ValueError('File PCK terpotong.')
            self.files[name] = (offset, size, field, entry_flags)

    def read(self, name):
        offset, size, _, entry_flags = self.files[name]
        if entry_flags & 1: raise ValueError('File di dalam PCK terenkripsi.')
        return self.raw[self.file_base + offset:self.file_base + offset + size]

    def rebuild(self, replacements):
        if not replacements: return self.raw
        body = bytearray(self.raw)
        for name, data in replacements.items():
            body += b'\0' * (-len(body) % 32)  # Godot aligns file data
            offset = len(body) - self.file_base; body += data
            field = self.files[name][2]
            struct.pack_into('<QQ', body, field, offset, len(data)); body[field + 16:field + 32] = hashlib.md5(data).digest()
        return body  # bytearray: avoids another full copy of large archives


def _unescape(text):
    return re.sub(r'\\(.)', lambda m: {'n': '\n', 't': '\t', 'r': '\r', '"': '"', '\\': '\\'}.get(m.group(1), '\\' + m.group(1)), text)

def _escape(text):
    return text.replace('\\', '\\\\').replace('"', '\\"').replace('\t', '\\t').replace('\r', '\\r').replace('\n', '\\n')

def parse_po(text):
    """[(fields dict)] with msgctxt/msgid/msgid_plural/msgstr/msgstr[n]; comments are dropped."""
    entries = []; current = {}; key = None
    def flush():
        if 'msgid' in current: entries.append(dict(current))
        current.clear()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            if not line and current.get('msgid') is not None and any(k.startswith('msgstr') for k in current): flush()
            continue
        match = re.match(r'(msgctxt|msgid_plural|msgid|msgstr(?:\[\d+\])?)\s+"(.*)"$', line)
        if match:
            if match.group(1) in ('msgid', 'msgctxt') and any(k.startswith('msgstr') for k in current): flush()
            key = match.group(1); current[key] = _unescape(match.group(2))
        elif line.startswith('"') and line.endswith('"') and key:
            current[key] += _unescape(line[1:-1])
        else:
            raise ValueError('Baris PO tidak dikenali.')
    flush()
    if not entries or entries[0].get('msgid') != '': raise ValueError('File PO tanpa header.')
    return entries

def render_po(entries):
    blocks = []
    for entry in entries:
        lines = []
        for key in ('msgctxt', 'msgid', 'msgid_plural'):
            if key in entry: lines.append(f'{key} "{_escape(entry[key])}"')
        for key in sorted((k for k in entry if k.startswith('msgstr')), key=lambda k: (len(k), k)):
            lines.append(f'{key} "{_escape(entry[key])}"')
        blocks.append('\n'.join(lines))
    return ('\n\n'.join(blocks) + '\n').encode('utf-8')


def to_display(text):
    protected = {m.group() for m in TOKENS.finditer(text)}
    return BRACKET.sub(lambda m: m.group() if m.group() in protected else '{' + m.group() + '}', text)

def to_game(text):
    return SHOWN_BRACKET.sub(lambda m: m.group(1), text.replace('\r\n', '\n'))


def translatable(text):
    return bool(text.strip()) and any(c.isalpha() for c in text)


class GodotPckDocument:
    def __init__(self, path, raw, pck, slot_name, entries):
        self.path = Path(path); self.raw = raw; self.pck = pck; self.slot_name = slot_name; self.po = entries
        locale = PO_PATH.search(slot_name).group(3)
        self.format = f'Godot PCK gettext (menggantikan slot bahasa "{locale}")'
        self.entries = []; self.index = {}
        # A slot written by LinguaPlay shows its current (translated) text; an original slot shows the English msgid.
        ours = MARKER in entries[0].get('msgstr', '')
        for number, entry in enumerate(entries[1:], 1):
            if 'msgid_plural' in entry or not translatable(entry['msgid']): continue
            identity = 'po:' + hashlib.sha1((entry.get('msgctxt', '') + '\x04' + entry['msgid']).encode()).hexdigest()[:16]
            if identity in self.index: continue
            current = entry.get('msgstr') if ours and entry.get('msgstr') else entry['msgid']
            self.index[identity] = number; self.entries.append(Entry(identity, to_display(current)))

    @property
    def sha256(self):
        return digest(self.raw)

    def check_translation(self, entry_id, value):
        if not isinstance(value, str) or not value.strip() or '\x00' in value: raise ValueError('Terjemahan kosong atau tidak valid.')

    def render(self, translations):
        if set(translations) - set(self.index): raise ValueError('ID terjemahan tidak dikenal.')
        if not translations: return self.raw
        values = {}
        for entry_id, value in translations.items():
            self.check_translation(entry_id, value); values[self.index[entry_id]] = to_game(value)
        rebuilt = []
        for number, entry in enumerate(self.po):
            entry = dict(entry)
            if number == 0:
                # Plural rules become Indonesian (one form); the language code stays so the slot keeps loading.
                header = re.sub(r'Plural-Forms:[^\n]*\n', 'Plural-Forms: nplurals=1; plural=0;\n', entry.get('msgstr', ''))
                entry['msgstr'] = header if MARKER in header else header + MARKER + '\n'
            else:
                for key in [k for k in entry if k.startswith('msgstr')]: entry[key] = ''
                if number in values: entry['msgstr'] = values[number]
            rebuilt.append(entry)
        return self.pck.rebuild({self.slot_name: render_po(rebuilt)})


def read_godot_pck(path):
    path = Path(path)
    with path.open('rb') as stream:
        head = stream.read(48)
    if head[:4] != b'GDPC': raise ValueError('Bukan arsip Godot PCK.')
    raw = path.read_bytes(); pck = Pck(raw)
    slots = {PO_PATH.search(name).group(3): name for name in pck.files if PO_PATH.search(name)}
    if not slots: raise ValueError('PCK ini tidak berisi file terjemahan gettext (.po).')
    choice = next((slots[code] for code in SLOT_PREFERENCE if code in slots), sorted(slots.values())[0])
    try: entries = parse_po(pck.read(choice).decode('utf-8'))
    except UnicodeError as exc: raise ValueError('File PO bukan UTF-8.') from exc
    document = GodotPckDocument(path, raw, pck, choice, entries)
    if not document.entries: raise ValueError('File PO tidak berisi teks yang bisa diterjemahkan.')
    return document

register_adapter('godot-pck-gettext', ('.pck',), read_godot_pck, max_size=MAX_PCK_SIZE)
