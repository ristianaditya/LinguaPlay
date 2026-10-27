import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from linguaplay.adapters import load_document, scan_folder
from linguaplay.dbpf_text import Package, parse_stbl, render_stbl, STBL_TYPE, refpack
from linguaplay.patches import prepare_patch

def package(resources):
    """resources: [(type, payload bytes, compression)] -> minimal DBPF 2.1 file."""
    body=bytearray(96); entries=[]
    for number,(kind,data,comp) in enumerate(resources):
        stored=zlib.compress(data) if comp==0x5A42 else data
        entries.append((kind,0,0,number+1,len(body),len(stored)|0x80000000,len(data),comp,1)); body+=stored
    index=struct.pack('<I',0)+b''.join(struct.pack('<IIIIIIIHH',*e) for e in entries)
    offset=len(body); body+=index
    body[0:4]=b'DBPF'; struct.pack_into('<II',body,4,2,1); struct.pack_into('<III',body,36,len(entries),0,len(index)); struct.pack_into('<Q',body,64,offset)
    return bytes(body)

ROWS=[(0x11,0,'{0.SimFirstName} is hungry'),(0x22,0,'Have a Sim reach max level\\nin a career'),(0x33,0,'Debug_Interaction_Name'),(0x44,0,'')]

class SimsStringTableTests(unittest.TestCase):
    def build(self,folder):
        path=Path(folder)/'Strings_ENG_US.package'
        path.write_bytes(package([(0x1A527DB,b'audio'*20,0x5A42),(STBL_TYPE,render_stbl(ROWS),0x5A42),(0x166038C,b'map',0)])); return path

    def test_reads_translatable_rows_and_round_trips(self):
        with tempfile.TemporaryDirectory() as directory:
            doc=load_document(self.build(directory))
            self.assertEqual([e.text for e in doc.entries],['{0.SimFirstName} is hungry','Have a Sim reach max level\\nin a career'])
            self.assertEqual(doc.render({}),doc.raw)
            out=doc.render({doc.entries[0].id:'{0.SimFirstName} lapar'})
            old,new=Package(doc.raw),Package(out)
            self.assertEqual(old.read(old.entries[0]),new.read(new.entries[0])); self.assertEqual(old.read(old.entries[2]),new.read(new.entries[2]))
            rows=parse_stbl(new.read(new.entries[1]))
            self.assertEqual(rows[0],(0x11,0,'{0.SimFirstName} lapar')); self.assertEqual(rows[2],(0x33,0,'Debug_Interaction_Name'))

    def test_patch_staging_rereads_and_other_packages_are_skipped(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as storage:
            doc=load_document(self.build(directory))
            folder=prepare_patch(directory,[(doc,{doc.entries[1].id:'Capai level maksimal\\ndalam karier'})],storage)
            self.assertTrue(any(p.name.endswith('Strings_ENG_US.package') for p in Path(folder).iterdir()))
            (Path(directory)/'ClientFullBuild0.package').write_bytes(package([(0x1,b'x',0)]))
            (Path(directory)/'Strings_FRE_FR.package').write_bytes(package([(STBL_TYPE,render_stbl(ROWS),0)]))
            self.assertEqual([d.path.name for d in scan_folder(directory).documents],['Strings_ENG_US.package'])

    def test_refpack_literal_and_copy_commands(self):
        # Header (size 9), 0xE0 = 4 literal bytes, 0x08 0x03 = copy 5 bytes from 4 back, 0xFC = stop.
        data=bytes([0x10,0xFB,0,0,9,0xE0])+b'abcd'+bytes([0x08,0x03,0xFC])
        self.assertEqual(refpack(data),b'abcdabcda')
        with self.assertRaises(ValueError): refpack(bytes([0x10,0xFB,0,0,20,0xE0])+b'abcd'+bytes([0xFC]))

if __name__=='__main__': unittest.main()
