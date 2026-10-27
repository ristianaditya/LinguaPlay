"""Copy installed distribution notices beside a finished portable build."""
from pathlib import Path
import importlib.metadata as metadata
import shutil
import sys
import urllib.request

project=Path(__file__).resolve().parent.parent
destination=project/'portable'/'LinguaPlay'/'licenses'
destination.mkdir(parents=True,exist_ok=True)
for dist in metadata.distributions():
    name=dist.metadata.get('Name','unknown')
    target=destination/name
    for item in dist.files or []:
        low=str(item).lower()
        if '.dist-info/' in low and ('license' in low or 'copying' in low or 'notice' in low or low.endswith('/metadata')):
            source=Path(dist.locate_file(item))
            if source.is_file():
                target.mkdir(exist_ok=True)
                shutil.copy2(source,target/source.name)
python_license=Path(sys.base_prefix)/'LICENSE.txt'
if python_license.is_file(): shutil.copy2(python_license,destination/'Python-LICENSE.txt')
for name in ['LGPL-3.0-only','GPL-3.0-only']:
    target=destination/(name+'.txt')
    if not target.exists():
        with urllib.request.urlopen(f'https://raw.githubusercontent.com/qt/qtbase/dev/LICENSES/{name}.txt',timeout=30) as response:
            target.write_bytes(response.read())
shutil.copy2(project/'THIRD_PARTY_NOTICES.md',destination/'THIRD_PARTY_NOTICES.md')
print('Notices:',destination)
