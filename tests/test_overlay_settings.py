import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import time
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch
from PIL import Image
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication
from linguaplay.overlay_settings import OverlayAppearance, OverlaySettingsPanel, place_overlay, load_appearance, save_appearance
from linguaplay.ocr import SubtitleOverlay, OcrWorker
from linguaplay.ui import MainWindow, configure_app

class FakeScreen:
    def geometry(self): return QRect(0,0,1280,720)

class OverlaySettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]); configure_app(cls.app)

    def test_appearance_applies_live_and_keeps_click_through(self):
        overlay=SubtitleOverlay(FakeScreen(),QRect(200,570,880,130))
        appearance=OverlayAppearance(font_size=36,text_color='#ffdd55',background_opacity=40,width_percent=60,position_y=95)
        overlay.apply_appearance(appearance)
        self.assertEqual(overlay.appearance.font_size,36)
        self.assertIn('#ffdd55',overlay.label.styleSheet())
        self.assertIn('102',overlay.label.styleSheet())
        self.assertFalse(overlay.geometry().intersects(QRect(200,570,880,130)))
        from PySide6.QtCore import Qt
        self.assertTrue(overlay.windowFlags() & Qt.WindowType.WindowTransparentForInput)
        overlay.close()

    def test_safe_position_respects_offset_screen_and_rejects_full_capture(self):
        bounds=QRect(-1280,0,1280,720); region=QRect(-1100,570,880,130)
        placed=place_overlay(bounds,region,OverlayAppearance(position_y=100))
        self.assertTrue(bounds.contains(placed)); self.assertFalse(placed.intersects(region))
        with self.assertRaises(ValueError): place_overlay(bounds,bounds,OverlayAppearance())

    def test_settings_persist_and_corrupt_input_falls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'appearance.json'
            expected=OverlayAppearance(font_size=34,text_color='#ffdd55',background_opacity=15)
            save_appearance(path,expected)
            self.assertEqual(load_appearance(path),expected)
            path.write_text('{"font_size":"broken","text_color":"bad"}')
            self.assertEqual(load_appearance(path),OverlayAppearance())

    def test_panel_controls_update_overlay_and_escape_closes(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        panel=OverlaySettingsPanel(OverlayAppearance()); changed=[]; closed=[]
        panel.changed.connect(changed.append); panel.finished.connect(closed.append)
        panel.show(); panel.font_size.setValue(40); self.app.processEvents()
        self.assertEqual(changed[-1].font_size,40)
        QTest.keyClick(panel,Qt.Key.Key_Escape); self.app.processEvents()
        self.assertFalse(panel.isVisible()); self.assertEqual(len(closed),1)

    def test_frameless_panel_can_be_dragged_and_closed_from_header(self):
        from PySide6.QtCore import Qt,QPoint,QPointF,QEvent
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtTest import QTest
        panel=OverlaySettingsPanel(OverlayAppearance()); panel.move(60,60); panel.show(); self.app.processEvents()
        self.assertTrue(panel.windowFlags() & Qt.WindowType.FramelessWindowHint)
        start=panel.pos()
        QTest.mousePress(panel.drag_handle,Qt.MouseButton.LeftButton,pos=QPoint(20,15))
        local=QPoint(90,65); global_pos=panel.drag_handle.mapToGlobal(local)
        event=QMouseEvent(QEvent.Type.MouseMove,QPointF(local),QPointF(global_pos),Qt.MouseButton.NoButton,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(panel.drag_handle,event)
        QTest.mouseRelease(panel.drag_handle,Qt.MouseButton.LeftButton,pos=local)
        self.assertGreater(panel.x(),start.x()); self.assertGreater(panel.y(),start.y())
        QTest.mouseClick(panel.close_button,Qt.MouseButton.LeftButton); self.app.processEvents()
        self.assertFalse(panel.isVisible())

    def test_keyboard_can_reposition_panel_and_both_tabs_keep_live_controls(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        panel=OverlaySettingsPanel(OverlayAppearance()); panel.move(60,60); panel.show(); self.app.processEvents()
        start=panel.pos(); QTest.keyClick(panel,Qt.Key.Key_Right,Qt.KeyboardModifier.AltModifier); self.app.processEvents()
        self.assertGreater(panel.x(),start.x())
        changed=[]; panel.changed.connect(changed.append)
        panel.tabs.setCurrentIndex(1); panel.position_x.setValue(75)
        self.assertEqual(changed[-1].position_x,75)
        panel.close()

    def test_hotkey_dispatch_and_preview_work_without_ocr(self):
        with tempfile.TemporaryDirectory() as directory:
            window=MainWindow(Path(directory)); window.show()
            window.handle_hotkeys(settings_pressed=True,stop_pressed=False)
            self.app.processEvents()
            self.assertTrue(window.overlay_settings.isVisible())
            window.overlay_settings.move(120,100)
            window.overlay_settings.font_size.setValue(38)
            self.assertEqual(window.appearance.font_size,38)
            window.handle_hotkeys(settings_pressed=True,stop_pressed=False)
            self.assertTrue(window.overlay_settings.isVisible(),'Held key must not immediately toggle closed')
            window.handle_hotkeys(settings_pressed=False,stop_pressed=False)
            window.handle_hotkeys(settings_pressed=True,stop_pressed=False)
            self.app.processEvents()
            self.assertFalse(window.overlay_settings.isVisible())
            self.assertEqual(load_appearance(Path(directory)/'overlay-settings.json').font_size,38)
            window.handle_hotkeys(settings_pressed=False,stop_pressed=False)
            window.handle_hotkeys(settings_pressed=True,stop_pressed=False)
            self.assertEqual(window.overlay_settings.pos().x(),120)
            self.assertEqual(window.overlay_settings.pos().y(),100)
            window.close()

    def test_worker_does_not_capture_while_panel_paused(self):
        pause=Event(); pause.set(); cancel=Event()
        worker=OcrWorker((0,0,500,100),'en-US',None,cancel,pause=pause)
        with patch('linguaplay.ocr.ImageGrab.grab',return_value=Image.new('RGB',(500,100))) as grab:
            worker.start(); deadline=time.monotonic()+.25
            while time.monotonic()<deadline: self.app.processEvents(); time.sleep(.01)
            cancel.set(); worker.wait(2000)
            self.assertEqual(grab.call_count,0)
        self.assertFalse(worker.isRunning())

    def test_active_ocr_pauses_for_settings_then_resumes_after_close(self):
        from linguaplay.translation import Translator
        async def recognized(image,language): return 'Hello Nathan!'
        with tempfile.TemporaryDirectory() as directory:
            window=MainWindow(Path(directory)); window.error=lambda message:self.fail(message)
            window.ocr_translator=Translator(lambda text:text.replace('Hello','Halo'),Path(directory)/'cache.sqlite','resume-fixture')
            with patch('linguaplay.ocr.ImageGrab.grab',return_value=Image.new('RGB',(500,100))) as grab, patch('linguaplay.ocr.recognize_image',recognized):
                try:
                    window.start_ocr(QRect(150,620,500,80)); window.toggle_overlay_settings()
                    self.assertTrue(window.ocr_pause.is_set())
                    count=grab.call_count; deadline=time.monotonic()+.2
                    while time.monotonic()<deadline: self.app.processEvents(); time.sleep(.01)
                    self.assertEqual(grab.call_count,count)
                    window.overlay_settings.accept()
                    deadline=time.monotonic()+3
                    while not window.latest_subtitle and time.monotonic()<deadline:
                        self.app.processEvents(); time.sleep(.01)
                    self.assertFalse(window.ocr_pause.is_set())
                    self.assertEqual(window.latest_subtitle,'Halo Nathan!')
                finally:
                    window.stop_ocr(); window.ocr_worker.wait(3000); self.app.processEvents()
                    window.close(); self.app.processEvents()

if __name__=='__main__': unittest.main()
