from pathlib import Path
import psutil

def running_in_folder(folder,executable=''):
    root=Path(folder).resolve(); name=Path(executable).name.casefold() if executable else ''
    for process in psutil.process_iter(['exe','name']):
        info=process.info
        if info.get('exe'):
            try:
                if Path(info['exe']).resolve().is_relative_to(root): return True
            except OSError: pass
        elif name and (info.get('name') or '').casefold()==name: return True
    return False

def assert_folder_idle(folder):
    if running_in_folder(folder):
        raise ValueError('Game masih berjalan. Tutup game sebelum mengubah file subtitle.')
