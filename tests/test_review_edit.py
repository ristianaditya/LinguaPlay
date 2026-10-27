import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from linguaplay.ui import MainWindow, configure_app
from linguaplay.translation import Translator
from linguaplay.translation_memory import UserEdits

SRT=(b'1\r\n00:00:01,000 --> 00:00:02,000\r\nHello, {player_name}!\r\n\r\n'
     b'2\r\n00:00:03,000 --> 00:00:04,000\r\nHello friend.\r\n\r\n'
     b'3\r\n00:00:05,000 --> 00:00:06,000\r\nHello friend.\r\n')

class ReviewEditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]); configure_app(cls.app)

    def wait_job(self,window):
        deadline=time.monotonic()+20
        while window.worker and window.worker.isRunning() and time.monotonic()<deadline: self.app.processEvents(); time.sleep(.01)
        self.app.processEvents()

    def window_with_translation(self,root):
        game=root/'game'; game.mkdir(); source=game/'dialogue.en.srt'; source.write_bytes(SRT)
        window=MainWindow(root/'appdata'); errors=[]; window.error=errors.append; window.show()
        window.translator=lambda:Translator(lambda text:text.replace('Hello','Halo'),root/'cache.sqlite','review-test')
        window.folder.setText(str(game)); window.scan(); self.wait_job(window)
        window.translate(); self.wait_job(window); self.assertEqual(errors,[])
        return window,source,errors

    def test_manual_edit_is_validated_remembered_and_installed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); window,source,errors=self.window_with_translation(root)
            self.assertEqual(window.preview.rowCount(),3)
            window.preview.selectRow(0)
            self.assertFalse(window.commit_translation(0,'Halo!'),'Placeholder {player_name} must be kept')
            self.assertTrue(window.review_panel.message.text())
            window.preview.selectRow(1); window.save_review_entry('Hai, kawan.')
            # The same English sentence elsewhere in the file follows the correction.
            self.assertEqual(window.preview.item(2,1).text(),'Hai, kawan.')
            self.assertEqual(window.preview.item(1,2).text(),'Diedit')
            self.assertEqual(UserEdits(root/'appdata'/'user-edits.json','en','id').lookup('Hello friend.'),'Hai, kawan.')
            window.review_filter.setCurrentIndex(1)
            self.assertEqual([r for r in range(3) if not window.preview.isRowHidden(r)],[1,2])
            window.review_filter.setCurrentIndex(0); window.review_search.setText('player')
            self.assertEqual([r for r in range(3) if not window.preview.isRowHidden(r)],[0])
            window.install(); self.wait_job(window); self.assertEqual(errors,[])
            self.assertIn(b'Hai, kawan.',source.read_bytes()); self.assertIn(b'Halo, {player_name}!',source.read_bytes())
            window.close()

    def test_rescan_of_patched_game_uses_originals_and_replaces_old_patch(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); window,source,errors=self.window_with_translation(root)
            window.install(); self.wait_job(window); self.assertIn(b'Halo friend.',source.read_bytes())
            window.scan(); self.wait_job(window)
            self.assertEqual(window.report.originals,1)
            self.assertEqual(window.preview.item(1,0).text(),'Hello friend.','Source must be the original English, not the patch')
            window.translate(); self.wait_job(window)
            window.preview.selectRow(1); window.save_review_entry('Hai, kawan.')
            window.install(); self.wait_job(window); self.assertEqual(errors,[])
            self.assertIn(b'Hai, kawan.',source.read_bytes())
            statuses=sorted(m['status'] for _,m in __import__('linguaplay.patches',fromlist=['list_patches']).list_patches(root/'appdata'/'patches'))
            self.assertEqual(statuses,['installed','restored'])
            window.close()

    def test_edit_survives_retranslation_and_can_revert_to_machine(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); window,source,errors=self.window_with_translation(root)
            window.preview.selectRow(1); window.save_review_entry('Hai, kawan.')
            window.translate(); self.wait_job(window)
            self.assertEqual(window.preview.item(1,1).text(),'Hai, kawan.')
            window.preview.selectRow(1); window.revert_review_entry()
            self.assertEqual(window.preview.item(1,1).text(),'Halo friend.')
            self.assertIsNone(UserEdits(root/'appdata'/'user-edits.json','en','id').lookup('Hello friend.'))
            window.close()

if __name__=='__main__': unittest.main()
