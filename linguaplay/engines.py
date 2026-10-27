"""Identify a game's engine and anti-cheat from file names, so a scan can explain *why*
no translatable text was found. Only names and a few header bytes are read."""
from pathlib import Path
import os

ANTICHEAT_NOTE = ('Dilindungi {name}. Mengubah file game dapat dianggap curang dan berisiko ban akun, '
                  'jadi LinguaPlay tidak membuat patch untuk game ini. Gunakan Overlay OCR.')

ENGINES = {
    'naughty-dog': ('Naughty Dog (PS4)', 'Subtitle dan teks in-game di core.psarc didukung.'),
    'sims4': ('The Sims 4 (EA)', 'Teks in-game di Strings_ENG_US.package (base game dan semua pack) didukung.'),
    'unreal': ('Unreal Engine', 'Teks ada di file .locres di dalam arsip .pak/.utoc, yang sering terenkripsi. '
                                'Belum didukung; gunakan Overlay OCR.'),
    'unity': ('Unity', 'Tabel teks Unity Localization (bundle string-tables bahasa Inggris) didukung. Game Unity yang menyimpan '
                       'teks dengan cara lain belum didukung; gunakan Analisis mendalam atau Overlay OCR.'),
    'godot': ('Godot', 'Terjemahan gettext (.po) di dalam arsip .pck didukung: bahasa Indonesia dipasang menggantikan satu slot bahasa '
                       '(mis. Deutsch). Format .translation biner belum didukung; gunakan Overlay OCR untuk itu.'),
    'frostbite': ('Frostbite (EA)', 'Data game ada di arsip .cas/.toc yang terenkripsi. Tidak didukung; gunakan Overlay OCR.'),
    'adobe-air': ('Adobe AIR', 'Teks ada di arsip .swz yang terenkripsi. Belum didukung; gunakan Overlay OCR.'),
}

def _names(root, depth=4, limit=20000):
    root = Path(root); seen = 0
    for folder, dirs, files in os.walk(root):
        level = len(Path(folder).relative_to(root).parts)
        dirs[:] = [d for d in dirs if d not in ('.linguaplay', '.git', '__pycache__')] if level < depth else []
        for name in dirs + files:
            seen += 1
            if seen > limit: return
            yield Path(folder) / name, name.lower()

def _starts_with(path, magic):
    try:
        with open(path, 'rb') as stream: return stream.read(len(magic)) == magic
    except OSError: return False

def identify_engine(root):
    """Return {'engine', 'engine_name', 'anticheat', 'note'}; empty strings when unknown."""
    anticheat = engine = ''
    for path, name in _names(root):
        if not anticheat:
            if name in ('easyanticheat', 'start_protected_game.exe', 'easyanticheat_eos_setup.exe'): anticheat = 'EasyAntiCheat'
            elif name.startswith('eaanticheat'): anticheat = 'EA AntiCheat'
            elif name in ('battleye',) or name.startswith('beservice'): anticheat = 'BattlEye'
        if not engine:
            if name == 'core.psarc': engine = 'naughty-dog'
            elif name in ('ts4_x64.exe', 'ts4.exe') or name == 'strings_eng_us.package': engine = 'sims4'
            elif name in ('unityplayer.dll', 'unityengine.dll') or name.endswith('_data') and (path / 'globalgamemanagers').exists(): engine = 'unity'
            elif name.endswith('.pck') and _starts_with(path, b'GDPC'): engine = 'godot'
            elif name.endswith(('.utoc', '.ucas')) or (name.endswith('.pak') and path.parent.name.lower() == 'paks'): engine = 'unreal'
            elif name.endswith('.cas') and 'superbundlelayout' in str(path).lower() or name == 'layout.toc': engine = 'frostbite'
            elif name == 'adobe air' or name.endswith('.swz'): engine = 'adobe-air'
        if anticheat and engine: break
    engine_name, note = ENGINES.get(engine, ('', ''))
    if anticheat: note = ANTICHEAT_NOTE.format(name=anticheat)
    return {'engine': engine, 'engine_name': engine_name, 'anticheat': anticheat, 'note': note}
