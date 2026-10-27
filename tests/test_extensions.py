import tempfile
import unittest
from pathlib import Path
from linguaplay.adapters import (register_adapter, unregister_adapter, load_document,
                                 scan_folder, Document, Entry)

class AdapterExtensionTests(unittest.TestCase):
    def test_new_adapter_is_detected_without_user_mapping(self):
        def reader(path):
            raw=path.read_bytes(); text=raw.decode()
            if not text.startswith('DIALOG/1\n'): raise ValueError('Invalid signature')
            return Document(path,'Example dialog v1',raw,text,'utf-8',[Entry('cue:1',text[9:])],[(9,len(text))])
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); (root/'subtitle.dialog').write_bytes(b'DIALOG/1\nHello!')
            register_adapter('fixture-dialog',('.dialog',),reader)
            try:
                report=scan_folder(root)
                self.assertEqual(len(report.documents),1)
                self.assertEqual(report.documents[0].entries[0].text,'Hello!')
                self.assertEqual(report.documents[0].render({'cue:1':'Halo!'}),b'DIALOG/1\nHalo!')
            finally: unregister_adapter('fixture-dialog')

    def test_conflicting_registration_refused(self):
        with self.assertRaises(ValueError): register_adapter('srt',('.srt',),lambda path:None)

if __name__=='__main__': unittest.main()
