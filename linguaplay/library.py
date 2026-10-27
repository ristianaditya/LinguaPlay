"""Local game catalogue and explicit original/translated launch preparation."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import subprocess
from .patches import atomic_write, list_patches, install_patch, restore_patch, verify_installed_patch, PatchError
from .adapters import digest


class GameLibrary:
    def __init__(self,data):
        self.data=Path(data); self.data.mkdir(parents=True,exist_ok=True)
        self.path=self.data/'library.json'; self.profiles_path=self.data/'game-profiles.json'; self.games=[]; self.load_warning=''
        self.profiles={}
        if self.profiles_path.exists():
            try:
                value=json.loads(self.profiles_path.read_text(encoding='utf-8'))
                if isinstance(value,dict): self.profiles=value
            except (OSError,UnicodeError,ValueError):
                self.profiles={}
        if self.path.exists():
            try:
                document=json.loads(self.path.read_text(encoding='utf-8'))
                if not isinstance(document,dict) or document.get('schema')!=1 or not isinstance(document.get('games'),list): raise ValueError()
                for game in document['games']:
                    if not isinstance(game,dict) or any(not isinstance(game.get(key),str) for key in ('id','name','root','executable','steam_id','cover')): raise ValueError()
                    if not game['id'] or not game['name'] or not Path(game['root']).is_absolute(): raise ValueError()
                self.games=document['games']
            except (ValueError,UnicodeError):
                backup=self.path.with_name('library-unreadable-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')+'.json')
                self.path.replace(backup)
                self.load_warning='Library sebelumnya tidak dapat dibaca. Salinan asli disimpan sebagai '+backup.name+'. Tambahkan kembali game Anda; file game tetap utuh.'

    def save(self):
        atomic_write(self.path,json.dumps({'schema':1,'games':self.games},ensure_ascii=False,indent=2).encode())

    def get_profile(self, identity):
        profile=self.profiles.get(identity)
        if not isinstance(profile,dict): profile={}
        defaults={'source_language':'en','target_language':'id','adapter_id':'','support_level':'unknown',
                  'glossary_path':'','memory_path':'','overlay_profile_id':'default','last_scan':'',
                  'engine_name':'','anticheat':'','engine_note':''}
        result=defaults.copy(); result.update({k:v for k,v in profile.items() if k in defaults})
        return result

    def save_profile(self, identity, profile):
        if not isinstance(profile,dict): raise ValueError('Profil game harus berupa objek.')
        current=self.get_profile(identity); current.update({k:v for k,v in profile.items() if k in current})
        self.profiles[identity]=current
        atomic_write(self.profiles_path,json.dumps(self.profiles,ensure_ascii=False,indent=2).encode())

    def add(self,game):
        old=next((g for g in self.games if g['id']==game['id']),None)
        if old: return old
        self.games.append(game); self.save(); return game

    def add_executable(self,path,name=None):
        path=Path(path).resolve(strict=True)
        if not path.is_file() or path.suffix.lower()!='.exe': raise ValueError('Pilih file EXE game yang valid.')
        identity=hashlib.sha256(str(path).casefold().encode()).hexdigest()[:20]
        return self.add({'id':identity,'name':name or path.stem,'root':str(path.parent),'executable':str(path),'steam_id':'','cover':'','last_played':''})

    def remove(self,identity):
        self.games=[g for g in self.games if g['id']!=identity]; self.save()


def _fields(text):
    # VDF scalar pairs; nested blocks are ignored. No evaluation or expansion.
    return {k:v.replace('\\\\','\\') for k,v in re.findall(r'"([^"\r\n]+)"\s+"((?:\\.|[^"\\])*)"',text)}


def steam_roots():
    roots=[]
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam') as key:
            roots.append(Path(winreg.QueryValueEx(key,'SteamPath')[0]))
    except (ImportError,OSError): pass
    roots.extend(Path(os.environ.get(name,''))/'Steam' for name in ('ProgramFiles(x86)','ProgramFiles') if os.environ.get(name))
    return [r for r in roots if (r/'steamapps').is_dir()]


# Steam runtime/redistributable packages that appear as installed apps but are not games.
STEAM_TOOLS={'228980','1070560','1391110','1628350','1826330'}

def _cached_image(cache,appid,names):
    """Find artwork in the old flat cache (<id>_<name>.jpg) or the newer per-app folders,
    which may nest files one level deeper in a hash-named directory."""
    folder=cache/appid
    for name in names:
        for candidate in [*cache.glob(f'{appid}_{name}.*'),*folder.glob(f'{name}.*'),*folder.glob(f'*/{name}.*')]:
            if candidate.is_file() and candidate.suffix.lower() in ('.jpg','.jpeg','.png','.webp'):
                return str(candidate)
    return ''

def steam_artwork(clients,appid):
    """Local Steam library artwork only; nothing is downloaded."""
    for client in clients:
        cache=Path(client)/'appcache'/'librarycache'
        if not cache.is_dir(): continue
        cover=_cached_image(cache,appid,('library_600x900','library_capsule','header','library_header','library_hero'))
        hero=_cached_image(cache,appid,('library_hero','header','library_header'))
        if cover or hero: return {'cover':cover or hero,'hero':hero or cover}
    return {'cover':'','hero':''}

def discover_steam(roots=None):
    initial=list(roots if roots is not None else steam_roots()); libraries=list(initial)
    for root in initial:
        try:
            text=(Path(root)/'steamapps'/'libraryfolders.vdf').read_text(encoding='utf-8')
            libraries.extend(Path(p.replace('\\\\','\\')) for p in re.findall(r'"path"\s+"((?:\\.|[^"\\])*)"',text))
        except (OSError,UnicodeError): pass
    games={}
    for root in dict.fromkeys(Path(p).resolve() for p in libraries):
        for manifest in (root/'steamapps').glob('appmanifest_*.acf'):
            try:
                data=_fields(manifest.read_text(encoding='utf-8')); appid=data['appid']; install=data['installdir']
                if not appid.isdigit() or Path(install).name!=install or install in ('.','..'): continue
                folder=(root/'steamapps'/'common'/install).resolve()
                if not folder.is_dir(): continue
                if appid in STEAM_TOOLS: continue
                art=steam_artwork(initial,appid)
                games[appid]={'id':'steam-'+appid,'name':data.get('name',install),'root':str(folder),'executable':'','steam_id':appid,'cover':art['cover'],'hero':art['hero'],'last_played':''}
            except (OSError,UnicodeError,KeyError): continue
    return sorted(games.values(),key=lambda g:g['name'].casefold())


def patches_for(game,storage):
    root=Path(game['root']).resolve()
    return [(p,m) for p,m in list_patches(storage) if m.get('root') and Path(m['root']).resolve().is_relative_to(root)]


def game_patch_state(game,storage):
    patches=patches_for(game,storage)
    if any(m.get('status') in ('installing','restoring','recovery_required') for _,m in patches): return 'recovery'
    if any(m.get('status')=='installed' for _,m in patches): return 'installed'
    if any(m.get('status') in ('prepared','restored') for _,m in patches): return 'ready'
    return 'original'


def is_running(game):
    from .process_guard import running_in_folder
    return running_in_folder(game['root'],game.get('executable',''))


def set_play_mode(game,storage,mode,running=is_running):
    if mode not in ('original','translated'): raise ValueError('Mode permainan tidak dikenal.')
    if running(game): raise ValueError('Game masih berjalan. Tutup game sebelum mengubah patch atau memulai sesi baru.')
    patches=patches_for(game,storage)
    if game_patch_state(game,storage)=='recovery': raise PatchError('Patch perlu dipulihkan melalui Cadangan sebelum bermain.')
    active=[(p,m) for p,m in patches if m.get('status')=='installed']
    if mode=='original':
        for p,_ in active: restore_patch(p,game['root'])
        return
    selected=next(((p,m) for p,m in patches if m.get('status') in ('prepared','restored','installed')),None)
    if not selected: raise PatchError('Belum ada patch terjemahan. Siapkan terjemahan terlebih dahulu.')
    path,manifest=selected
    if manifest['status']=='installed':
        for active_path,_ in active: verify_installed_patch(active_path)
        return
    for p,_ in active: restore_patch(p,game['root'])
    install_patch(path,game['root'])

def validate_launch_target(game):
    root=Path(game['root'])
    if not root.is_dir(): raise ValueError('Folder game tidak ditemukan. Perbarui lokasi game.')
    if game.get('steam_id'):
        if not str(game['steam_id']).isdigit(): raise ValueError('ID game Steam tidak valid.')
    elif game.get('launch_uri','').startswith(('com.epicgames.launcher://','uplay://')) and not game.get('executable'):
        return
    else:
        exe=Path(game.get('executable',''))
        if not exe.is_file() or exe.suffix.lower()!='.exe' or not exe.resolve().is_relative_to(root.resolve()): raise ValueError('File EXE game tidak ditemukan di folder game. Perbarui lokasinya.')


def launch_executable(game):
    validate_launch_target(game)
    exe=Path(game.get('executable',''))
    if not exe.is_file() or exe.suffix.lower()!='.exe': raise ValueError('File EXE game tidak ditemukan. Perbarui lokasi game.')
    return subprocess.Popen([str(exe)],cwd=game['root'])
