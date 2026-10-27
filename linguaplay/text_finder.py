"""Deep analysis: find where a game keeps its English text, the way a person would investigate it.

Files are identified by content (magic bytes), archive listings are inspected where they are readable,
and English sentences are counted in loose and binary files. Nothing is modified.
"""
from dataclasses import dataclass, field
from pathlib import Path
import os
import re
import struct
import zlib

COMMON = set('''the a an and or but if then of to in on at by for with from as is are was were be been being it its this that these those
you your yours we our us they their them he his him she her i me my not no yes do does did done have has had will would can could should
shall may might must there here what when where who why how all any some more most other into out up down over under again only very
just now also than so too off about after before because while until each every both few many much such own same new old good great
right left back next last first find get got take make go come see look use need want know think let help press hold select choose
open close save load quit continue start game player level health enemy weapon item items map quest mission objective friend friends
time day night home world life mode option options settings menu sound music video controls'''.split())
SKIP_SUFFIX = {'.png', '.jpg', '.jpeg', '.dds', '.tga', '.bmp', '.ktx', '.webp', '.ico', '.wav', '.ogg', '.mp3', '.wem', '.bnk', '.xvag',
               '.at9', '.vag', '.mp4', '.bk2', '.usm', '.webm', '.avi', '.dll', '.exe', '.pdb', '.sys', '.so', '.lib', '.ttf', '.otf',
               '.spv', '.cso', '.cxo', '.pxo', '.shader', '.fx', '.cache', '.log', '.sig', '.cat'}
LOCALE_NAME = re.compile(r'(local|locale|lang|language|strings?|text|subtitle|dialog|dialogue|caption|translation|i18n|l10n|'
                         r'(^|[^a-z])(en|eng|english|en_us|en-us)([^a-z]|$))', re.I)
# Legal text, documentation, third-party runtimes and source code are not game text.
NOT_GAME_TEXT = re.compile(r'(licen[cs]e|copying|eula|readme|notice|credits?\b|privacy|agreement|terms|third.?party|thirdparty|changelog|'
                           r'patch.?notes|__installer|redist|support[\\/]|adobe air|cef3?|chromium|webkit|[\\/]engine[\\/]binaries|'
                           r'backupthisfolder|il2cppoutput|burstdebug|[\\/]plugins[\\/]|steamworks|sentry|\.xml$|\.html?$|\.rtf$|\.cpp$|\.h$|\.cs$|'
                           r'unins\d*\.dat$|global-metadata\.dat$)', re.I)
# Strong signals of real localisation data.
LOCALIZATION_SUFFIX = {'.po', '.pot', '.csv', '.tsv', '.locres', '.loc', '.translation', '.strings', '.lang', '.ftl', '.json', '.yaml', '.yml', '.ini', '.txt'}
SENTENCE = re.compile(r"[A-Za-z][A-Za-z'’,.!?;:\- ]{8,}")
MAGIC = [(b'PSAR', 'PSARC (PlayStation)'), (b'DBPF', 'DBPF (The Sims/EA)'), (b'UnityFS', 'Unity asset bundle'),
         (b'UnityWeb', 'Unity asset bundle'), (b'GDPC', 'Godot PCK'), (b'PK\x03\x04', 'ZIP'), (b'FWS', 'Flash SWF'),
         (b'CWS', 'Flash SWF (zlib)'), (b'ZWS', 'Flash SWF (LZMA)'), (b'RIFF', 'RIFF media'), (b'\x89PNG', 'PNG image')]
UE_PAK_MAGIC = struct.pack('<I', 0x5A6F12E1)


@dataclass
class Finding:
    path: str
    kind: str
    status: str          # patch | found | locked | archive
    english: int = 0
    samples: list = field(default_factory=list)
    note: str = ''

    localization: bool = False

    @property
    def score(self):
        return ({'patch': 4, 'found': 3, 'archive': 2, 'locked': 1}[self.status], self.localization, self.english)


def english_sentences(text, limit=4000):
    """Sentence-like runs where at least 40% of the words are common English words."""
    found = []
    for match in SENTENCE.finditer(text):
        run = match.group().strip(); words = re.findall(r"[a-z']+", run.lower())
        # Code identifiers (Foo.Bar, A::B, snake_case) are not dialogue or UI text.
        if re.search(r'::|\w\.\w|_|\(\)|[a-z][A-Z]', run) and not re.search(r'[.!?]\s', run): continue
        # Compressed bytes produce short letter salad ("A!Ia all"): demand real words and mostly letters.
        real = [w for w in words if len(w) >= 2]
        if len(real) < 3 or sum(c.isalpha() or c == ' ' for c in run) / len(run) < .8 or not any(len(w) >= 3 and w in COMMON for w in real): continue
        if len(words) >= 3 and sum(w in COMMON for w in words) / len(words) >= .4:
            found.append(run)
            if len(found) >= limit: break
    return found


def _decode(data):
    if data.startswith((b'\xff\xfe', b'\xfe\xff')): return data.decode('utf-16', 'ignore')
    if data[:2000].count(b'\0') > 200 and data[1:2000:2].count(0) > 600: return data.decode('utf-16-le', 'ignore')
    return data.decode('utf-8', 'ignore')


def _binary_strings(data):
    """Printable UTF-8 runs and UTF-16LE runs inside a binary blob."""
    ascii_runs = ' \n'.join(m.decode('utf-8', 'ignore') for m in re.findall(rb'[\x20-\x7e\xc2-\xf4\x80-\xbf]{12,}', data))
    wide_runs = ' \n'.join(m.decode('utf-16-le', 'ignore') for m in re.findall(rb'(?:[\x20-\x7e]\x00){12,}', data))
    return ascii_runs + '\n' + wide_runs


