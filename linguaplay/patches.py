"""Staged, byte-exact backups with journalled install and recoverable restore."""
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import tempfile
import uuid
from .adapters import digest, load_document
from .translation import validate_tokens

class PatchError(ValueError):
    pass

def atomic_write(path, data):
    path=Path(path)
    fd,name=tempfile.mkstemp(prefix='.linguaplay-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)

def _save(folder,manifest):
    atomic_write(Path(folder)/'manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2).encode())

def _load(folder):
    folder=Path(folder).resolve(strict=True)
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema')!=1 or not manifest.get('files'):
        raise PatchError('Manifest patch tidak valid.')
    root=Path(manifest['root']).resolve(strict=True)
    seen=set()
    for item in manifest['files']:
        rel=Path(item['path'])
        if rel.is_absolute() or '..' in rel.parts or str(rel).lower() in seen:
            raise PatchError('Path patch tidak valid.')
        seen.add(str(rel).lower())
        target=root/rel
        if not target.resolve().is_relative_to(root) or any(p.is_symlink() for p in [target,*target.parents] if p!=root.parent):
            raise PatchError('Path patch keluar dari folder game atau berupa symlink.')
        for key in ('backup','staged'):
            value=Path(item[key])
            if value.is_absolute() or len(value.parts)!=1:
                raise PatchError('Path payload tidak valid.')
    return folder,manifest,root

def prepare_patch(root, documents, storage):
    root=Path(root).resolve(strict=True)
    documents=list(documents)
    if not documents: raise PatchError('Tidak ada file dipilih.')
    folder=Path(storage)/uuid.uuid4().hex
    folder.mkdir(parents=True)
    manifest={'schema':1,'root':str(root),'created':datetime.now(timezone.utc).isoformat(),'status':'prepared','files':[]}
    seen=set()
    for index,(doc,mapping) in enumerate(documents):
        if doc.path.is_symlink() or not doc.path.resolve().is_relative_to(root):
            raise PatchError('File berada di luar folder game.')
        rel=str(doc.path.resolve().relative_to(root))
        if rel.lower() in seen: raise PatchError('File duplikat.')
        seen.add(rel.lower())
        if not mapping or set(mapping)-{e.id for e in doc.entries}:
            raise PatchError('Tidak ada terjemahan atau ID tidak dikenal.')
        for entry in doc.entries: validate_tokens(entry.text,mapping.get(entry.id,entry.text))
        rendered=doc.render(mapping)
        backup=f'{index}.original'; staged=f'{index}{doc.path.suffix.lower()}'
        (folder/backup).write_bytes(doc.raw)
        (folder/staged).write_bytes(rendered)
        check=load_document(folder/staged)
        if [(e.id,e.text.replace('\r\n','\n')) for e in check.entries] != [(e.id,mapping.get(e.id,e.text).replace('\r\n','\n')) for e in doc.entries]:
            raise PatchError('Validasi baca ulang terjemahan gagal.')
        manifest['files'].append({'path':rel,'backup':backup,'staged':staged,'original_hash':doc.sha256,'installed_hash':digest(rendered)})
    _save(folder,manifest)
    return folder

def _payload(folder,item,key):
    data=(folder/item[key]).read_bytes()
    expected=item['original_hash' if key=='backup' else 'installed_hash']
    if digest(data)!=expected: raise PatchError('Checksum backup/patch tidak cocok. File tidak diubah.')
    return data

def install_patch(folder,process_root=None):
    folder,manifest,root=_load(folder)
    from .process_guard import assert_folder_idle
    guard=Path(process_root).resolve() if process_root else root
    if not root.is_relative_to(guard): raise PatchError('Folder proses tidak mencakup folder subtitle.')
    assert_folder_idle(guard)
    if manifest['status'] not in ('prepared','restored'): raise PatchError('Patch ini tidak berstatus siap pasang.')
    payloads=[]
    for item in manifest['files']:
        if digest((root/item['path']).read_bytes())!=item['original_hash']:
            raise PatchError(f"File berubah sejak dipindai: {item['path']}. Pindai ulang.")
        _payload(folder,item,'backup')
        payloads.append(_payload(folder,item,'staged'))
    manifest['status']='installing'; _save(folder,manifest)
    written=[]
    try:
        for item,data in zip(manifest['files'],payloads):
            target=root/item['path']
            if digest(target.read_bytes())!=item['original_hash']:
                raise PatchError('File berubah saat pemasangan.')
            atomic_write(target,data); written.append(item)
        manifest['status']='installed'; _save(folder,manifest)
    except Exception as exc:
        manifest['status']='recovery_required'; _save(folder,manifest)
        for item in reversed(written):
            target=root/item['path']
            if digest(target.read_bytes())==item['installed_hash']:
                atomic_write(target,_payload(folder,item,'backup'))
        manifest['status']='prepared'; _save(folder,manifest)
        raise PatchError('Pemasangan gagal; perubahan yang dipasang telah dikembalikan. '+str(exc)) from exc

def restore_patch(folder,process_root=None):
    folder,manifest,root=_load(folder)
    from .process_guard import assert_folder_idle
    guard=Path(process_root).resolve() if process_root else root
    if not root.is_relative_to(guard): raise PatchError('Folder proses tidak mencakup folder subtitle.')
    assert_folder_idle(guard)
    if manifest['status'] not in ('installed','installing','restoring','recovery_required'):
        raise PatchError('Patch tidak terpasang atau sudah dipulihkan.')
    payloads=[]
    for item in manifest['files']:
        current=digest((root/item['path']).read_bytes())
        if current not in (item['installed_hash'],item['original_hash']):
            raise PatchError(f"Pemulihan ditolak: {item['path']} diubah oleh program lain.")
        payloads.append(_payload(folder,item,'backup'))
    manifest['status']='restoring'; _save(folder,manifest)
    for item,data in zip(manifest['files'],payloads):
        current=digest((root/item['path']).read_bytes())
        if current not in (item['installed_hash'],item['original_hash']):
            raise PatchError('File berubah saat pemulihan. Coba pulihkan kembali setelah game ditutup.')
        atomic_write(root/item['path'],data)
    manifest['status']='restored'; _save(folder,manifest)

def list_patches(storage):
    result=[]
    for path in Path(storage).glob('*/manifest.json'):
        try:
            manifest=json.loads(path.read_text(encoding='utf-8'))
            result.append((path.parent,manifest))
        except (OSError,ValueError): pass
    return sorted(result,key=lambda x:x[1].get('created',''),reverse=True)

def verify_installed_patch(folder):
    folder,manifest,root=_load(folder)
    if manifest['status']!='installed': raise PatchError('Patch belum terpasang.')
    for item in manifest['files']:
        if digest((root/item['path']).read_bytes())!=item['installed_hash']:
            raise PatchError('File patch berubah. Periksa Cadangan sebelum menjalankan game.')
