import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from linguaplay.ui import MainWindow, configure_app
from linguaplay.desktop_widgets import ActivityBar, SegmentedToggle, Spinner
from linguaplay.icons import PATHS, icon

class DesktopMotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]); configure_app(cls.app)

    def test_every_icon_renders(self):
        for name in PATHS: self.assertFalse(icon(name).isNull(),name)

    def test_play_toggle_mirrors_combo_and_refuses_disabled_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); exe=root/'game.exe'; exe.touch()
            window=MainWindow(root/'appdata'); window.resize(1280,860); window.show()
            game=window.library.add_executable(exe,'Adventure'); window.select_library_game(game['id']); self.app.processEvents()
            toggle=window.play_toggle; self.assertIsInstance(toggle,SegmentedToggle)
            QTest.mouseClick(toggle,Qt.MouseButton.LeftButton,pos=QPoint(toggle.width()-10,toggle.height()//2))
            self.assertEqual(window.play_mode.currentIndex(),0,'Translated mode is unavailable without a patch')
            window.play_mode.model().item(1).setEnabled(True)
            QTest.mouseClick(toggle,Qt.MouseButton.LeftButton,pos=QPoint(toggle.width()-10,toggle.height()//2))
            self.assertEqual(window.play_mode.currentData(),'translated')
            window.close()

    def test_busy_state_drives_spinner_and_shimmer(self):
        bar=ActivityBar(); spinner=Spinner()
        bar.setRange(0,0); spinner.start(); self.assertTrue(bar.animation.state()==bar.animation.State.Running); self.assertTrue(spinner.isVisible() or not spinner.isHidden())
        bar.setRange(0,1); spinner.stop(); self.assertFalse(bar.animation.state()==bar.animation.State.Running); self.assertTrue(spinner.isHidden())

    def test_overlay_hub_opens_with_panel_and_backdrop_click_returns_to_game(self):
        with tempfile.TemporaryDirectory() as directory:
            window=MainWindow(Path(directory)); window.show()
            window.toggle_overlay_settings(); self.app.processEvents()
            hub=window.overlay_hub; self.assertTrue(hub.isVisible()); self.assertTrue(window.overlay_settings.isVisible())
            QTest.mouseClick(hub,Qt.MouseButton.LeftButton,pos=QPoint(hub.width()//2,hub.height()//2)); self.app.processEvents()
            self.assertFalse(window.overlay_settings.isVisible()); self.assertIsNone(window.overlay_hub)
            window.close()

if __name__=='__main__': unittest.main()
