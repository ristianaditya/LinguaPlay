import struct
import tempfile
import unittest
from pathlib import Path
from linguaplay.adapters import load_document
from linguaplay.patches import prepare_patch
from linguaplay.unity_text import Bundle, SerializedFile, lz4_block

def type_tree():
    strings=bytearray(); offsets={}
    def at(text):
        if text not in offsets: offsets[text]=len(strings); strings.extend(text.encode()+b'\0')
        return offsets[text]
    nodes=[]
    def node(level,type_,name,size,meta=0): nodes.append(struct.pack('<HBBIIiiIQ',1,level,0,at(type_),at(name),size,len(nodes),meta,0))
    def string(level,name):
        node(level,'string',name,-1); node(level+1,'Array','Array',-1,0x4000); node(level+2,'int','size',4); node(level+2,'char','data',1)
    node(0,'MonoBehaviour','Base',-1,0x8000); string(1,'m_Name')
    node(1,'LocaleIdentifier','m_LocaleId',-1); string(2,'m_Code')
    node(1,'TableEntryData','m_TableData',-1); node(2,'Array','Array',-1); node(3,'int','size',4); node(3,'TableEntryData','data',-1)
    node(4,'SInt64','m_Id',8); string(4,'m_Localized')
    return struct.pack('<ii',len(nodes),len(strings))+b''.join(nodes)+bytes(strings)

def ustr(text):
    data=text.encode(); return struct.pack('<i',len(data))+data+b'\0'*(-len(data)%4)

def table(locale,rows):
    return ustr('UI_'+locale)+ustr(locale)+struct.pack('<i',len(rows))+b''.join(struct.pack('<q',k)+ustr(v) for k,v in rows)

def serialized(objects):
    meta=b'6000.0.0f1\0'+struct.pack('<i',19)+b'\1'+struct.pack('<i',1)+struct.pack('<iBh',114,0,-1)+b'\0'*32+type_tree()+struct.pack('<i',0)
    meta+=struct.pack('<i',len(objects)); body=bytearray(); table_bytes=b''
    for path_id,data in objects:
        body+=b'\0'*(-len(body)%8); start=len(body); body+=data
        meta+=b'\0'*(-(48+len(meta))%4)+struct.pack('<qQIi',path_id,start,len(data),0)
    data_offset=(48+len(meta)+15)//16*16; head=bytearray(48)
    struct.pack_into('>IIII',head,0,0,0,22,0); struct.pack_into('>IQQ',head,20,len(meta),data_offset+len(body),data_offset)
    return bytes(head)+meta+b'\0'*(data_offset-48-len(meta))+bytes(body)

def bundle(cab):
    info=b'\0'*16+struct.pack('>i',1)+struct.pack('>IIH',len(cab),len(cab),0)+struct.pack('>i',1)+struct.pack('>qqI',0,len(cab),4)+b'CAB-test\0'
    head=bytearray(b'UnityFS\0'+struct.pack('>I',8)+b'5.x.x\0'+b'6000.0.0f1\0'+b'\0'*20); head+=b'\0'*(-len(head)%16)
    struct.pack_into('>QIII',head,8+4+6+11,len(head)+len(info)+len(cab),len(info),len(info),0x40)
    return bytes(head)+info+cab

ENGLISH=[(1,'Yes'),(2,'Guest Number: {0}'),(3,'389fd902d0330504a9218b0bcdf2594a')]

class UnityStringTableTests(unittest.TestCase):
    def build(self,folder,locale='en',name='localization-string-tables-english(en)_assets_all.bundle'):
        path=Path(folder)/name; path.write_bytes(bundle(serialized([(7,table(locale,ENGLISH)),(9,b'\1\2\3\4')]))); return path

    def test_reads_english_strings_skips_guids_and_round_trips(self):
        with tempfile.TemporaryDirectory() as directory:
            doc=load_document(self.build(directory))
            self.assertEqual([e.text for e in doc.entries],['Yes','Guest Number: {0}'])
            self.assertEqual(doc.render({}),doc.raw)
            out=doc.render({doc.entries[1].id:'Nomor tamu yang panjang sekali: {0}'})
            new=SerializedFile(Bundle(out).file('CAB-test'))
            objects={o['path_id']:new.object_data(o) for o in new.objects}
            self.assertEqual(objects[9],b'\1\2\3\4','Other objects are copied unchanged')
            self.assertEqual(objects[7],table('en',[(1,'Yes'),(2,'Nomor tamu yang panjang sekali: {0}'),ENGLISH[2]]))

    def test_other_languages_are_not_exposed_and_staging_rereads(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as storage:
            with self.assertRaises(ValueError): load_document(self.build(directory,'de','localization-string-tables-german(de)_assets_all.bundle'))
            doc=load_document(self.build(directory))
            folder=prepare_patch(directory,[(doc,{doc.entries[0].id:'Ya'})],storage)
            staged=next(p for p in Path(folder).iterdir() if p.name.endswith('.bundle'))
            self.assertEqual(load_document(staged).entries[0].text,'Ya')

    def test_lz4_block_literals_and_overlapping_match(self):
        # "abc" literals, then a match of 6 bytes at offset 3 (overlapping copy), then final literal "!".
        data=bytes([0x32])+b'abc'+bytes([3,0])+bytes([0x10])+b'!'
        self.assertEqual(lz4_block(data,10),b'abcabcabc!')
        with self.assertRaises(ValueError): lz4_block(data,11)

if __name__=='__main__': unittest.main()
