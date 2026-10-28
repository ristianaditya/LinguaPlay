import json
from linguaplay.adapter_packages import validate_manifest, install_package


def test_validate_manifest_accepts_safe_support_pack(tmp_path):
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'id':'demo.game','version':'1.0.0','game_ids':['demo'],
                                    'formats':['.srt'],'entrypoint':'adapter.py'}), encoding='utf-8')
    result = validate_manifest(manifest)
    assert result['id'] == 'demo.game'
    assert result['entrypoint'] == 'adapter.py'


def test_validate_manifest_rejects_path_traversal(tmp_path):
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'id':'demo.game','version':'1.0.0','game_ids':['demo'],
                                    'formats':['.srt'],'entrypoint':'../adapter.py'}), encoding='utf-8')
    try:
        validate_manifest(manifest)
    except ValueError as exc:
        assert 'entrypoint' in str(exc)
    else:
        raise AssertionError('unsafe manifest accepted')


def test_install_package_copies_only_validated_pack(tmp_path):
    source = tmp_path / 'source'; source.mkdir()
    (source / 'manifest.json').write_text(json.dumps({'id':'demo.game','version':'1.0.0','game_ids':['demo'],
                                                       'formats':['.srt'],'entrypoint':'adapter.py'}), encoding='utf-8')
    (source / 'adapter.py').write_text('ADAPTER = True', encoding='utf-8')
    installed = install_package(source, tmp_path / 'packs')
    assert installed.name == 'demo.game'
    assert (installed / 'manifest.json').is_file()
    assert (installed / 'adapter.py').is_file()
