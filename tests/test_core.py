import json
from pathlib import Path
import unittest
import tempfile
from contextlib import contextmanager

@contextmanager
def raises(error):
    try:
        yield
    except error:
        return
    raise AssertionError(f"Expected {error.__name__}")

from linguaplay.adapters import load_document, scan_folder
from linguaplay.translation import Translator, TranslationError
from linguaplay.patches import prepare_patch, install_patch, restore_patch, PatchError

SRT = '1\r\n00:00:01,000 --> 00:00:03,000\r\nHello, {player}! <i>Stay here.</i>\r\n\r\n2\r\n00:00:04,000 --> 00:00:05,000\r\nLet us go!\r\n'

def test_srt_roundtrip_and_structure(tmp_path):
    p = tmp_path / 'en.srt'; p.write_bytes(b'\xef\xbb\xbf' + SRT.encode())
    d = load_document(p)
    assert len(d.entries) == 2
    assert d.render({}) == p.read_bytes()
    result = d.render({d.entries[0].id: 'Halo, {player}! <i>Tunggu.</i>'})
    assert b'00:00:01,000 --> 00:00:03,000\r\n' in result
    assert b'Halo' in result and result.startswith(b'\xef\xbb\xbf')

def test_vtt_preserves_notes_and_identifiers(tmp_path):
    p = tmp_path / 'en.vtt'
    text = 'WEBVTT\n\nNOTE hello\nnot dialogue\n\nintro\n00:01.000 --> 00:03.000 align:start\nHello!\n'
    p.write_text(text, encoding='utf-8')
    d = load_document(p)
    assert [e.text for e in d.entries] == ['Hello!']
    result = d.render({d.entries[0].id: 'Halo!' }).decode().replace('\r\n','\n')
    assert 'NOTE hello\nnot dialogue' in result and 'intro\n00:01.000' in result

def test_json_only_explicit_strings_schema(tmp_path):
    p = tmp_path / 'language.json'
    p.write_text(json.dumps({'locale':'en', 'strings':{'a':'Hello'}, 'version':2}))
    d = load_document(p)
    assert json.loads(d.render({'a':'Halo'})) == {'locale':'en','strings':{'a':'Halo'},'version':2}
    p.write_text('{"password":"not a subtitle"}')
    with raises(ValueError): load_document(p)

def test_scan_rejects_malformed_and_records_unknown(tmp_path):
    (tmp_path/'bad.srt').write_text('This is not a subtitle')
    (tmp_path/'data.pak').write_bytes(b'PACK' + b'\0'*20)
    (tmp_path/'valid.srt').write_bytes(SRT.encode())
    report = scan_folder(tmp_path)
    assert len(report.documents) == 1
    assert len(report.unsupported) == 2

def test_tokens_protected_and_cache_used(tmp_path):
    calls=[]
    def backend(text):
        calls.append(text)
        assert '{player}' not in text and '<i>' not in text
        return text.replace('Hello', 'Halo')
    t = Translator(backend, tmp_path/'cache.sqlite', 'test-en-id')
    text='Hello {player}, <i>%s</i> [color=red]friend[/color]'
    assert t.translate(text) == text.replace('Hello','Halo')
    assert t.translate(text) == text.replace('Hello','Halo')
    assert len(calls) == 1

def test_missing_tokens_refused(tmp_path):
    t = Translator(lambda text: 'Halo', tmp_path/'cache.sqlite', 'test')
    with raises(TranslationError): t.translate('Hello {player}')

def test_install_and_restore_exact_bytes(tmp_path):
    root=tmp_path/'game'; root.mkdir()
    p=root/'en.srt'; p.write_bytes(SRT.encode())
    d=load_document(p)
    patch=prepare_patch(root, [(d, {d.entries[0].id:'Halo, {player}! <i>Tunggu.</i>'})], tmp_path/'patches')
    assert p.read_bytes() == SRT.encode()
    install_patch(patch)
    assert b'Halo' in p.read_bytes()
    restore_patch(patch)
    assert p.read_bytes() == SRT.encode()

def test_install_refuses_changed_file(tmp_path):
    p=tmp_path/'en.srt'; p.write_bytes(SRT.encode()); d=load_document(p)
    patch=prepare_patch(tmp_path, [(d,{d.entries[1].id:'Ayo!'})],tmp_path/'patches')
    p.write_text('updated by game')
    with raises(PatchError): install_patch(patch)
    assert p.read_text() == 'updated by game'

def test_restore_refuses_external_modification(tmp_path):
    p=tmp_path/'en.srt'; p.write_bytes(SRT.encode()); d=load_document(p)
    patch=prepare_patch(tmp_path,[(d,{d.entries[1].id:'Ayo!'})],tmp_path/'patches')
    install_patch(patch); p.write_text('new update')
    with raises(PatchError): restore_patch(patch)
    assert p.read_text() == 'new update'


def _wrap(fn):
    def run(self):
        with tempfile.TemporaryDirectory() as folder:
            fn(Path(folder))
    return run

class CoreTests(unittest.TestCase):
    pass

for _name, _fn in list(globals().items()):
    if _name.startswith('test_'):
        setattr(CoreTests, _name, _wrap(_fn))
del _name, _fn

if __name__ == '__main__':
    unittest.main()
