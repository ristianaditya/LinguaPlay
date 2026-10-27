"""Windows OCR and click-through subtitle overlay; no audio or game injection."""
import asyncio
import ctypes
import time
from threading import Event, Lock
from PIL import ImageGrab
from PySide6.QtCore import Qt, QRect, Signal, QThread
from PySide6.QtGui import QColor, QPainter, QPen, QFont
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from .overlay_settings import OverlayAppearance, place_overlay

def available_languages():
    from winrt.windows.media.ocr import OcrEngine
    import winrt.windows.foundation.collections  # WinRT iterable projections
    return [language.language_tag for language in OcrEngine.available_recognizer_languages]

async def recognize_image(image, language):
    from winrt.windows.globalization import Language
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.graphics.imaging import SoftwareBitmap, BitmapPixelFormat, BitmapAlphaMode
    from winrt.windows.storage.streams import DataWriter
    engine=OcrEngine.try_create_from_language(Language(language))
    if engine is None:
        raise RuntimeError(f'Paket OCR {language} belum terpasang. Tambahkan bahasa melalui Settings Windows.')
    image=image.convert('RGBA')
    if max(image.size)>OcrEngine.max_image_dimension:
        image.thumbnail((OcrEngine.max_image_dimension,OcrEngine.max_image_dimension))
    writer=DataWriter()
    try:
        writer.write_bytes(image.tobytes())
        buffer=writer.detach_buffer()
        bitmap=SoftwareBitmap.create_copy_from_buffer(buffer,BitmapPixelFormat.RGBA8,image.width,image.height,BitmapAlphaMode.IGNORE)
        try:
            result=await engine.recognize_async(bitmap)
            return '\n'.join(line.text for line in result.lines).strip()
        finally:
            bitmap.close()
    finally:
        writer.close()

class RegionSelector(QWidget):
    selected=Signal(object)
    cancelled=Signal()

    def __init__(self,screen):
        super().__init__(None,Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(screen.geometry())
        self.start=None; self.end=None
        self.setCursor(Qt.CursorShape.CrossCursor)

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.fillRect(self.rect(),QColor(12,29,50,145))
        painter.setPen(QColor('white')); painter.setFont(QFont('Segoe UI',16))
        painter.drawText(self.rect().adjusted(32,32,-32,-32),Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
                         'Tarik area subtitle di layar utama. Tekan Esc untuk batal.')
        if self.start and self.end:
            rect=QRect(self.start,self.end).normalized()
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(rect,Qt.GlobalColor.transparent)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor('#82cfff'),3)); painter.drawRect(rect)

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self.start=event.position().toPoint(); self.end=self.start; self.update()

    def mouseMoveEvent(self,event):
        if self.start: self.end=event.position().toPoint(); self.update()

    def mouseReleaseEvent(self,event):
        if self.start and event.button()==Qt.MouseButton.LeftButton:
            rect=QRect(self.start,event.position().toPoint()).normalized().intersected(self.rect())
            if rect.width()<40 or rect.height()<20: return
            rect.translate(self.geometry().topLeft())
            self.hide(); self.selected.emit(rect); self.close()

    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape:
            self.cancelled.emit(); self.close()

class SubtitleOverlay(QWidget):
    def __init__(self,screen,region,appearance=None):
        flags=Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool | Qt.WindowType.WindowTransparentForInput | Qt.WindowType.WindowDoesNotAcceptFocus
        super().__init__(None,flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.label=QLabel('Menunggu subtitle…')
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setWordWrap(True); self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.addWidget(self.label)
        self.bounds=screen.geometry(); self.region=QRect(region)
        self.apply_appearance(appearance or OverlayAppearance())

    def apply_appearance(self,appearance):
        geometry=place_overlay(self.bounds,self.region,appearance)
        color=QColor(appearance.background_color); alpha=round(255*appearance.background_opacity/100)
        self.label.setStyleSheet(f'color: {appearance.text_color}; background: rgba({color.red()}, {color.green()}, {color.blue()}, {alpha}); border-radius: 8px; padding: 16px; font: {appearance.font_size}px "{appearance.font_family}";')
        self.appearance=appearance; self.setGeometry(geometry)

    def showEvent(self,event):
        super().showEvent(event)
        # Exclude our overlay from supported Windows capture paths as extra protection.
        try: ctypes.windll.user32.SetWindowDisplayAffinity(int(self.winId()),0x11)
        except (AttributeError,OSError): pass

class OcrWorker(QThread):
    subtitle=Signal(str)
    status=Signal(str)
    failure=Signal(str)

    def __init__(self,bbox,language,translator,cancel,pause=None,capture_lock=None):
        super().__init__(); self.bbox=bbox; self.language=language
        self.translator=translator; self.cancel=cancel
        self.pause=pause or Event(); self.capture_lock=capture_lock or Lock()

    def run(self):
        try: asyncio.run(self.loop())
        except Exception as exc: self.failure.emit(str(exc))

    async def loop(self):
        previous=''; pending=''; blank_since=None
        while not self.cancel.is_set():
            with self.capture_lock:
                image=None if self.pause.is_set() else ImageGrab.grab(bbox=self.bbox,all_screens=True)
            if image is None:
                await asyncio.sleep(.1); continue
            text=await recognize_image(image,self.language)
            if not text:
                if blank_since is None: blank_since=time.monotonic()
                if time.monotonic()-blank_since>1.2:
                    self.subtitle.emit(''); previous=''; pending=''
            else:
                blank_since=None
                # Wait for two equal reads to avoid translating partially drawn text.
                if text==pending and text!=previous:
                    start=time.monotonic(); self.status.emit('Menerjemahkan subtitle…')
                    translated=self.translator.translate(text)
                    if not self.cancel.is_set():
                        self.subtitle.emit(translated)
                        self.status.emit(f'OCR aktif • proses terakhir {time.monotonic()-start:.1f} detik • Ctrl+Alt+F10 untuk berhenti')
                    previous=text
                pending=text
            for _ in range(4):
                if self.cancel.is_set(): break
                await asyncio.sleep(.1)
