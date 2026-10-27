"""Content-validated adapters. Unknown containers are never unpacked or written."""
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
import hashlib
import json
import os
import re
import stat

MAX_FILE_SIZE = 8 * 1024 * 1024
TIME = re.compile(r'^(?:\d{2}:)?\d{2}:\d{2}[,.]\d{3}\s+-->\s+(?:\d{2}:)?\d{2}:\d{2}[,.]\d{3}(?:[^\r\n]*)$')

def digest(data):
    return hashlib.sha256(data).hexdigest()

@dataclass(frozen=True)
class Entry:
    id: str
    text: str

@dataclass
class Document:
    path: Path
    format: str
    raw: bytes
    text: str
    encoding: str
    entries: list[Entry]
    spans: list[tuple[int, int]] = field(default_factory=list)
    payload: dict | None = None

    @property
    def sha256(self):
        return digest(self.raw)

    def render(self, translations: dict[str, str]) -> bytes:
        known = {e.id for e in self.entries}
        if set(translations) - known:
            raise ValueError('ID terjemahan tidak dikenal.')
        if not translations:
            return self.raw
        for value in translations.values():
            if not isinstance(value, str) or not value.strip() or '\x00' in value:
                raise ValueError('Terjemahan kosong atau tidak valid.')
        if self.payload is not None:
            # Replace only selected JSON string literals: metadata numeric precision,
            # escapes, whitespace, nested values and property ordering stay exact.
            result=self.text
            for entry,(start,end) in reversed(list(zip(self.entries,self.spans))):
                if entry.id in translations:
                    result=result[:start]+json.dumps(translations[entry.id],ensure_ascii=False)+result[end:]
            return self.encode(result)
        result = self.text
        newline = '\r\n' if '\r\n' in result else '\n'
        for entry, (start, end) in reversed(list(zip(self.entries, self.spans))):
            if entry.id in translations:
                value = translations[entry.id].replace('\r\n', '\n').replace('\r', '\n')
                if re.search(r'\n\s*\n', value) or '-->' in value:
                    raise ValueError('Terjemahan merusak struktur subtitle.')
                result = result[:start] + value.replace('\n', newline) + result[end:]
        return self.encode(result)

    def encode(self,text):
        if self.raw.startswith(b'\xfe\xff'):
            return b'\xfe\xff'+text.encode('utf-16-be')
        return text.encode(self.encoding)

def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Kunci JSON duplikat tidak didukung.')
        result[key] = value
    return result

def _reject_constant(value):
    raise ValueError(f'Konstanta JSON tidak standar: {value}')

def _json_value_spans(text):
    """Locate direct root strings value tokens without serializing other fields."""
    decoder=json.JSONDecoder(parse_constant=_reject_constant)
    def ws(pos):
        while pos<len(text) and text[pos].isspace(): pos+=1
        return pos
    pos=ws(0)+1
    while True:
        pos=ws(pos)
        if text[pos]=='}': break
        key,pos=decoder.raw_decode(text,pos)
        pos=ws(pos)+1; pos=ws(pos)  # colon
        if key=='strings':
            spans=[]; pos=ws(pos+1)
            while text[pos]!='}':
                _,pos=decoder.raw_decode(text,pos)
                pos=ws(pos)+1; start=ws(pos)
                _,end=decoder.raw_decode(text,start)
                spans.append((start,end)); pos=ws(end)
                if text[pos]==',': pos=ws(pos+1)
            return spans
        _,pos=decoder.raw_decode(text,pos)
        pos=ws(pos)
        if text[pos]==',': pos+=1
    raise ValueError('Objek strings tidak ditemukan.')

def _load_builtin(path) -> Document:
    path = Path(path)
    if path.stat().st_size > MAX_FILE_SIZE:
        raise ValueError('File melebihi batas 8 MiB.')
    raw = path.read_bytes()
    encoding = 'utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else ('utf-8-sig' if raw.startswith(b'\xef\xbb\xbf') else 'utf-8')
    try:
        text = raw.decode(encoding)
    except UnicodeError as exc:
        raise ValueError('Encoding belum didukung; gunakan UTF-8 atau UTF-16 dengan BOM.') from exc
    if '\x00' in text:
        raise ValueError('Data biner tidak didukung.')
    suffix = path.suffix.lower()
    if suffix == '.json':
        payload = json.loads(text, object_pairs_hook=_unique_pairs,parse_constant=_reject_constant)
        strings = payload.get('strings') if isinstance(payload, dict) else None
        if not isinstance(strings, dict) or not strings or not all(isinstance(v,str) and v.strip() for v in strings.values()):
            raise ValueError('JSON harus mempunyai objek strings berisi ID:teks. JSON umum tidak diproses.')
        return Document(path, 'JSON strings', raw, text, encoding, [Entry(k,v) for k,v in strings.items()], spans=_json_value_spans(text),payload=payload)
    if suffix not in ('.srt', '.vtt'):
        raise ValueError('Belum ada adapter untuk format ini.')
    is_vtt = suffix == '.vtt'
    if is_vtt and not re.match(r'^WEBVTT(?:[ \t].*)?(?:\r?\n|$)', text):
        raise ValueError('Header WEBVTT tidak valid.')
    entries, spans = [], []
    offset = 0
    # Keep exact original spans including separators and timestamp settings.
    for block in re.split(r'(\r?\n[ \t]*\r?\n)', text):
        lines = block.splitlines(keepends=True)
        stripped = [line.rstrip('\r\n') for line in lines]
        skip = not stripped or not block.strip() or (is_vtt and bool(re.match(r'^(?:WEBVTT(?:[ \t]|$)|NOTE(?:[ \t]|$)|STYLE$|REGION$)',stripped[0])))
        if not skip:
            times = [i for i,line in enumerate(stripped) if TIME.fullmatch(line)]
            if len(times) != 1 or times[0] not in (0,1):
                raise ValueError('Struktur cue subtitle tidak valid.')
            idx = times[0]
            if not is_vtt and (idx != 1 or not stripped[0].isdigit()):
                raise ValueError('SRT harus memiliki nomor cue.')
            start = offset + sum(len(line) for line in lines[:idx+1])
            end = offset + len(block.rstrip('\r\n'))
            if start >= end:
                raise ValueError('Cue tidak memiliki teks.')
            entry_id = f'cue:{len(entries)+1}'
            entries.append(Entry(entry_id, text[start:end]))
            spans.append((start,end))
        offset += len(block)
    if not entries:
        raise ValueError('Tidak ditemukan cue subtitle.')
    return Document(path, 'WebVTT' if is_vtt else 'SRT', raw, text, encoding, entries, spans)

