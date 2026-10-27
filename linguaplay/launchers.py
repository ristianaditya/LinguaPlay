"""Find installed games outside Steam: Epic, GOG, Ubisoft Connect, EA app and plain game folders.

Only local manifests, registry values and file names are read; nothing is downloaded or run.
"""
from pathlib import Path
import hashlib
import json
import os
import re

SOURCES = {'steam': 'STEAM', 'epic': 'EPIC GAMES', 'gog': 'GOG', 'ubisoft': 'UBISOFT CONNECT', 'ea': 'EA APP', 'folder': 'PC • GAME LOKAL'}
# Launcher links LinguaPlay may open; anything else is launched by its EXE.
LAUNCH_SCHEMES = ('steam://', 'com.epicgames.launcher://', 'uplay://')
SKIP_EXE = re.compile(r'(unins|uninstall|setup|install|redist|vcredist|dxsetup|crash|report|helper|updater|update|'
                      r'launcherpatcher|easyanticheat|eac|battleye|be_service|cefprocess|webhelper|dotnet|ue4prereq|'
                      r'touchup|cleanup|activation|register|config|settings|benchmark|server)', re.I)


def _game(source, key, name, root, executable='', launch_uri='', cover=''):
    identity = f'{source}-' + (key if source != 'folder' else hashlib.sha256(str(root).casefold().encode()).hexdigest()[:16])
    return {'id': identity, 'name': name, 'root': str(root), 'executable': str(executable) if executable else '',
            'steam_id': '', 'cover': cover, 'hero': '', 'last_played': '', 'source': source, 'launch_uri': launch_uri}


def pick_executable(root, max_depth=3):
    """Best guess for a game's main EXE: skip tools, prefer a name like the folder, else the largest."""
    root = Path(root); candidates = []
    words = {w for w in re.split(r'[^a-z0-9]+', root.name.lower()) if len(w) > 2}
    for folder, dirs, files in os.walk(root):
        depth = len(Path(folder).relative_to(root).parts)
        if depth >= max_depth: dirs[:] = []
        dirs[:] = [d for d in dirs if not SKIP_EXE.search(d) and d.lower() not in ('_commonredist', 'redist', 'directx', 'support', 'tools')]
        for name in files:
            if not name.lower().endswith('.exe') or SKIP_EXE.search(name): continue
            path = Path(folder) / name
            try: size = path.stat().st_size
            except OSError: continue
            score = (sum(w in name.lower() for w in words), -depth, size)
            candidates.append((score, path))
    return max(candidates)[1] if candidates else None


def discover_epic(manifests=None):
    folder = Path(manifests) if manifests else Path(os.environ.get('PROGRAMDATA', r'C:\ProgramData')) / 'Epic' / 'EpicGamesLauncher' / 'Data' / 'Manifests'
    games = []
    for item in sorted(folder.glob('*.item')) if folder.is_dir() else []:
        try:
            data = json.loads(item.read_text(encoding='utf-8'))
            if data.get('bIsApplication') is False or 'applications' in data.get('AppCategories', []) or 'games' not in data.get('AppCategories', ['games']):
                continue
            root = Path(data['InstallLocation']); app = str(data['AppName'])
            if not root.is_dir() or not re.fullmatch(r'[A-Za-z0-9_.-]+', app): continue
            exe = root / data.get('LaunchExecutable', '') if data.get('LaunchExecutable') else pick_executable(root)
            games.append(_game('epic', app, data.get('DisplayName') or root.name, root, exe if exe and Path(exe).is_file() else '',
                               f'com.epicgames.launcher://apps/{app}?action=launch&silent=true'))
        except (OSError, ValueError, KeyError, TypeError): continue
    return games


def _registry_children(path):
    try:
        import winreg
    except ImportError:
        return []
    result = []
    for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ | view) as key:
                for index in range(winreg.QueryInfoKey(key)[0]):
                    name = winreg.EnumKey(key, index); values = {}
                    with winreg.OpenKey(key, name) as child:
                        for value_index in range(winreg.QueryInfoKey(child)[1]):
                            value_name, value, _ = winreg.EnumValue(child, value_index)
                            if isinstance(value, str): values[value_name] = value
                    result.append((name, values))
        except OSError: continue
    return result


def discover_gog(entries=None):
    games = []
    for key, values in entries if entries is not None else _registry_children(r'SOFTWARE\GOG.com\Games'):
        root = Path(values.get('path', ''))
        if not key.isdigit() or not values.get('path') or not root.is_dir(): continue
        exe = Path(values['exe']) if values.get('exe') else pick_executable(root)
        games.append(_game('gog', key, values.get('gameName') or root.name, root, exe if exe and exe.is_file() else ''))
    return games


def discover_ubisoft(entries=None):
    games = []
    for key, values in entries if entries is not None else _registry_children(r'SOFTWARE\Ubisoft\Launcher\Installs'):
        root = Path(values.get('InstallDir', ''))
        if not key.isdigit() or not values.get('InstallDir') or not root.is_dir(): continue
        exe = pick_executable(root)
        games.append(_game('ubisoft', key, root.name, root, exe or '', f'uplay://launch/{key}/0'))
    return games


def discover_ea(entries=None):
    games = []
    for key, values in entries if entries is not None else _registry_children(r'SOFTWARE\EA Games'):
        root = Path(values.get('Install Dir', ''))
        if not values.get('Install Dir') or not root.is_dir(): continue
        exe = pick_executable(root)
        name = values.get('DisplayName', key).replace('\ufffd', '').replace('™', '').strip() or key
        games.append(_game('ea', re.sub(r'[^A-Za-z0-9]+', '-', key).strip('-').lower(), name, root, exe or ''))
    return games


def default_game_folders():
    """'Games' folders at the root of each drive, e.g. F:\\Games."""
    folders = []
    for letter in 'CDEFGHIJ':
        for name in ('Games', 'Game', 'My Games'):
            path = Path(f'{letter}:\\') / name
            if path.is_dir(): folders.append(path)
    return folders


def discover_folder(folder):
    """Each subfolder holding a game EXE becomes a library entry (install folders such as F:\\Games)."""
    games = []
    try: children = sorted(p for p in Path(folder).iterdir() if p.is_dir())
    except OSError: return games
    for child in children:
        exe = pick_executable(child)
        if exe: games.append(_game('folder', '', child.name, child, exe))
    return games


def discover_other(folders=None):
    """All non-Steam sources; entries sharing an install folder are reported once."""
    found = []
    for finder in (discover_epic, discover_gog, discover_ubisoft, discover_ea):
        try: found.extend(finder())
        except Exception: continue
    for folder in default_game_folders() if folders is None else folders:
        found.extend(discover_folder(folder))
    unique = {}
    for game in found:
        unique.setdefault(str(Path(game['root']).resolve()).casefold(), game)
    return list(unique.values())
