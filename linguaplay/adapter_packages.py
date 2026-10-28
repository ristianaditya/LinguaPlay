"""Validation for user-provided game support pack manifests."""
from pathlib import Path
import json
import re

_ID = re.compile(r'^[a-z0-9][a-z0-9._-]{1,63}$')
_VERSION = re.compile(r'^\d+\.\d+\.\d+$')


def validate_manifest(path):
    path = Path(path).resolve(strict=True)
    if path.name.casefold() != 'manifest.json':
        raise ValueError('Paket dukungan harus memiliki manifest.json.')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError('manifest.json tidak valid.') from exc
    if not isinstance(data, dict) or not _ID.fullmatch(str(data.get('id',''))):
        raise ValueError('ID paket tidak valid.')
    if not _VERSION.fullmatch(str(data.get('version',''))):
        raise ValueError('Versi paket harus memakai format major.minor.patch.')
    game_ids = data.get('game_ids'); formats = data.get('formats')
    if not isinstance(game_ids, list) or not game_ids or not all(isinstance(x,str) and x for x in game_ids):
        raise ValueError('game_ids harus berupa daftar yang tidak kosong.')
    if not isinstance(formats, list) or not formats or not all(isinstance(x,str) and x.startswith('.') for x in formats):
        raise ValueError('formats harus berisi ekstensi file.')
    entrypoint = data.get('entrypoint','')
    if not isinstance(entrypoint,str) or not entrypoint or Path(entrypoint).is_absolute() or '..' in Path(entrypoint).parts:
        raise ValueError('entrypoint paket tidak aman.')
    return {'id':data['id'],'version':data['version'],'game_ids':list(game_ids),
            'formats':list(formats),'entrypoint':entrypoint}
