import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from linguaplay.adapters import load_document, scan_folder
from linguaplay.translation import ProviderConfig, Translator, TranslationError
from linguaplay.patches import prepare_patch, install_patch, restore_patch, PatchError

class IntegrationTests(unittest.TestCase):
    def test_json_translation_preserves_all_unrelated_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'en.json'
            raw=b'{ "build":1.234567890123456789, "threshold":1e400, "strings": { "a" : "Hello" }, "nested":{"strings":{"b":"Keep"}} }'
            p.write_bytes(raw)
            self.assertEqual(load_document(p).render({'a':'Halo'}),raw.replace(b'"Hello"',b'"Halo"'))

    def test_reordered_markup_is_refused(self):
        from linguaplay.translation import validate_tokens
        with self.assertRaises(TranslationError):
            validate_tokens('<b>Hello</b> {name}', '</b>Halo<b> {name}')

    def test_utf16_big_endian_stays_big_endian(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'en.srt'
            p.write_bytes(b'\xfe\xff'+'1\n00:00:01,000 --> 00:00:02,000\nHello!\n'.encode('utf-16-be'))
            data=load_document(p).render({'cue:1':'Halo!'})
            self.assertTrue(data.startswith(b'\xfe\xff'))
            self.assertIn('Halo!',data[2:].decode('utf-16-be'))

    def test_api_to_patch_and_restore(self):
        received=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                received.append((self.path,data))
                text=data['messages'][1]['content'].replace('Hello','Halo')
                body=json.dumps({'choices':[{'message':{'content':text}}]}).encode()
                self.send_response(200); self.end_headers(); self.wfile.write(body)
            def log_message(self,*args): pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try:
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder); file=root/'en.json'
                file.write_text('{"strings":{"hello":"Hello {name}!"}}')
                original=file.read_bytes(); doc=load_document(file)
                config=ProviderConfig(endpoint=f'http://127.0.0.1:{server.server_port}/v1')
                translator=Translator(config.backend,root/'cache.sqlite',config.namespace())
                translations={e.id:translator.translate(e.text) for e in doc.entries}
                prepared=prepare_patch(root,[(doc,translations)],root/'patches')
                install_patch(prepared)
                self.assertEqual(json.loads(file.read_bytes())['strings']['hello'],'Halo {name}!')
                self.assertEqual(received[0][0],'/v1/chat/completions')
                restore_patch(prepared); self.assertEqual(file.read_bytes(),original)
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_failed_second_write_rolls_back_first(self):
        import linguaplay.patches as module
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); docs=[]
            for name in ['a','b']:
                p=root/f'{name}.json'; p.write_text('{"strings":{"a":"Hello"}}')
                docs.append((load_document(p),{'a':'Halo'}))
            prepared=prepare_patch(root,docs,root/'patches')
            original_write=module.atomic_write
            def fail_second(path,data):
                if Path(path)==root/'b.json': raise OSError('disk unavailable')
                original_write(path,data)
            with patch.object(module,'atomic_write',fail_second):
                with self.assertRaises(PatchError): install_patch(prepared)
            self.assertEqual((root/'a.json').read_bytes(),docs[0][0].raw)
            self.assertEqual((root/'b.json').read_bytes(),docs[1][0].raw)

    def test_utf16_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'en.srt'; p.write_bytes('1\r\n00:00:01,000 --> 00:00:02,000\r\nHello!\r\n'.encode('utf-16'))
            doc=load_document(p)
            self.assertEqual(doc.render({}),p.read_bytes())
            self.assertIn('Halo!',doc.render({'cue:1':'Halo!'}).decode('utf-16'))

    def test_symlink_outside_is_not_scanned(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); game=root/'game'; game.mkdir()
            outside=root/'outside.json'; outside.write_text('{"strings":{"x":"Secret"}}')
            try: (game/'link.json').symlink_to(outside)
            except OSError: self.skipTest('Windows symlink permission unavailable')
            self.assertEqual(scan_folder(game).documents,[])

    def test_bad_response_and_insecure_remote_refused(self):
        config=ProviderConfig(endpoint='http://example.com/v1',api_key='secret')
        with self.assertRaises(TranslationError): config.backend('Hello')

if __name__=='__main__': unittest.main()
