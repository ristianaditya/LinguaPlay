import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from linguaplay.ui import MainWindow, configure_app

class DesktopFlowTests(unittest.TestCase):
    def test_library_home_selection_and_removal_keep_game_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); exe=root/'game.exe'; exe.touch()
            window=MainWindow(root/'appdata')
            self.assertEqual(window.pages.currentIndex(),4)
            game=window.library.add_executable(exe,'Adventure')
            window.refresh_library(); self.assertEqual(window.game_grid.count(),1)
            window.select_library_game(game['id'])
            self.assertEqual(window.pages.currentIndex(),5)
            self.assertEqual(window.detail_title.text(),'Adventure')
            self.assertFalse(window.play_mode.model().item(1).isEnabled())
            window.library_search.setText('missing'); self.assertEqual(window.game_grid.count(),0)
            window.remove_library_game(); self.assertTrue(exe.exists())
            self.assertEqual(window.pages.currentIndex(),4); window.close()

    def test_steam_editor_cannot_change_install_location(self):
        from linguaplay.library_ui import GameEditor
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); other=root/'other'; other.mkdir()
            game={'name':'Steam Game','root':str(root),'executable':'','cover':'','steam_id':'42'}
            editor=GameEditor(None,game)
            editor.root.setText(str(other)); editor.validate()
            self.assertIn('Steam',editor.message.text())
            self.assertEqual(editor.result(),0); editor.close()

    def test_local_provider_disables_api_fields_and_can_switch_back(self):
        with tempfile.TemporaryDirectory() as directory:
            window=MainWindow(Path(directory))
            self.assertEqual(window.config().kind,'OPUS-MT lokal')
            self.assertGreaterEqual(window.provider.findText('OPUS-MT lokal'),0)
            window.provider.setCurrentText('OPUS-MT lokal')
            self.assertFalse(window.endpoint.isEnabled())
            self.assertFalse(window.model.isEnabled())
            self.assertFalse(window.key.isEnabled())
            self.assertIn('OPUS',window.profile_provider.text())
            window.save_settings(); window.close()
            restored=MainWindow(Path(directory))
            self.assertEqual(restored.config().kind,'OPUS-MT lokal')
            restored.provider.setCurrentText('OpenAI compatible')
            self.assertTrue(restored.endpoint.isEnabled())
            self.assertTrue(restored.model.isEnabled())
            from PySide6.QtWidgets import QLabel
            self.assertNotIn('offline',restored.findChild(QLabel,'localStatus').text().lower())
            restored.close()

    def test_responsive_pages_stack_sidebars_on_narrow_windows(self):
        from PySide6.QtWidgets import QBoxLayout
        with tempfile.TemporaryDirectory() as directory:
            window=MainWindow(Path(directory)); window.show(); self.app.processEvents()
            window.navigate(3,record=False); window.resize(980,700); self.app.processEvents()
            self.assertEqual(window.settings_columns.direction(),QBoxLayout.Direction.TopToBottom)
            self.assertGreater(window.settings_help_frame.width(),304)
            self.assertEqual(window.rail.width(),184)
            window.navigate(0,record=False); self.app.processEvents()
            self.assertEqual(window.responsive_columns[0].direction(),QBoxLayout.Direction.TopToBottom)
            window.resize(1400,900); self.app.processEvents()
            self.assertEqual(window.settings_columns.direction(),QBoxLayout.Direction.LeftToRight)
            self.assertEqual(window.settings_help_frame.width(),304)
            self.assertEqual(window.rail.width(),224)
            window.close(); self.app.processEvents()

    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        configure_app(cls.app)

    def wait_job(self,window):
        deadline=time.monotonic()+15
        while window.worker and window.worker.isRunning() and time.monotonic()<deadline:
            self.app.processEvents(); time.sleep(.01)
        self.app.processEvents()
        self.assertFalse(window.worker.isRunning(),'Worker did not finish')

    def test_custom_and_regional_language_codes_survive_typing_and_enter(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        with tempfile.TemporaryDirectory() as directory:
            window=MainWindow(Path(directory)); window.show(); self.app.processEvents()
            quick=window.quick_target
            quick.lineEdit().selectAll(); QTest.keyClicks(quick.lineEdit(),'en-US')
            self.assertEqual(quick.current_code(),'en-US')
            self.assertEqual(window.config().target,'en-US')
            quick.setEditText('it'); QTest.keyClick(quick,Qt.Key.Key_Return)
            self.assertEqual(quick.current_code(),'it')
            quick.set_code('en'); quick.set_code('it')
            self.assertEqual(window.config().target,'it')
            window.close(); self.app.processEvents()

    def test_dashboard_language_controls_and_game_preview_stay_in_sync(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); game=root/'My adventure'; game.mkdir()
            (game/'en.json').write_text('{"strings":{"a":"Hello Nathan!"}}')
            window=MainWindow(root/'data'); window.error=lambda message:self.fail(message)
            window.quick_target.setCurrentText('ja')
            self.assertEqual(window.config().target,'ja')
            window.target.setCurrentText('id')
            self.assertEqual(window.quick_target.current_code(),'id')
            window.folder.setText(str(game)); window.scan(); self.wait_job(window)
            self.assertEqual(window.game_title.text(),'My adventure')
            doc=window.report.documents[0]
            window.translations={str(doc.path):{'a':'Halo Nathan!'}}
            window.show_selected(); self.app.processEvents()
            self.assertEqual(window.patch_overlay_preview.current_text,'Halo Nathan!')
            window.close(); self.app.processEvents()

    def test_failed_scan_clears_previous_game_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); game=root/'game'; game.mkdir()
            (game/'en.json').write_text('{"strings":{"a":"Hello"}}')
            window=MainWindow(root/'data'); window.error=lambda message:None
            window.folder.setText(str(game)); window.scan(); self.wait_job(window)
            self.assertTrue(window.translate_button.isEnabled())
            window.folder.setText(str(root/'missing')); window.scan(); self.wait_job(window)
            self.assertIsNone(window.report)
            self.assertEqual(window.files.rowCount(),0)
            self.assertFalse(window.translate_button.isEnabled())
            window.close(); self.app.processEvents()

    def test_scan_translate_preview_install_restore(self):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                text=data['messages'][1]['content'].replace('Hello','Halo')
                body=json.dumps({'choices':[{'message':{'content':text}}]}).encode()
                self.send_response(200); self.end_headers(); self.wfile.write(body)
            def log_message(self,*args): pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory); game=root/'Contoh petualangan'; game.mkdir()
                source=game/'dialogue.en.srt'
                source.write_bytes(b'1\r\n00:00:01,000 --> 00:00:04,000\r\nHello, {player_name}!\r\n')
                original=source.read_bytes()
                window=MainWindow(root/'appdata'); errors=[]; window.error=errors.append
                window.show(); self.app.processEvents()
                window.provider.setCurrentText('OpenAI compatible')
                window.endpoint.setText(f'http://127.0.0.1:{server.server_port}/v1')
                window.folder.setText(str(game)); window.scan(); self.wait_job(window)
                self.assertEqual(window.files.rowCount(),1)
                window.translate(); self.wait_job(window)
                self.assertEqual(errors,[])
                self.assertTrue(window.install_button.isEnabled())
                self.assertEqual(window.preview.item(0,1).text(),'Halo, {player_name}!')
                if os.environ.get('LINGUA_SCREENSHOT'):
                    window.grab().save(os.environ['LINGUA_SCREENSHOT'])
                window.install(); self.wait_job(window)
                self.assertIn(b'Halo',source.read_bytes())
                window.restore(); self.wait_job(window)
                self.assertEqual(errors,[]); self.assertEqual(source.read_bytes(),original)
                window.close(); self.app.processEvents()
        finally:
            server.shutdown(); server.server_close(); thread.join()

if __name__=='__main__': unittest.main()
