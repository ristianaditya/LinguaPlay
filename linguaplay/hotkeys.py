"""Customisable global shortcuts, polled with GetAsyncKeyState so they work while a game has focus."""
from pathlib import Path
import json
import re

DEFAULTS = {'overlay': 'Ctrl+Alt+O', 'region': 'Ctrl+Alt+R', 'stop': 'Ctrl+Alt+F10'}
LABELS = {'overlay': 'Buka overlay dalam game', 'region': 'Ubah area subtitle OCR', 'stop': 'Hentikan OCR'}
MODIFIERS = {'ctrl': 0x11, 'alt': 0x12, 'shift': 0x10, 'meta': 0x5B, 'win': 0x5B}
NAMED = {'space': 0x20, 'tab': 0x09, 'home': 0x24, 'end': 0x23, 'ins': 0x2D, 'insert': 0x2D, 'del': 0x2E, 'delete': 0x2E,
         'pgup': 0x21, 'pgdown': 0x22, 'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27,
         '`': 0xC0, '-': 0xBD, '=': 0xBB, '[': 0xDB, ']': 0xDD, ';': 0xBA, "'": 0xDE, ',': 0xBC, '.': 0xBE, '/': 0xBF, '\\': 0xDC}

class HotkeyError(ValueError):
    pass

def parse(text):
    """'Ctrl+Alt+O' -> (modifier virtual keys, key virtual key). Function keys may stand alone."""
    parts = [p.strip() for p in re.split(r'\+(?!$)', str(text or '')) if p.strip()]
    if not parts: raise HotkeyError('Pintasan kosong.')
    *mods, key = parts; codes = []
    for mod in mods:
        if mod.lower() not in MODIFIERS: raise HotkeyError(f'Tombol pengubah tidak dikenal: {mod}')
        codes.append(MODIFIERS[mod.lower()])
    low = key.lower()
    if len(key) == 1 and key.isalnum(): vk = ord(key.upper())
    elif re.fullmatch(r'f([1-9]|1[0-9]|2[0-4])', low): vk = 0x6F + int(low[1:])
    elif low in NAMED: vk = NAMED[low]
    else: raise HotkeyError(f'Tombol tidak didukung: {key}')
    if not codes and not 0x70 <= vk <= 0x87:
        raise HotkeyError('Gunakan Ctrl, Alt atau Shift bersama tombol tersebut agar tidak bentrok dengan kontrol game.')
    return tuple(sorted(set(codes))), vk

def normalise(text):
    mods, vk = parse(text)
    names = {0x11: 'Ctrl', 0x12: 'Alt', 0x10: 'Shift', 0x5B: 'Win'}
    key = next((k for k, v in NAMED.items() if v == vk and len(k) > 1), None)
    label = f'F{vk - 0x6F}' if 0x70 <= vk <= 0x87 else (key.title() if key else chr(vk))
    order = [0x11, 0x12, 0x10, 0x5B]
    return '+'.join([names[m] for m in order if m in mods] + [label])

def validate(mapping):
    result = {}; seen = {}
    for action in DEFAULTS:
        text = normalise(mapping.get(action, DEFAULTS[action]))
        if text in seen: raise HotkeyError(f'{text} sudah dipakai untuk "{LABELS[seen[text]]}".')
        seen[text] = action; result[action] = text
    return result

def load(path):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        return validate(data if isinstance(data, dict) else {})
    except (OSError, ValueError):
        return dict(DEFAULTS)

def save(path, mapping):
    from .patches import atomic_write
    clean = validate(mapping); Path(path).parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, json.dumps(clean, indent=2).encode()); return clean