def _archive_names(path, kind, head):
    try:
        if kind.startswith('PSARC'):
            from .psarc_text import Psarc
            return list(Psarc(path.read_bytes()).names) if path.stat().st_size < 256 * 1024 * 1024 else []
        if kind == 'ZIP':
            import zipfile
            with zipfile.ZipFile(path) as archive: return archive.namelist()[:20000]
        if kind == 'Godot PCK':
            with path.open('rb') as stream:
                data = stream.read(min(path.stat().st_size, 32 * 1024 * 1024))
            version = struct.unpack_from('<I', data, 4)[0]; pos = 8 + 12 + (12 if version >= 2 else 0) + 64
            count = struct.unpack_from('<I', data, pos)[0]; pos += 4; names = []
            for _ in range(min(count, 50000)):
                length = struct.unpack_from('<I', data, pos)[0]; pos += 4
                names.append(data[pos:pos + length].rstrip(b'\0').decode('utf-8', 'ignore')); pos += length + 16 + 16 + (4 if version >= 2 else 0)
            return names
    except (OSError, ValueError, struct.error, Exception):
        return []
    return []


def identify(path, head):
    for magic, kind in MAGIC:
        if head.startswith(magic): return kind
    try:
        size = path.stat().st_size
        if path.suffix.lower() == '.pak' and size > 256:
            with path.open('rb') as stream:
                stream.seek(max(0, size - 512)); tail = stream.read()
            if UE_PAK_MAGIC in tail: return 'Unreal PAK'
    except OSError: pass
    if path.suffix.lower() in ('.utoc', '.ucas'): return 'Unreal IoStore'
    if path.suffix.lower() == '.swz': return 'Adobe AIR SWZ'
    return ''


def analyze(root, progress=None, cancel=None, supported=None, max_files=50000):
    """Return findings, best first. `supported` maps relative paths already readable by an adapter."""
    root = Path(root); findings = []; inspected = 0; supported = supported or {}
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d.lower() not in ('.linguaplay', '.git', 'node_modules', '__pycache__', 'shadercache', 'logs', 'crashes')]
        for name in files:
            if cancel and cancel.is_set(): raise InterruptedError('Analisis dibatalkan.')
            inspected += 1
            if inspected > max_files: break
            path = Path(folder) / name; rel = str(path.relative_to(root)); suffix = path.suffix.lower()
            if rel not in supported and NOT_GAME_TEXT.search(rel): continue
            if rel in supported:
                doc = supported[rel]
                findings.append(Finding(rel, doc.format, 'patch', len(doc.entries), [e.text[:120] for e in doc.entries[:3]], 'Bisa diterjemahkan dan dipatch.')); continue
            if suffix in SKIP_SUFFIX: continue
            try: size = path.stat().st_size
            except OSError: continue
            if size < 64: continue
            if progress and inspected % 50 == 0: progress(f'Menganalisis {inspected} file… {rel[-60:]}')
            try:
                with path.open('rb') as stream: head = stream.read(min(size, 512 * 1024))
            except OSError: continue
            kind = identify(path, head); localeish = bool(LOCALE_NAME.search(name))
            if kind:
                if kind in ('RIFF media', 'PNG image'): continue
                names = _archive_names(path, kind, head)
                text_names = [n for n in names if LOCALE_NAME.search(n.rsplit('/', 1)[-1])]
                locked = kind in ('Unreal PAK', 'Unreal IoStore', 'Adobe AIR SWZ', 'Flash SWF (LZMA)')
                sample = english_sentences(_binary_strings(head)) if not names else []
                if text_names or len(sample) >= 2 or (localeish and sample):
                    note = (f'Arsip {kind}: {len(text_names)} file teks/lokalisasi di dalamnya, mis. ' + ', '.join(text_names[:3])) if text_names else \
                           (f'Arsip {kind} kemungkinan terenkripsi/terkompresi; teks tidak bisa dibaca langsung.' if locked else f'Arsip {kind} berisi teks Inggris.')
                    findings.append(Finding(rel, kind, 'locked' if locked and not sample else 'archive', len(sample), sample[:3], note + ' Format ini belum bisa dipatch.', bool(text_names)))
                continue
            text = _decode(head)
            printable = sum(c.isprintable() or c in '\r\n\t' for c in text[:20000]) / max(1, len(text[:20000]))
            sentences = english_sentences(text if printable > .95 else _binary_strings(head))
            if len(sentences) < (3 if localeish else 12): continue
            loose = printable > .95
            if suffix in ('.po', '.pot'):
                findings.append(Finding(rel, 'Gettext PO/POT', 'found', len(sentences), sentences[:3],
                                        'Template terjemahan resmi (gettext). Kandidat terbaik untuk adapter patch.', True)); continue
            fmt = {'.csv': 'CSV', '.tsv': 'TSV', '.json': 'JSON', '.xml': 'XML', '.txt': 'Teks', '.ini': 'INI', '.po': 'Gettext PO',
                   '.lua': 'Lua', '.yaml': 'YAML', '.yml': 'YAML', '.loc': 'LOC', '.locres': 'Unreal LocRes'}.get(suffix, 'Teks' if loose else 'Biner')
            estimate = len(sentences) if size <= len(head) else round(len(sentences) * size / len(head))
            note = (f'File {fmt} berisi ±{estimate} kalimat Inggris. ' + ('Format teks ini belum punya adapter patch; bagikan diagnostik agar bisa ditambahkan.' if loose else
                    'Teks tersimpan di dalam file biner; butuh adapter khusus.'))
            findings.append(Finding(rel, fmt, 'found', estimate, sentences[:3], note, localeish or suffix in LOCALIZATION_SUFFIX))
    return sorted(findings, key=lambda f: f.score, reverse=True)[:200]
