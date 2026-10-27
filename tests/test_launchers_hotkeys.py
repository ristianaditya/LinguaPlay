import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication
from linguaplay import hotkeys
from linguaplay.launchers import discover_epic, discover_folder, discover_gog, discover_other, pick_executable
from linguaplay.ui import MainWindow, configure_app

class LauncherTests(unittest.TestCase):
    def test_folder_discovery_picks_main_exe_and_skips_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            games=Path(directory); game=games/'Silver Pines'; (game/'_CommonRedist').mkdir(parents=True)
            (game/'Carpenter.exe').write_bytes(b'x'*500); (game/'UnityCrashHandler64.exe').write_bytes(b'x'*900)
            (game/'unins000.exe').write_bytes(b'x'*900); (game/'_CommonRedist'/'vcredist.exe').write_bytes(b'x'*900)
            (games/'Empty').mkdir()
            found=discover_folder(games)
            self.assertEqual([(g['name'],Path(g['executable']).name,g['source']) for g in found],[('Silver Pines','Carpenter.exe','folder')])
            self.assertEqual(pick_executable(games/'Empty'),None)

    def test_epic_skips_applications_and_gog_reads_registry_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); manifests=root/'manifests'; manifests.mkdir(); game=root/'Hades'; game.mkdir(); (game/'Hades.exe').touch()
            app=root/'Discord'; app.mkdir()
            (manifests/'a.item').write_text(json.dumps({'DisplayName':'Hades','AppName':'Min','InstallLocation':str(game),'LaunchExecutable':'Hades.exe','AppCategories':['public','games']}))
            (manifests/'b.item').write_text(json.dumps({'DisplayName':'Discord','AppName':'disc','InstallLocation':str(app),'bIsApplication':True,'AppCategories':['applications']}))
            epic=discover_epic(manifests)
            self.assertEqual([g['name'] for g in epic],['Hades']); self.assertTrue(epic[0]['launch_uri'].startswith('com.epicgames.launcher://apps/Min'))
            gog=discover_gog([('1207658924',{'path':str(game),'exe':str(game/'Hades.exe'),'gameName':'Hades GOG'})])
            self.assertEqual(gog[0]['id'],'gog-1207658924')
            self.assertEqual(len(discover_other([root])),1,'Same install folder is listed once')

class HotkeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]); configure_app(cls.app)

    def test_parse_validate_and_conflicts(self):
        self.assertEqual(hotkeys.parse('Ctrl+Alt+O'),((0x11,0x12),0x4F)); self.assertEqual(hotkeys.parse('F9'),((),0x78))
        self.assertEqual(hotkeys.normalise('alt+ctrl+o'),'Ctrl+Alt+O')
        for bad in ('O','Ctrl+?',''):
            with self.assertRaises(hotkeys.HotkeyError): hotkeys.parse(bad)
        with self.assertRaises(hotkeys.HotkeyError): hotkeys.validate({'overlay':'Ctrl+Alt+R'})

    def test_window_saves_shortcuts_and_updates_every_badge(self):
        with tempfile.TemporaryDirectory() as directory:
            window=MainWindow(Path(directory))
            window.hotkey_edits['overlay'].setKeySequence(QKeySequence('Ctrl+Shift+T')); window.save_hotkeys()
            self.assertEqual(window.hotkeys['overlay'],'Ctrl+Shift+T'); self.assertEqual(window.hotkey_codes['overlay'],((0x10,0x11),0x54))
            self.assertTrue(all(b.text()==window.hotkeys[b.hotkey_action] for b in window.hotkey_badges))
            self.assertEqual(hotkeys.load(Path(directory)/'hotkeys.json')['overlay'],'Ctrl+Shift+T')
            window.hotkey_edits['region'].setKeySequence(QKeySequence('Ctrl+Shift+T')); window.save_hotkeys()
            self.assertIn('sudah dipakai',window.hotkey_status.text()); self.assertEqual(window.hotkeys['region'],'Ctrl+Alt+R')
            window.close()

    def test_back_button_returns_to_previous_page(self):
        with tempfile.TemporaryDirectory() as directory:
            window=MainWindow(Path(directory)); window.show(); self.app.processEvents()
            self.assertFalse(window.back_button.isVisible())
            window.navigate(1); window.navigate(3); self.assertTrue(window.back_button.isVisible())
            window.go_back(); self.assertEqual(window.pages.currentIndex(),1)
            window.go_back(); self.assertEqual(window.pages.currentIndex(),4); self.assertFalse(window.back_button.isVisible())
            window.close()

if __name__=='__main__': unittest.main()
