import hashlib
import struct
import tempfile
import unittest
from pathlib import Path
from linguaplay.adapters import load_document
from linguaplay.godot_text import Pck, parse_po, render_po
from linguaplay.patches import prepare_patch

PO='''msgid ""
msgstr ""
"Language: de\\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\\n"

#: res://ui/menu.tscn
msgid "Back To Main Menu"
msgstr "Zurück zum Hauptmenü"

msgid "Kick Player \\"{0}\\"?"
msgstr "Spieler \\"{0}\\" kicken?"

msgid "[p]Long text[\\\\/p]"
msgstr "[p]Langer Text[\\\\/p]"
'''

def pck(files):
    """Godot 4.4 style PCK v3 (directory at the end, file data relative to file_base)."""
    base=112; data=bytearray(); entries=[]
    for name,payload in files.items():
        data+=b'\0'*(-len(data)%32); entries.append((name,len(data),payload)); data+=payload
    directory=struct.pack('<I',len(entries))
    for name,offset,payload in entries:
        encoded=name.encode(); encoded+=b'\0'*(-len(encoded)%4)
        directory+=struct.pack('<I',len(encoded))+encoded+struct.pack('<QQ',offset,len(payload))+hashlib.md5(payload).digest()+struct.pack('<I',0)
    head=b'GDPC'+struct.pack('<IIII',3,4,4,1)+struct.pack('<IQQ',2,base,base+len(data))
    head+=b'\0'*(base-len(head))
    return head+bytes(data)+directory

class GodotPckTests(unittest.TestCase):
    def build(self,folder):
        path=Path(folder)/'Game.pck'
        path.write_bytes(pck({'scripts/a.gd':b'extends Node','data/localization/de/game.po':PO.encode(),'data/localization/ja/game.po':PO.encode()}))
        return path

    def test_reads_english_msgids_and_replaces_only_the_slot(self):
        with tempfile.TemporaryDirectory() as directory:
            doc=load_document(self.build(directory))
            self.assertIn('"de"',doc.format)
            self.assertEqual([e.text for e in doc.entries],['Back To Main Menu','Kick Player "{0}"?','[p]Long text{[\\/p]}'])
            out=doc.render({doc.entries[0].id:'Kembali ke Menu Utama',doc.entries[2].id:'[p]Teks panjang{[\\/p]}'})
            new=Pck(bytes(out)); self.assertEqual(new.read('scripts/a.gd'),b'extends Node'); self.assertEqual(new.read('data/localization/ja/game.po'),PO.encode())
            po={e['msgid']:e['msgstr'] for e in parse_po(new.read('data/localization/de/game.po').decode())}
            self.assertEqual(po['Back To Main Menu'],'Kembali ke Menu Utama')
            self.assertEqual(po['Kick Player "{0}"?'],'','Untranslated lines fall back to English, not German')
            self.assertEqual(po['[p]Long text[\\/p]'],'[p]Teks panjang[\\/p]')
            self.assertIn('nplurals=1',po[''])

    def test_patch_staging_rereads_translated_slot(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as storage:
            doc=load_document(self.build(directory))
            folder=prepare_patch(directory,[(doc,{doc.entries[0].id:'Kembali ke Menu Utama'})],storage)
            staged=next(p for p in Path(folder).iterdir() if p.name.endswith('Game.pck'))
            self.assertEqual(load_document(staged).entries[0].text,'Kembali ke Menu Utama')

    def test_po_round_trip_escapes(self):
        entries=parse_po(PO); self.assertEqual(parse_po(render_po(entries).decode()),entries)

if __name__=='__main__': unittest.main()
