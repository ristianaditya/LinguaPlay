import json
import tempfile
import unittest
from pathlib import Path
from linguaplay.library import GameLibrary, discover_steam, set_play_mode, game_patch_state
from linguaplay.adapters import load_document
from linguaplay.patches import prepare_patch, install_patch
from unittest.mock import patch as mock_patch

class GameLibraryTests(unittest.TestCase):
    def test_corrupt_library_is_preserved_and_can_be_rebuilt(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); file=root/'library.json'; original=b'{broken'; file.write_bytes(original)
            store=GameLibrary(root)
            self.assertEqual(store.games,[])
            self.assertTrue(store.load_warning)
            self.assertEqual(next(root.glob('library-unreadable-*.json')).read_bytes(),original)
            exe=root/'game.exe'; exe.touch(); store.add_executable(exe)
            self.assertEqual(len(GameLibrary(root).games),1)

    def test_nested_subtitle_patch_is_associated_and_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); exe=root/'game.exe'; exe.touch(); subtitles=root/'subtitles'; subtitles.mkdir()
            file=subtitles/'en.json'; file.write_text('{"strings":{"a":"Hello"}}')
            game=GameLibrary(root/'data').add_executable(exe)
            prepare_patch(subtitles,[(load_document(file),{'a':'Halo'})],root/'patches')
            self.assertEqual(game_patch_state(game,root/'patches'),'ready')
            set_play_mode(game,root/'patches','translated',running=lambda _:False)
            set_play_mode(game,root/'patches','translated',running=lambda _:False)

    def test_direct_patch_install_and_restore_refuse_running_game(self):
        from linguaplay.patches import restore_patch
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); file=root/'en.json'; file.write_text('{"strings":{"a":"Hello"}}')
            prepared=prepare_patch(root,[(load_document(file),{'a':'Halo'})],root/'patches')
            with mock_patch('linguaplay.process_guard.running_in_folder',return_value=True):
                with self.assertRaisesRegex(ValueError,'berjalan'): install_patch(prepared)
            install_patch(prepared)
            with mock_patch('linguaplay.process_guard.running_in_folder',return_value=True):
                with self.assertRaisesRegex(ValueError,'berjalan'): restore_patch(prepared)
            self.assertIn('Halo',file.read_text())

    def test_add_persist_deduplicate_and_remove_without_deleting_game(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); exe=root/'Adventure.exe'; exe.write_bytes(b'game')
            store=GameLibrary(root/'data'); game=store.add_executable(exe,'Adventure')
            self.assertEqual(store.add_executable(exe)['id'],game['id'])
            self.assertEqual(len(GameLibrary(root/'data').games),1)
            store.remove(game['id']); self.assertTrue(exe.exists())
            self.assertEqual(GameLibrary(root/'data').games,[])

    def test_patch_original_patch_switch_preserves_integrity_and_blocks_running(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); game_root=root/'game'; game_root.mkdir(); exe=game_root/'game.exe'; exe.touch()
            file=game_root/'en.json'; file.write_bytes(b'{"strings":{"a":"Hello"}}'); original=file.read_bytes()
            store=GameLibrary(root/'data'); game=store.add_executable(exe)
            patch=prepare_patch(game_root,[(load_document(file),{'a':'Halo'})],root/'patches')
            self.assertEqual(game_patch_state(game,root/'patches'),'ready')
            set_play_mode(game,root/'patches','translated',running=lambda _:False)
            self.assertIn(b'Halo',file.read_bytes())
            with self.assertRaisesRegex(ValueError,'berjalan'):
                set_play_mode(game,root/'patches','original',running=lambda _:True)
            self.assertIn(b'Halo',file.read_bytes())
            set_play_mode(game,root/'patches','original',running=lambda _:False)
            self.assertEqual(file.read_bytes(),original)
            set_play_mode(game,root/'patches','translated',running=lambda _:False)
            self.assertIn(b'Halo',file.read_bytes())
            file.write_bytes(b'changed by update')
            with self.assertRaises(ValueError):
                set_play_mode(game,root/'patches','translated',running=lambda _:False)

    def test_steam_discovery_reads_only_installed_manifests(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); apps=root/'steamapps'; apps.mkdir(); (apps/'common'/'Adventure').mkdir(parents=True)
            (apps/'appmanifest_42.acf').write_text('"AppState" { "appid" "42" "name" "My Adventure" "installdir" "Adventure" }')
            games=discover_steam([root]); self.assertEqual(len(games),1)
            self.assertEqual(games[0]['steam_id'],'42'); self.assertEqual(games[0]['name'],'My Adventure')
            (apps/'appmanifest_99.acf').write_text('"AppState" { "appid" "99" "name" "Missing" "installdir" "Missing" }')
            self.assertEqual(len(discover_steam([root])),1)

    def test_steam_artwork_supports_new_cache_folders_and_skips_redistributables(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); apps=root/'steamapps'; cache=root/'appcache'/'librarycache'
            for appid,name in (('42','Adventure'),('7','Puzzle'),('228980','Steamworks Common Redistributables')):
                (apps/'common'/name).mkdir(parents=True)
                (apps/f'appmanifest_{appid}.acf').write_text(f'"AppState" {{ "appid" "{appid}" "name" "{name}" "installdir" "{name}" }}')
            (cache/'42').mkdir(parents=True); (cache/'42'/'library_600x900.jpg').write_bytes(b'x'); (cache/'42'/'library_hero.jpg').write_bytes(b'x')
            (cache/'7'/'abc123').mkdir(parents=True); (cache/'7'/'abc123'/'library_capsule.jpg').write_bytes(b'x')
            games={g['steam_id']:g for g in discover_steam([root])}
            self.assertEqual(sorted(games),['42','7'])
            self.assertTrue(games['42']['cover'].endswith('library_600x900.jpg')); self.assertTrue(games['42']['hero'].endswith('library_hero.jpg'))
            self.assertTrue(games['7']['cover'].endswith('library_capsule.jpg'))

    def test_engine_and_anticheat_detection_explains_scan_and_blocks_patches(self):
        from linguaplay.adapters import scan_game_root
        from linguaplay.engines import identify_engine
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            unity=root/'unity'; unity.mkdir(); (unity/'UnityPlayer.dll').touch()
            godot=root/'godot'; godot.mkdir(); (godot/'Game.pck').write_bytes(b'GDPC'+b'\0'*12)
            unreal=root/'unreal'; (unreal/'Game'/'Content'/'Paks').mkdir(parents=True); (unreal/'Game'/'Content'/'Paks'/'Game.pak').touch()
            self.assertEqual(identify_engine(unity)['engine'],'unity')
            self.assertEqual(identify_engine(godot)['engine'],'godot')
            self.assertEqual(identify_engine(unreal)['engine'],'unreal')
            protected=root/'protected'; (protected/'EasyAntiCheat').mkdir(parents=True)
            (protected/'dialogue.en.srt').write_text('1\n00:00:01,000 --> 00:00:02,000\nHello\n')
            report=scan_game_root(protected)
            self.assertEqual(report['anticheat'],'EasyAntiCheat'); self.assertEqual(report['support_level'],'ocr')
            self.assertIn('ban',report['engine_note'])

    def test_untranslated_game_can_play_original_but_not_translated(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); exe=root/'game.exe'; exe.touch(); game=GameLibrary(root/'data').add_executable(exe)
            set_play_mode(game,root/'patches','original',running=lambda _:False)
            with self.assertRaisesRegex(ValueError,'patch'):
                set_play_mode(game,root/'patches','translated',running=lambda _:False)