_ADAPTERS = {}

def register_adapter(name, extensions, reader):
    """Developer extension point; trusted Python code only, no remote plugin loading."""
    extensions=tuple(extension.lower() for extension in extensions)
    if name in _ADAPTERS or not extensions or any(not e.startswith('.') for e in extensions):
        raise ValueError('Nama adapter sudah ada atau daftar ekstensi tidak valid.')
    _ADAPTERS[name]=(extensions,reader)

def unregister_adapter(name):
    if name in ('srt','webvtt','json-strings'):
        raise ValueError('Adapter bawaan tidak dapat dihapus saat runtime.')
    _ADAPTERS.pop(name,None)

def load_document(path) -> Document:
    path=Path(path)
    if path.stat().st_size>MAX_FILE_SIZE:
        raise ValueError('File melebihi batas 8 MiB.')
    errors=[]
    for extensions,reader in _ADAPTERS.values():
        if path.suffix.lower() in extensions:
            try:
                document=reader(path)
                ids=[entry.id for entry in document.entries]
                if not ids or len(set(ids))!=len(ids):
                    raise ValueError('Adapter menghasilkan ID kosong atau duplikat.')
                return document
            except ValueError as exc: errors.append(str(exc))
    raise ValueError('; '.join(errors) or 'Belum ada adapter untuk format ini.')

register_adapter('srt',('.srt',),_load_builtin)
register_adapter('webvtt',('.vtt',),_load_builtin)
register_adapter('json-strings',('.json',),_load_builtin)

def _is_reparse(path):
    try:
        return bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except AttributeError:
        return path.is_symlink()
    except OSError:
        return True

@dataclass
class ScanReport:
    root: Path
    documents: list[Document] = field(default_factory=list)
    unsupported: list[dict] = field(default_factory=list)
    executables: list[str] = field(default_factory=list)
    inspected: int = 0
    truncated: bool = False

    def diagnostic(self):
        return {'schema':1, 'root_name':self.root.name, 'inspected':self.inspected,
                'truncated':self.truncated, 'executables':self.executables,
                'supported':[{'path':str(d.path.relative_to(self.root)), 'format':d.format, 'entries':len(d.entries)} for d in self.documents],
                'unsupported':self.unsupported}

def scan_folder(path, cancel: Event | None = None, progress=None) -> ScanReport:
    root = Path(path).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Pilih folder instalasi game.')
    report = ScanReport(root)
    containers = {'.pak','.pck','.bundle','.assets','.loc','.dat','.bin','.archive','.ucas','.utoc'}
    for folder, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in {'.linguaplay','.git','node_modules','backups','__pycache__'} and not _is_reparse(Path(folder)/d))
        for name in sorted(files):
            if cancel and cancel.is_set():
                raise InterruptedError('Pemindaian dibatalkan.')
            report.inspected += 1
            if report.inspected > 50000:
                report.truncated = True
                return report
            file = Path(folder)/name
            if _is_reparse(file) or not file.resolve().is_relative_to(root):
                continue
            rel = str(file.relative_to(root))
            if file.suffix.lower() == '.exe' and len(report.executables) < 30:
                report.executables.append(rel)
            supported_extensions={ext for extensions,_ in _ADAPTERS.values() for ext in extensions}
            if file.suffix.lower() not in containers | supported_extensions:
                continue
            try:
                if file.suffix.lower() in containers and file.suffix.lower() not in supported_extensions:
                    with file.open('rb') as stream:
                        signature = stream.read(16).hex()
                    raise ValueError(f'Kontainer belum didukung; signature {signature}')
                report.documents.append(load_document(file))
            except (ValueError, OSError) as exc:
                if len(report.unsupported) < 500:
                    report.unsupported.append({'path':rel, 'reason':str(exc)})
            if progress:
                progress(f'Memeriksa {rel}')
    return report


def scan_game_root(path) -> dict:
    """Return a small compatibility summary for the library UI."""
    report = scan_folder(path)
    candidates = [str(d.path.relative_to(report.root)) for d in report.documents]
    if candidates:
        level = 'patch'
    elif report.unsupported:
        level = 'ocr'
    else:
        level = 'unsupported'
    return {'support_level': level, 'candidates': candidates,
            'adapter_id': report.documents[0].format if report.documents else '',
            'warnings': [item['reason'] for item in report.unsupported[:20]],
            'scan_hash': digest(json.dumps(report.diagnostic(), sort_keys=True).encode())}
