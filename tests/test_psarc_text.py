import hashlib
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from linguaplay.adapters import load_document, scan_folder
from linguaplay.patches import prepare_patch
from linguaplay.psarc_text import Psarc, parse_table, SOURCE_TABLE

def table(rows):
    """rows: [(hash, text)] -> Naughty Dog text table bytes."""
    blob=bytearray(b'UNTRANSLATED STRING!!!\x00'); pairs=[]
    for key,text in sorted(rows):
        pairs.append((key,len(blob))); blob+=text.encode()+b'\x00'
    return struct.pack('>I',len(pairs))+b''.join(struct.pack('>II',*p) for p in pairs)+bytes(blob)

def archive(members,padding=b'PAD'):
    """Minimal zlib PSARC v1.4; members is {name: bytes}. Padding sits between members like real archives."""
    names=list(members); payloads=['\n'.join(names).encode()]+[members[n] for n in names]
    blocks=[]; datas=[]; entries=[]
    for payload in payloads:
        start=len(blocks); stored=bytearray()
        for i in range(0,len(payload),65536):
            piece=payload[i:i+65536]; packed=zlib.compress(piece)
            chunk=packed if len(packed)<len(piece) else piece
            blocks.append(len(chunk)); stored+=chunk
        datas.append(bytes(stored)+padding); entries.append((start,len(payload)))
    toc_length=32+len(payloads)*30+len(blocks)*2; offset=toc_length; toc=b''
    for (start,size),data,name in zip(entries,datas,['']+names):
        toc+=hashlib.md5(name.encode()).digest()+struct.pack('>I',start)+size.to_bytes(5,'big')+offset.to_bytes(5,'big'); offset+=len(data)
    toc+=b''.join(b.to_bytes(2,'big') for b in blocks)
    header=struct.pack('>4sI4sIIIII',b'PSAR',0x00010004,b'zlib',toc_length,30,len(payloads),65536,0)
    return header+toc+b''.join(datas)

ENGLISH=[(0x10,'Hello, Elena.'),(0x20,'-Hey! \\ -Hey!'),(0x30,'Kublai_Khan treasure.')]

class PsarcTextTests(unittest.TestCase):
    def build(self,root):
        members={'text1/ps4/2.subtitles':table(ENGLISH),'text1/ps4/7.subtitles':table(ENGLISH),
                 'text1/ps4/10.subtitles':table([(0x10,'Hallo, Elena.'),(0x20,'-Hé! \\ -Hé!'),(0x30,'Schat.')]),
                 'effect1/big.bin':bytes(range(256))*600}
        path=Path(root)/'core.psarc'; path.write_bytes(archive(members)); return path

    def test_reads_subtitles_and_display_markup(self):
        with tempfile.TemporaryDirectory() as directory:
            doc=load_document(self.build(directory))
            self.assertEqual([e.text for e in doc.entries],['Hello, Elena.','-Hey!\n-Hey!','Kublai Khan treasure.'])
            self.assertEqual(doc.render({}),doc.raw)

    def test_render_replaces_only_english_tables_and_round_trips(self):
        with tempfile.TemporaryDirectory() as directory:
            doc=load_document(self.build(directory))
            out=doc.render({'sub:00000010':'Halo, Elena.','sub:00000020':'-Hei!\n-Hei!'})
            old,new=Psarc(doc.raw),Psarc(out)
            changed=[n for n,i in old.names.items() if old.read(i)!=new.read(i)]
            self.assertEqual(sorted(changed),['text1/ps4/2.subtitles','text1/ps4/7.subtitles'])
            rows={k:t for k,_,t in parse_table(new.read(new.names[SOURCE_TABLE]))}
            self.assertEqual(rows,{0x10:'Halo, Elena.',0x20:'-Hei! \\ -Hei!',0x30:'Kublai_Khan treasure.'})
            # Untouched members keep their exact original compressed bytes.
            self.assertIn(old.raw[old.toc_length:],out)

    def test_in_game_text_keeps_buttons_and_values_and_skips_internal_names(self):
        common=[(0x10,'Press |C| to drop'),(0x20,'Collected [#COUNT] of [A] treasures'),(0x30,'Marco_Polo'),(0x40,'Odd || markup')]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'core.psarc'
            path.write_bytes(archive({'text1/ps4/2.subtitles':table(ENGLISH),'text1/ps4/2.common':table(common),'text1/ps4/7.common':table(common)}))
            doc=load_document(path); ui={e.id:e.text for e in doc.entries if e.id.startswith('ui:')}
            self.assertEqual(ui,{'ui:00000010':'Press {|C|} to drop','ui:00000020':'Collected {[#COUNT]} of [A] treasures'})
            out=doc.render({'ui:00000010':'Tekan {|C|} untuk turun','ui:00000020':'Terkumpul {[#COUNT]} dari [A] harta'})
            new=Psarc(out)
            for name in ('text1/ps4/2.common','text1/ps4/7.common'):
                rows={k:t for k,_,t in parse_table(new.read(new.names[name]))}
                self.assertEqual(rows[0x10],'Tekan |C| untuk turun'); self.assertEqual(rows[0x20],'Terkumpul [#COUNT] dari [A] harta'); self.assertEqual(rows[0x30],'Marco_Polo')
            with self.assertRaises(ValueError): doc.render({'ui:00000010':'Tekan | untuk turun'})

    def test_patch_staging_validates_reread(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as storage:
            doc=load_document(self.build(directory))
            folder=prepare_patch(directory,[(doc,{'sub:00000010':'Halo, Elena.'})],storage)
            self.assertEqual(load_document(folder/'0.core.psarc').entries[0].text,'Halo, Elena.')

    def test_rejects_markup_in_translation_and_unrelated_archives(self):
        with tempfile.TemporaryDirectory() as directory:
            doc=load_document(self.build(directory))
            with self.assertRaises(ValueError): doc.render({'sub:00000010':'Halo_Elena'})
            (Path(directory)/'audio.psarc').write_bytes(archive({'speech/a.xvag':b'x'*100}))
            report=scan_folder(directory)
            self.assertEqual([d.path.name for d in report.documents],['core.psarc'])
            self.assertIn('tidak berisi tabel subtitle',report.unsupported[0]['reason'])
            (Path(directory)/'broken.psarc').write_bytes(b'PSAR'+b'\x00'*10)
            with self.assertRaises(ValueError): load_document(Path(directory)/'broken.psarc')

if __name__=='__main__': unittest.main()
