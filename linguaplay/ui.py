from dataclasses import asdict
from pathlib import Path
from threading import Event, Lock
import ctypes
import json
import os
import sys
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QUrl, QPoint
from PySide6.QtGui import QFont, QFontDatabase, QDesktopServices, QIcon
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QFileDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QStackedWidget, QFrame, QSplitter, QPlainTextEdit,
    QProgressBar, QListWidget, QListWidgetItem, QFormLayout, QMessageBox)
from .adapters import scan_folder
from .translation import Translator, ProviderConfig
from .patches import prepare_patch, install_patch, restore_patch, list_patches
from .ocr import available_languages, RegionSelector, SubtitleOverlay, OcrWorker
from .overlay_settings import OverlaySettingsPanel, load_appearance, save_appearance

from .desktop_theme import STYLE, apply_palette, apply_window_chrome
from .desktop_layout import DesktopLayout
from .library_ui import LibraryUI

class Worker(QThread):
    result=Signal(object); failure=Signal(str); progress=Signal(str)
    def __init__(self,fn): super().__init__(); self.fn=fn
    def run(self):
        try: self.result.emit(self.fn(self.progress.emit))
        except Exception as exc: self.failure.emit(str(exc))

class MainWindow(LibraryUI,DesktopLayout,QMainWindow):
    def __init__(self,data_dir=None):
        super().__init__()
        self.data=Path(data_dir or Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'LinguaPlay')
        self.data.mkdir(parents=True,exist_ok=True)
        self.storage=self.data/'patches'; self.storage.mkdir(exist_ok=True)
        self.report=None; self.prepared=None; self.translations={}; self.cancel=Event()
        self.worker=None; self.ocr_worker=None; self.overlay=None; self.selector=None
        self.closing=False; self.last_hotkey=False
        self.last_settings_hotkey=False; self.overlay_settings=None; self.settings_preview=None
        self.overlay_panel_position=None
        self.appearance=load_appearance(self.data/'overlay-settings.json'); self.latest_subtitle=''
        self.setWindowTitle('LinguaPlay • Library game'); self.resize(1400,900); self.setMinimumSize(1180,780)
        icon=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))/'assets'/'app.ico'
        if icon.is_file(): self.setWindowIcon(QIcon(str(icon)))
        self.build_shell()
        self.build_patch(); self.build_ocr(); self.build_history(); self.build_settings()
        self.build_library()
        self.bind_dashboard(); self.load_settings(); self.refresh_history(); self.navigate(4)
        self.hotkey_timer=QTimer(self); self.hotkey_timer.timeout.connect(self.check_hotkey); self.hotkey_timer.start(150)

    def config(self):
        config=ProviderConfig(self.provider.currentText(),self.endpoint.text().strip(),self.model.text().strip(),self.key.text().strip(),self.source.currentText().strip(),self.target.currentText().strip())
        if not config.source or not config.target: raise ValueError('Isi bahasa sumber dan tujuan.')
        if config.source==config.target: raise ValueError('Bahasa sumber dan tujuan harus berbeda.')
        if config.kind=='OpenAI compatible' and not config.model: raise ValueError('Isi nama model.')
        return config

    def showEvent(self,event):
        super().showEvent(event); apply_window_chrome(self)

    def load_settings(self):
        try:
            data=json.loads((self.data/'settings.json').read_text(encoding='utf-8'))
            for name in ['endpoint','model']: getattr(self,name).setText(data[name])
            for name in ['source','target']: getattr(self,name).setCurrentText(data[name])
            self.provider.setCurrentText(data['kind'])
        except (OSError,ValueError,KeyError): pass

    def save_settings(self):
        try:
            data=asdict(self.config()); data.pop('api_key')
            (self.data/'settings.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
            self.status.setText('Pengaturan disimpan. Kunci API tetap hanya di memori.')
        except Exception as exc: self.error(str(exc))

    def translator(self):
        config=self.config(); return Translator(config.backend,self.data/'cache.sqlite',config.namespace())

    def error(self,message):
        self.status.setText(message)
        QMessageBox.warning(self,'Proses belum berhasil',message)

    def busy(self,active,cancellable=True):
        self.pages.setEnabled(not active)
        self.progress.setRange(0,0 if active else 1)
        self.cancel_button.setVisible(active and cancellable)

    def run_job(self,fn,done,cancellable=True):
        if self.worker and self.worker.isRunning(): return
        self.cancel=Event(); self.busy(True,cancellable)
        self.worker=Worker(fn); self.worker.progress.connect(self.status.setText)
        self.worker.result.connect(done); self.worker.failure.connect(self.error)
        self.worker.finished.connect(lambda:self.job_finished())
        self.worker.start()

    def job_finished(self):
        self.busy(False); self.refresh_history()
        self.refresh_library()
        if self.closing: self.close()

    def cancel_job(self):
        self.cancel.set(); self.status.setText('Membatalkan setelah operasi saat ini selesai…')

    def choose_folder(self):
        path=QFileDialog.getExistingDirectory(self,'Pilih folder game')
        if path: self.folder.setText(path); self.scan()

    def open_demo(self):
        base=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))/'examples'
        # Copy samples to a writable sandbox, never patch bundled installation assets.
        import shutil
        target=self.data/'contoh-game'; target.mkdir(exist_ok=True)
        for path in base.glob('*'):
            if path.is_file() and not (target/path.name).exists(): shutil.copy2(path,target/path.name)
        self.folder.setText(str(target)); self.scan()

    def scan(self):
        if not self.folder.text(): self.status.setText('Pilih folder terlebih dahulu.'); return
        self.report=None; self.prepared=None; self.translations={}
        self.files.setRowCount(0); self.preview.setRowCount(0)
        self.game_title.setText(Path(self.folder.text()).name)
        self.game_caption.setText('Memindai file subtitle…'); self.update_patch_overlay()
        self.install_button.setEnabled(False); self.translate_button.setEnabled(False); self.diagnostic_button.setEnabled(False)
        self.summary.setText('Memindai folder pilihan…')
        self.status.setText('Memindai folder…')
        folder=self.folder.text()
        self.run_job(lambda progress:scan_folder(folder,self.cancel,progress),self.scanned)

    def scanned(self,report):
        self.report=report; self.files.setRowCount(len(report.documents)); self.preview.setRowCount(0)
        self.game_title.setText(report.root.name[:54]+('…' if len(report.root.name)>54 else ''))
        self.game_title.setToolTip(str(report.root)); self.folder.setToolTip(str(report.root))
        self.game_caption.setText('Tinjau terjemahan, lalu pasang ke folder game.')
        for row,doc in enumerate(report.documents):
            item=QTableWidgetItem(f'{doc.path.relative_to(report.root)}  [{doc.format}]')
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable); item.setCheckState(Qt.CheckState.Checked)
            self.files.setItem(row,0,item); self.files.setItem(row,1,QTableWidgetItem(str(len(doc.entries))))
        self.translate_button.setEnabled(bool(report.documents)); self.diagnostic_button.setEnabled(True)
        total=sum(len(d.entries) for d in report.documents)
        self.summary.setText(f'{len(report.documents)} file • {total} dialog')
        self.patch_hint.setText('Periksa pilihan file dan bahasa sumber sebelum menerjemahkan.')
        self.status.setText('Pemindaian selesai.'+(' Batas 50.000 file tercapai; pilih subfolder lebih spesifik.' if report.truncated else ''))
        if report.documents: self.files.selectRow(0)
        else: self.patch_hint.setText('Tidak ada format didukung. Ekspor diagnostik atau gunakan Overlay OCR.')

    def show_selected(self):
        row=self.files.currentRow()
        if not self.report or row<0 or row>=len(self.report.documents): return
        doc=self.report.documents[row]; mapping=self.translations.get(str(doc.path),{})
        self.preview.setRowCount(min(len(doc.entries),500))
        for i,entry in enumerate(doc.entries[:500]):
            self.preview.setItem(i,0,QTableWidgetItem(entry.text)); self.preview.setItem(i,1,QTableWidgetItem(mapping.get(entry.id,'Belum diterjemahkan')))
        self.preview.resizeRowsToContents()
        if doc.entries: self.preview.selectRow(0)
        self.update_patch_overlay()

    def translate(self):
        if not self.report: return
        try: translator=self.translator()
        except Exception as exc: self.error(str(exc)); return
        selected=[doc for i,doc in enumerate(self.report.documents) if self.files.item(i,0).checkState()==Qt.CheckState.Checked]
        if not selected: self.status.setText('Centang setidaknya satu file.'); return
        self.prepared=None; self.install_button.setEnabled(False)
        root=self.report.root
        def work(progress):
            result=[]; total=sum(len(d.entries) for d in selected); count=0
            for doc in selected:
                mapping={}
                for entry in doc.entries:
                    if self.cancel.is_set(): raise InterruptedError('Terjemahan dibatalkan; file game belum diubah.')
                    count+=1; progress(f'Menerjemahkan {count}/{total}: {doc.path.name}')
                    mapping[entry.id]=translator.translate(entry.text)
                result.append((doc,mapping))
            if self.cancel.is_set(): raise InterruptedError('Terjemahan dibatalkan.')
            return prepare_patch(root,result,self.storage),result
        def done(result):
            self.prepared,pairs=result; self.translations={str(doc.path):mapping for doc,mapping in pairs}
            self.show_selected(); self.install_button.setEnabled(True)
            self.patch_hint.setText('Patch siap. Tinjau hasil dan tutup game, lalu pasang.')
            self.status.setText('Terjemahan siap ditinjau; file game belum diubah.')
        self.run_job(work,done)

    def install(self):
        if not self.prepared: return
        path=self.prepared
        process_root=self.process_root_for_patch(path)
        def done(_):
            self.install_button.setEnabled(False); self.prepared=None
            self.status.setText('Patch terpasang. Gunakan Cadangan untuk memulihkan file asli.')
            self.patch_hint.setText('Pilih bahasa sumber yang diganti dalam pengaturan game.')
        self.run_job(lambda progress:install_patch(path,process_root),done,False)

    def export_diagnostic(self):
        if not self.report: return
        path,_=QFileDialog.getSaveFileName(self,'Simpan diagnostik','diagnostik-linguaplay.json','JSON (*.json)')
        if path:
            try: Path(path).write_text(json.dumps(self.report.diagnostic(),ensure_ascii=False,indent=2),encoding='utf-8'); self.status.setText('Diagnostik disimpan lokal; tidak diunggah.')
            except OSError as exc: self.error(str(exc))

    def refresh_history(self):
        self.history.clear()
        states={'prepared':'Siap pasang','installed':'Terpasang','restored':'Dipulihkan','installing':'Perlu pemulihan','restoring':'Pemulihan terhenti','recovery_required':'Perlu pemulihan'}
        for folder,manifest in list_patches(self.storage):
            item=QListWidgetItem(f"{Path(manifest.get('root','')).name} — {states.get(manifest.get('status'),manifest.get('status'))}\n{manifest.get('created','')[:19].replace('T',' ')} UTC • {len(manifest.get('files',[]))} file")
            item.setData(Qt.ItemDataRole.UserRole,str(folder)); self.history.addItem(item)
        if self.history.count(): self.history.setCurrentRow(0)

    def selected_patch(self):
        item=self.history.currentItem(); return Path(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def restore(self):
        folder=self.selected_patch()
        if folder:
            process_root=self.process_root_for_patch(folder)
            self.run_job(lambda progress:restore_patch(folder,process_root),lambda _:self.status.setText('File asli berhasil dipulihkan.'),False)

    def open_patch_folder(self):
        folder=self.selected_patch()
        if folder: QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def test_connection(self):
        try: translator=self.translator()
        except Exception as exc: self.error(str(exc)); return
        self.connection_status.setText('Menguji layanan…')
        self.run_job(lambda progress:translator.translate('Stay here, {player_name}!'),lambda text:self.connection_status.setText('Koneksi berhasil: '+text))

    def select_region(self):
        if self.ocr_worker and self.ocr_worker.isRunning(): return
        if self.overlay_settings and self.overlay_settings.isVisible(): self.overlay_settings.close()
        if not self.ocr_language.currentText(): self.error('Tidak ada bahasa Windows OCR. Pasang paket OCR melalui Settings Windows.'); return
        try: self.ocr_translator=self.translator()
        except Exception as exc: self.error(str(exc)); return
        self.hide(); self.selector=RegionSelector(QApplication.primaryScreen())
        self.selector.cancelled.connect(self.show); self.selector.selected.connect(self.start_ocr); self.selector.show()

    def start_ocr(self,region):
        screen=QApplication.primaryScreen(); ratio=screen.devicePixelRatio()
        bbox=(round(region.left()*ratio),round(region.top()*ratio),round((region.right()+1)*ratio),round((region.bottom()+1)*ratio))
        try: self.overlay=SubtitleOverlay(screen,region,self.appearance)
        except ValueError as exc: self.show(); self.error(str(exc)); return
        self.ocr_cancel=Event(); self.ocr_pause=Event(); self.capture_lock=Lock(); self.latest_subtitle=''
        self.ocr_worker=OcrWorker(bbox,self.ocr_language.currentText(),self.ocr_translator,self.ocr_cancel,self.ocr_pause,self.capture_lock)
        self.ocr_worker.subtitle.connect(self.update_subtitle); self.ocr_worker.status.connect(self.ocr_status.setText)
        self.ocr_worker.failure.connect(self.ocr_failed); self.ocr_worker.finished.connect(self.ocr_finished)
        self.ocr_start.setEnabled(False); self.ocr_stop.setEnabled(True)
        self.show(); self.showMinimized(); self.overlay.show(); self.ocr_worker.start()
        self.ocr_status.setText('OCR aktif • Ctrl+Alt+F10 untuk berhenti')

    def update_subtitle(self,text):
        self.latest_subtitle=text
        self.ocr_last.setPlainText(text)
        self.ocr_overlay_preview.set_text(text or 'Subtitle terjemahan\nakan muncul di sini.')
        if self.overlay:
            editing=bool(self.overlay_settings and self.overlay_settings.isVisible())
            self.overlay.label.setText(text or ('Contoh subtitle terjemahan.\nTampilan berubah langsung saat Anda mengaturnya.' if editing else ''))
            self.overlay.setVisible(bool(text) or editing)

    def toggle_overlay_settings(self):
        if self.selector and self.selector.isVisible(): return
        if self.overlay_settings and self.overlay_settings.isVisible():
            self.overlay_settings.close(); return
        if self.ocr_worker and self.ocr_worker.isRunning():
            self.ocr_pause.set()
            # Complete any capture already in progress before showing the panel.
            with self.capture_lock: pass
        target=self.overlay
        if target is None:
            from PySide6.QtCore import QRect
            self.settings_preview=SubtitleOverlay(QApplication.primaryScreen(),QRect(),self.appearance)
            target=self.settings_preview
        target.label.setText(self.latest_subtitle or 'Contoh subtitle terjemahan.\nTampilan berubah langsung saat Anda mengaturnya.')
        target.show()
        self.overlay_settings=OverlaySettingsPanel(self.appearance,bool(self.ocr_worker and self.ocr_worker.isRunning()))
        self.overlay_settings.changed.connect(self.apply_overlay_appearance)
        self.overlay_settings.finished.connect(self.overlay_settings_closed)
        self.overlay_settings.adjustSize()
        bounds=QApplication.primaryScreen().availableGeometry()
        self.overlay_settings.move_within_screen(self.overlay_panel_position or QPoint(bounds.left()+32,bounds.top()+80))
        self.overlay_settings.show(); self.overlay_settings.raise_(); self.overlay_settings.activateWindow()

    def apply_overlay_appearance(self,appearance):
        target=self.overlay or self.settings_preview
        try:
            if target: target.apply_appearance(appearance)
            save_appearance(self.data/'overlay-settings.json',appearance)
            self.appearance=appearance
            self.patch_overlay_preview.apply_appearance(appearance)
            self.ocr_overlay_preview.apply_appearance(appearance)
            if self.overlay_settings:
                self.overlay_settings.notice.setText('Tersimpan. Posisi disesuaikan otomatis jika menutupi area OCR.')
        except (ValueError,OSError) as exc:
            if self.overlay_settings: self.overlay_settings.notice.setText(str(exc))

    def overlay_settings_closed(self,*args):
        if self.overlay_settings: self.overlay_panel_position=self.overlay_settings.pos()
        if self.settings_preview:
            self.settings_preview.close(); self.settings_preview=None
        if self.overlay:
            self.overlay.label.setText(self.latest_subtitle); self.overlay.setVisible(bool(self.latest_subtitle))
        worker=self.ocr_worker
        def resume():
            if worker is self.ocr_worker and worker and worker.isRunning() and not (self.overlay_settings and self.overlay_settings.isVisible()):
                self.ocr_pause.clear()
        # Give the compositor a frame to remove the panel before capture resumes.
        QTimer.singleShot(180,resume)

    def stop_ocr(self):
        if self.overlay_settings and self.overlay_settings.isVisible(): self.overlay_settings.close()
        if self.ocr_worker and self.ocr_worker.isRunning():
            self.ocr_cancel.set(); self.ocr_status.setText('Menghentikan OCR setelah permintaan saat ini…')
            self.ocr_stop.setEnabled(False)
        if self.overlay: self.overlay.hide()

    def ocr_failed(self,message):
        self.showNormal(); self.ocr_status.setText(message); self.error(message)

    def ocr_finished(self):
        if self.overlay_settings and self.overlay_settings.isVisible(): self.overlay_settings.close()
        if self.overlay: self.overlay.close(); self.overlay=None
        self.ocr_start.setEnabled(True); self.ocr_stop.setEnabled(False)
        self.ocr_status.setText('OCR berhenti.'); self.showNormal()
        if self.closing: self.close()

    def check_hotkey(self):
        try:
            user=ctypes.windll.user32
            modifiers=all(user.GetAsyncKeyState(key)&0x8000 for key in (0x11,0x12))
            self.handle_hotkeys(bool(modifiers and user.GetAsyncKeyState(0x4F)&0x8000),bool(modifiers and user.GetAsyncKeyState(0x79)&0x8000))
        except AttributeError: pass

    def handle_hotkeys(self,settings_pressed,stop_pressed):
        if stop_pressed and not self.last_hotkey and self.ocr_worker and self.ocr_worker.isRunning():
            self.stop_ocr(); self.showNormal()
        elif settings_pressed and not self.last_settings_hotkey:
            self.toggle_overlay_settings()
        self.last_hotkey=stop_pressed; self.last_settings_hotkey=settings_pressed

    def closeEvent(self,event):
        if self.overlay_settings and self.overlay_settings.isVisible(): self.overlay_settings.close()
        if (self.worker and self.worker.isRunning()) or (self.ocr_worker and self.ocr_worker.isRunning()):
            self.closing=True; self.cancel.set(); self.stop_ocr(); self.status.setText('Menunggu operasi selesai sebelum menutup…'); event.ignore(); return
        if self.overlay: self.overlay.close()
        event.accept()

def configure_app(app):
    # Offscreen Qt has no system font discovery; explicitly load installed fonts.
    if 'Segoe UI' not in QFontDatabase.families():
        font_dir=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
        for filename in ('segoeui.ttf','segoeuib.ttf','segoeuii.ttf'):
            if (font_dir/filename).is_file(): QFontDatabase.addApplicationFont(str(font_dir/filename))
    app.setStyle('Fusion'); app.setFont(QFont('Segoe UI',10)); apply_palette(app); app.setStyleSheet(STYLE)

def main():
    app=QApplication(sys.argv); configure_app(app)
    window=MainWindow(); window.show()
    return app.exec()
