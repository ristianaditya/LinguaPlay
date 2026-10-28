from dataclasses import asdict
from pathlib import Path
from threading import Event, Lock
import ctypes
import json
import os
import sys
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QUrl, QPoint, QRect
from PySide6.QtGui import QFont, QFontDatabase, QDesktopServices, QIcon, QColor, QKeySequence
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QFileDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QStackedWidget, QFrame, QSplitter, QPlainTextEdit,
    QProgressBar, QListWidget, QListWidgetItem, QFormLayout, QMessageBox, QKeySequenceEdit,QDialog)
from .adapters import scan_folder
from .translation import Translator, ProviderConfig, TranslationError, TOKENS, validate_tokens
from .translation_memory import UserEdits
from . import hotkeys
from .patches import prepare_patch, install_patch, restore_patch, list_patches, atomic_write, discard_prepared, use_original_sources, supersede_installed
from .ocr import available_languages, RegionSelector, SubtitleOverlay, OcrWorker
from .overlay_settings import OverlaySettingsPanel, OverlayHub, load_appearance, save_appearance

from .desktop_theme import STYLE, apply_palette, apply_window_chrome
from .desktop_layout import DesktopLayout
from .library_ui import LibraryUI
from .desktop_widgets import PatchReviewDialog

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
        # machine: model output per file (for "revert"); patch_dirty: edits not yet staged into a patch.
        self.machine={}; self.patch_dirty=False; self.review_loading=False; self._edits=None
        self.worker=None; self.ocr_worker=None; self.overlay=None; self.selector=None
        self.closing=False; self.last_hotkey=False; self.last_region_hotkey=False
        self.last_settings_hotkey=False; self.overlay_settings=None; self.settings_preview=None
        self.overlay_panel_position=None; self.overlay_hub=None; self.ocr_region=self.load_ocr_region()
        self.appearance=load_appearance(self.data/'overlay-settings.json'); self.latest_subtitle=''
        self.hotkeys=hotkeys.load(self.data/'hotkeys.json'); self.hotkey_badges=[]; self.compile_hotkeys()
        try: self.ui_prefs=json.loads((self.data/'ui-settings.json').read_text(encoding='utf-8'))
        except (OSError,ValueError): self.ui_prefs={}
        if not isinstance(self.ui_prefs,dict): self.ui_prefs={}
        self.setWindowTitle('LinguaPlay • Library game'); self.resize(1400,900); self.setMinimumSize(920,680)
        icon=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))/'assets'/'app.ico'
        if icon.is_file(): self.setWindowIcon(QIcon(str(icon)))
        self.build_shell()
        self.build_patch(); self.build_ocr(); self.build_history(); self.build_settings()
        self.build_library(); self.backdrop.set_animated(self.ui_prefs.get('animated_background',True))
        self._load_ocr_default_language(); self.refresh_ocr_profiles()
        self.ocr_game_profile.currentIndexChanged.connect(self.load_selected_ocr_profile)
        self.ocr_language.currentTextChanged.connect(self.save_selected_ocr_language)
        self.bind_dashboard(); self.load_settings(); self.refresh_history(); self.navigate(4,record=False)
        self.hotkey_timer=QTimer(self); self.hotkey_timer.timeout.connect(self.check_hotkey); self.hotkey_timer.start(150)

    def config(self):
        config=ProviderConfig(self.provider.currentText(),self.endpoint.text().strip(),self.model.text().strip(),self.key.text().strip(),self.source.currentText().strip(),self.target.currentText().strip())
        if not config.source or not config.target: raise ValueError('Isi bahasa sumber dan tujuan.')
        if config.source==config.target: raise ValueError('Bahasa sumber dan tujuan harus berbeda.')
        if config.kind=='OpenAI compatible' and not config.model: raise ValueError('Isi nama model.')
        return config

    def showEvent(self,event):
        super().showEvent(event); apply_window_chrome(self)
        QTimer.singleShot(0,lambda:self.move_nav_indicator(animated=False))

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
        if active: self.spinner.start()
        else: self.spinner.stop()
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

    def scan(self):
        if not self.folder.text(): self.status.setText('Pilih folder terlebih dahulu.'); return
        self.report=None; self.prepared=None; self.translations={}; self.machine={}; self.patch_dirty=False
        self.files.setRowCount(0); self.preview.setRowCount(0); self.review_panel.set_entry(None); self.review_count.hide()
        self.game_title.setText(Path(self.folder.text()).name)
        self.game_caption.setText('Memindai file subtitle…'); self.update_patch_overlay()
        self.install_button.setEnabled(False); self.translate_button.setEnabled(False); self.diagnostic_button.setEnabled(False)
        self.summary.setText('Memindai folder pilihan…')
        self.status.setText('Memindai folder…')
        folder=self.folder.text()
        def work(progress):
            report=scan_folder(folder,self.cancel,progress)
            progress('Membaca teks asli dari cadangan patch yang terpasang…')
            report.originals=use_original_sources(report,self.storage); return report
        self.run_job(work,self.scanned)

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
        engine=report.engine or {}
        if engine.get('anticheat'):
            # Anti-cheat protected: never stage patches for these games.
            self.translate_button.setEnabled(False); self.patch_hint.setText(engine['note']); self.summary.setText('Patch dinonaktifkan (anti-cheat)')
            self.status.setText('Pemindaian selesai. '+engine['note']); return
        if getattr(report,'originals',0):
            self.patch_hint.setText(f'{report.originals} file sedang memakai patch LinguaPlay; teks asli dibaca dari cadangan. Patch lama otomatis diganti saat Anda memasang yang baru.')
        if report.documents: self.files.selectRow(0)
        else:
            prefix=f"Mesin: {engine['engine_name']}. " if engine.get('engine_name') else ''
            self.patch_hint.setText(prefix+(engine.get('note') or 'Tidak ada format didukung. Ekspor diagnostik atau gunakan Overlay OCR.'))

    # ---- Review & manual editing -------------------------------------------------------
    def user_edits(self):
        pair=(self.source.currentText().strip(),self.target.currentText().strip())
        if self._edits is None or self._edits_pair!=pair:
            self._edits=UserEdits(self.data/'user-edits.json',*pair); self._edits_pair=pair
        return self._edits

    def review_doc(self):
        row=self.files.currentRow()
        if not self.report or row<0 or row>=len(self.report.documents): return None
        return self.report.documents[row]

    def review_state(self,doc,entry):
        value=self.translations.get(str(doc.path),{}).get(entry.id)
        if value is None: return 'none'
        machine=self.machine.get(str(doc.path),{}).get(entry.id)
        return 'edited' if value!=machine and self.user_edits().lookup(entry.text)==value else 'machine'

    def fill_review_row(self,row,doc,entry):
        value=self.translations.get(str(doc.path),{}).get(entry.id); state=self.review_state(doc,entry)
        self.review_loading=True
        try:
            original=QTableWidgetItem(entry.text); original.setFlags(original.flags() & ~Qt.ItemFlag.ItemIsEditable)
            original.setData(Qt.ItemDataRole.UserRole,row); original.setToolTip(entry.text)
            translated=QTableWidgetItem(value if value is not None else 'Belum diterjemahkan'); translated.setToolTip('Klik dua kali untuk mengedit')
            if value is None: translated.setForeground(QColor('#7d8681'))
            status=QTableWidgetItem({'edited':'Diedit','machine':'Mesin','none':'—'}[state]); status.setFlags(status.flags() & ~Qt.ItemFlag.ItemIsEditable)
            status.setForeground(QColor('#d6fb51' if state=='edited' else '#8a928d')); status.setData(Qt.ItemDataRole.UserRole,state)
            self.preview.setItem(row,0,original); self.preview.setItem(row,1,translated); self.preview.setItem(row,2,status)
        finally: self.review_loading=False

    def show_selected(self):
        doc=self.review_doc()
        if doc is None: return
        self.preview.setUpdatesEnabled(False)
        try:
            self.preview.setRowCount(len(doc.entries))
            for i,entry in enumerate(doc.entries): self.fill_review_row(i,doc,entry)
        finally: self.preview.setUpdatesEnabled(True)
        self.apply_review_filter()
        first=next((i for i in range(self.preview.rowCount()) if not self.preview.isRowHidden(i)),-1)
        if first>=0: self.preview.selectRow(first)
        else: self.review_panel.set_entry(None)
        self.update_patch_overlay()

    def apply_review_filter(self,*args):
        doc=self.review_doc()
        if doc is None: return
        query=self.review_search.text().strip().casefold(); mode=self.review_filter.currentIndex(); visible=edited=0
        wanted={1:'edited',2:'machine',3:'none'}.get(mode)
        for row in range(self.preview.rowCount()):
            texts=[self.preview.item(row,c).text().casefold() if self.preview.item(row,c) else '' for c in (0,1)]
            state=self.preview.item(row,2).data(Qt.ItemDataRole.UserRole) if self.preview.item(row,2) else 'none'
            edited+=state=='edited'
            hide=(query and not any(query in t for t in texts)) or (wanted is not None and state!=wanted)
            self.preview.setRowHidden(row,bool(hide)); visible+=not hide
        self.review_count.setText(f'{visible} baris  •  {edited} diedit'); self.review_count.show()

    def load_review_entry(self):
        doc=self.review_doc(); row=self.preview.currentRow()
        if doc is None or row<0 or row>=len(doc.entries): self.review_panel.set_entry(None); return
        entry=doc.entries[row]; key=str(doc.path)
        value=self.translations.get(key,{}).get(entry.id,''); machine=self.machine.get(key,{}).get(entry.id)
        tokens=[t for t in TOKENS.findall(entry.text) if t.strip() and t not in ('\n','\r\n')]
        self.review_panel.set_entry(entry.text,value,self.review_state(doc,entry)=='edited',machine,f'{row+1} / {len(doc.entries)}',tokens)

    def commit_translation(self,row,text):
        """Validate and store a manual translation; it is remembered per English sentence."""
        doc=self.review_doc()
        if doc is None or row<0 or row>=len(doc.entries): return False
        entry=doc.entries[row]; text=text.replace('\r\n','\n').strip()
        try:
            if not text: raise ValueError('Terjemahan tidak boleh kosong.')
            validate_tokens(entry.text,text)
            if hasattr(doc,'check_translation'): doc.check_translation(entry.id,text)
        except ValueError as exc:
            self.review_panel.show_message(str(exc),True); return False
        edits=self.user_edits(); machine=self.machine.get(str(doc.path),{}).get(entry.id)
        if machine is not None and text==machine: edits.remove(entry.text)
        else: edits.store(entry.text,text)
        # The same English sentence elsewhere in this file gets the same correction.
        mapping=self.translations.setdefault(str(doc.path),{})
        for index,other in enumerate(doc.entries):
            if other.text==entry.text:
                mapping[other.id]=text; self.fill_review_row(index,doc,other)
        self.patch_dirty=True; self.install_button.setEnabled(True)
        self.patch_hint.setText('Editan tersimpan. Tekan Pasang patch untuk menerapkannya ke game.')
        self.apply_review_filter(); return True

    def review_cell_changed(self,item):
        if self.review_loading or item.column()!=1: return
        row=item.row(); doc=self.review_doc()
        if not self.commit_translation(row,item.text()) and doc is not None and row<len(doc.entries):
            self.fill_review_row(row,doc,doc.entries[row])
        self.load_review_entry()

    def save_review_entry(self,text):
        row=self.preview.currentRow()
        if self.commit_translation(row,text):
            self.step_review(1); self.review_panel.show_message('Tersimpan ✓  Lanjut ke baris berikutnya.')

    def revert_review_entry(self):
        doc=self.review_doc(); row=self.preview.currentRow()
        if doc is None or row<0: return
        machine=self.machine.get(str(doc.path),{}).get(doc.entries[row].id)
        if machine is not None and self.commit_translation(row,machine):
            self.load_review_entry(); self.review_panel.show_message('Dikembalikan ke terjemahan mesin.')

    def step_review(self,delta):
        row=self.preview.currentRow(); count=self.preview.rowCount(); target=row+delta
        while 0<=target<count and self.preview.isRowHidden(target): target+=delta
        if 0<=target<count:
            self.preview.selectRow(target); self.preview.scrollToItem(self.preview.item(target,0))

    def translate(self):
        if not self.report: return
        try: translator=self.translator()
        except Exception as exc: self.error(str(exc)); return
        selected=[doc for i,doc in enumerate(self.report.documents) if self.files.item(i,0).checkState()==Qt.CheckState.Checked]
        if not selected: self.status.setText('Centang setidaknya satu file.'); return
        self.prepared=None; self.install_button.setEnabled(False)
        root=self.report.root; edits=self.user_edits()
        def work(progress):
            result=[]; machines={}; total=sum(len(d.entries) for d in selected); count=0; skipped=0; reused=0
            for doc in selected:
                mapping={}; machine={}
                for entry in doc.entries:
                    if self.cancel.is_set(): raise InterruptedError('Terjemahan dibatalkan; file game belum diubah.')
                    count+=1; progress(f'Menerjemahkan {count}/{total}: {doc.path.name}')
                    # One bad line must not discard thousands of good ones; it stays in the original language.
                    try: machine[entry.id]=translator.translate(entry.text)
                    except TranslationError: skipped+=1
                    edited=edits.lookup(entry.text)
                    if edited is not None:
                        try:
                            validate_tokens(entry.text,edited)
                            if hasattr(doc,'check_translation'): doc.check_translation(entry.id,edited)
                            mapping[entry.id]=edited; reused+=1; continue
                        except ValueError: pass
                    if entry.id in machine: mapping[entry.id]=machine[entry.id]
                machines[str(doc.path)]=machine
                if mapping: result.append((doc,mapping))
            if self.cancel.is_set(): raise InterruptedError('Terjemahan dibatalkan.')
            if not result: raise TranslationError('Tidak ada dialog yang berhasil diterjemahkan.')
            return prepare_patch(root,result,self.storage),result,skipped,machines,reused
        def done(result):
            self.prepared,pairs,skipped,self.machine,reused=result; self.translations={str(doc.path):mapping for doc,mapping in pairs}
            self.patch_dirty=False; self.show_selected(); self.install_button.setEnabled(True)
            self.patch_hint.setText('Patch siap. Tinjau dan edit hasilnya bila perlu, tutup game, lalu pasang.')
            note=(f' {skipped} dialog gagal diterjemahkan dan tetap memakai teks asli.' if skipped else '')+(f' {reused} editan Anda dipakai.' if reused else '')
            self.status.setText('Terjemahan siap ditinjau; file game belum diubah.'+note)
        self.run_job(work,done)

    def install(self):
        if not self.report or not (self.prepared or self.translations): return
        review_files=[]; untouched=0
        for doc in self.report.documents:
            mapping=self.translations.get(str(doc.path))
            if not mapping: continue
            changed=sum(1 for entry in doc.entries if mapping.get(entry.id,entry.text)!=entry.text)
            review_files.append((str(doc.path.relative_to(self.report.root)),changed,len(doc.entries)))
            untouched+=max(0,len(doc.entries)-len(mapping))
        warnings=[
            'Tutup game sebelum memasang. Pemasangan ditolak jika proses game masih berjalan.',
            'Jika file berubah sejak dipindai, LinguaPlay membatalkan pemasangan dan meminta pemindaian ulang.',
            'File asli dicadangkan dan dapat dipulihkan dari halaman Cadangan.'
        ]
        if untouched: warnings.append(f'{untouched} baris tidak memiliki terjemahan dan tetap memakai teks asli.')
        review=PatchReviewDialog(review_files,warnings,self)
        if review.exec()!=QDialog.DialogCode.Accepted:
            self.status.setText('Pemasangan dibatalkan. File game belum diubah.')
            return
        stale=self.prepared if self.patch_dirty else None
        pairs=[(doc,dict(self.translations[str(doc.path)])) for doc in self.report.documents if self.translations.get(str(doc.path))]
        root=self.report.root
        def work(progress):
            path=self.prepared
            if self.patch_dirty or not path:
                # Re-stage with the user's edits; the previous never-installed staging is discarded.
                progress('Menyusun ulang patch dengan editan Anda…'); path=prepare_patch(root,pairs,self.storage)
                discard_prepared(stale)
            process_root=self.process_root_for_patch(path)
            if supersede_installed(self.storage,path,process_root): progress('Patch lama dipulihkan; memasang patch baru…')
            progress('Memasang patch…'); install_patch(path,process_root); return path
        def done(_):
            self.install_button.setEnabled(False); self.prepared=None; self.patch_dirty=False
            self.status.setText('Patch terpasang. Gunakan Cadangan untuk memulihkan file asli.')
            self.patch_hint.setText('Pilih bahasa sumber yang diganti dalam pengaturan game.')
        self.run_job(work,done,False)

    def run_deep_analysis(self,root,name=None):
        """Locate the game's English text like a manual investigation would, then show what can be done."""
        from .text_finder import analyze
        from .engines import identify_engine
        from .analysis_ui import AnalysisDialog
        def work(progress):
            progress('Analisis mendalam: memeriksa file yang bisa dipatch…'); report=scan_folder(root,self.cancel,progress)
            supported={str(d.path.relative_to(report.root)):d for d in report.documents}
            return analyze(root,progress,self.cancel,supported),report.engine or identify_engine(root)
        def done(result):
            findings,engine=result; self.status.setText(f'Analisis selesai: {len(findings)} lokasi teks ditemukan.')
            AnalysisDialog(self,name or Path(root).name,findings,engine).exec()
        self.run_job(work,done)

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
        self.hide(); self.selector=RegionSelector(QApplication.primaryScreen(),self.ocr_region)
        self.selector.cancelled.connect(self.show); self.selector.selected.connect(self.start_ocr)
        self.selector.show(); self.selector.activateWindow(); self.selector.setFocus()

    @staticmethod
    def region_bbox(screen,region):
        ratio=screen.devicePixelRatio()
        return (round(region.left()*ratio),round(region.top()*ratio),round((region.right()+1)*ratio),round((region.bottom()+1)*ratio))

    def load_ocr_region(self):
        try:
            value=json.loads((self.data/'ocr-region.json').read_text(encoding='utf-8'))
            if isinstance(value,list) and len(value)==4 and all(type(v) is int for v in value) and value[2]>=40 and value[3]>=20:
                return QRect(*value)
        except (OSError,ValueError): pass
        return None

    def _load_ocr_default_language(self):
        self.ocr_default_language=self.ocr_language.currentText()
        try:
            value=json.loads((self.data/'ocr-language.json').read_text(encoding='utf-8'))
            if isinstance(value,str) and value in [self.ocr_language.itemText(i) for i in range(self.ocr_language.count())]:
                self.ocr_default_language=value
        except (OSError,ValueError): pass
        if self.ocr_default_language: self.ocr_language.setCurrentText(self.ocr_default_language)

    def refresh_ocr_profiles(self):
        if not hasattr(self,'ocr_game_profile') or not hasattr(self,'library'): return
        selected=self.ocr_game_profile.currentData() if self.ocr_game_profile.count() else None
        self.ocr_game_profile.blockSignals(True); self.ocr_game_profile.clear()
        self.ocr_game_profile.addItem('Default umum',None)
        for game in sorted(self.library.games,key=lambda item:item['name'].casefold()):
            self.ocr_game_profile.addItem(game['name'],game['id'])
        index=self.ocr_game_profile.findData(selected)
        self.ocr_game_profile.setCurrentIndex(max(0,index)); self.ocr_game_profile.blockSignals(False)
        if self.ocr_game_profile.currentData()!=selected:
            self.load_selected_ocr_profile()

    def load_selected_ocr_profile(self,*_):
        if not hasattr(self,'ocr_game_profile') or not hasattr(self,'library'): return
        identity=self.ocr_game_profile.currentData()
        self.ocr_region=self.load_ocr_region()
        language=self.ocr_default_language
        if identity:
            profile=self.library.get_profile(identity)
            value=profile.get('ocr_region')
            if isinstance(value,list) and len(value)==4 and all(type(n) is int for n in value) and value[2]>=40 and value[3]>=20:
                self.ocr_region=QRect(*value)
            if profile.get('ocr_language'): language=profile['ocr_language']
        self.ocr_language.blockSignals(True)
        self.ocr_language.setCurrentIndex(self.ocr_language.findText(language) if language else -1)
        self.ocr_language.blockSignals(False)

    def save_selected_ocr_language(self,language):
        if not language: return
        identity=self.ocr_game_profile.currentData() if hasattr(self,'ocr_game_profile') else None
        if identity and hasattr(self,'library'):
            profile=self.library.get_profile(identity); profile['ocr_language']=language
            try: self.library.save_profile(identity,profile)
            except OSError as exc: self.ocr_status.setText(f'Profil OCR tidak dapat disimpan: {exc}')
        else:
            self.ocr_default_language=language
            try: atomic_write(self.data/'ocr-language.json',json.dumps(language,ensure_ascii=False).encode())
            except OSError: pass

    def remember_ocr_region(self,region):
        self.ocr_region=QRect(region)
        identity=self.ocr_game_profile.currentData() if hasattr(self,'ocr_game_profile') else None
        if identity and hasattr(self,'library'):
            profile=self.library.get_profile(identity); profile['ocr_region']=[region.x(),region.y(),region.width(),region.height()]
            try: self.library.save_profile(identity,profile)
            except OSError as exc: self.ocr_status.setText(f'Profil OCR tidak dapat disimpan: {exc}')
        else:
            try: atomic_write(self.data/'ocr-region.json',json.dumps([region.x(),region.y(),region.width(),region.height()]).encode())
            except OSError: pass

    def change_region(self):
        """Pick a new OCR area; a running OCR session keeps going with the new area."""
        if not (self.ocr_worker and self.ocr_worker.isRunning()): self.select_region(); return
        if self.selector and self.selector.isVisible(): return
        if self.overlay_settings and self.overlay_settings.isVisible(): self.overlay_settings.close()
        self.ocr_pause.set()
        with self.capture_lock: pass
        if self.overlay: self.overlay.hide()
        self.selector=RegionSelector(QApplication.primaryScreen(),self.ocr_region)
        self.selector.cancelled.connect(self.region_change_finished); self.selector.selected.connect(self.apply_region_change)
        self.selector.show(); self.selector.activateWindow(); self.selector.setFocus()

    def apply_region_change(self,region):
        if self.ocr_worker and self.ocr_worker.isRunning() and self.overlay:
            try: self.overlay.set_region(region)
            except ValueError as exc: self.ocr_status.setText(str(exc))
            else:
                with self.capture_lock: self.ocr_worker.bbox=self.region_bbox(QApplication.primaryScreen(),region)
                self.remember_ocr_region(region); self.ocr_status.setText(f"Area OCR diperbarui • {self.hotkeys['region']} untuk mengubah lagi")
        self.region_change_finished()

    def region_change_finished(self):
        if self.overlay: self.overlay.setVisible(bool(self.latest_subtitle))
        worker=self.ocr_worker
        def resume():
            if worker is self.ocr_worker and worker and worker.isRunning() and not (self.overlay_settings and self.overlay_settings.isVisible()):
                self.ocr_pause.clear()
        QTimer.singleShot(180,resume)

    def start_ocr(self,region):
        screen=QApplication.primaryScreen()
        bbox=self.region_bbox(screen,region)
        try: self.overlay=SubtitleOverlay(screen,region,self.appearance)
        except ValueError as exc: self.show(); self.error(str(exc)); return
        self.remember_ocr_region(region)
        self.ocr_cancel=Event(); self.ocr_pause=Event(); self.capture_lock=Lock(); self.latest_subtitle=''
        self.ocr_worker=OcrWorker(bbox,self.ocr_language.currentText(),self.ocr_translator,self.ocr_cancel,self.ocr_pause,self.capture_lock); self.ocr_worker.stop_hint=self.hotkeys['stop']
        self.ocr_worker.subtitle.connect(self.update_subtitle); self.ocr_worker.status.connect(self.ocr_status.setText)
        self.ocr_worker.failure.connect(self.ocr_failed); self.ocr_worker.finished.connect(self.ocr_finished)
        self.ocr_start.setEnabled(False); self.ocr_stop.setEnabled(True); self.ocr_region_button.setEnabled(True)
        self.ocr_game_profile.setEnabled(False); self.ocr_language.setEnabled(False)
        self.show(); self.showMinimized(); self.overlay.show(); self.ocr_worker.start()
        self.ocr_status.setText(f"OCR aktif • {self.hotkeys['region']} ubah area • {self.hotkeys['stop']} untuk berhenti")

    def update_subtitle(self,text):
        self.latest_subtitle=text
        self.ocr_last.setPlainText(text)
        self.ocr_overlay_preview.set_text(text or 'Subtitle terjemahan\nakan muncul di sini.')
        if self.overlay:
            editing=bool(self.overlay_settings and self.overlay_settings.isVisible())
            self.overlay.set_text(text or ('Contoh subtitle terjemahan.\nTampilan berubah langsung saat Anda mengaturnya.' if editing else ''))
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
        running=bool(self.ocr_worker and self.ocr_worker.isRunning())
        # Steam/Discord-style layer: dim the game, then float the preview and panel above it.
        actions=[('crop','Ubah area',self.change_region),('stop','Hentikan OCR',self.stop_ocr)] if running else []
        actions+=[('library','Buka LinguaPlay',self.open_app_from_overlay),('play','Kembali ke game',lambda:self.overlay_settings and self.overlay_settings.accept())]
        if self.overlay_hub: self.overlay_hub.close()
        self.overlay_hub=OverlayHub(QApplication.primaryScreen(),actions,self.latest_subtitle,running,self.hotkeys['overlay'])
        self.overlay_hub.dismissed.connect(lambda:self.overlay_settings and self.overlay_settings.reject()); self.overlay_hub.present()
        target.label.setText(self.latest_subtitle or 'Contoh subtitle terjemahan.\nTampilan berubah langsung saat Anda mengaturnya.')
        target.show(); target.raise_()
        self.overlay_settings=OverlaySettingsPanel(self.appearance,running,self.hotkeys['overlay'])
        self.overlay_settings.changed.connect(self.apply_overlay_appearance)
        self.overlay_settings.finished.connect(self.overlay_settings_closed)
        self.overlay_settings.adjustSize()
        bounds=QApplication.primaryScreen().availableGeometry()
        self.overlay_settings.move_within_screen(self.overlay_panel_position or QPoint(bounds.right()-self.overlay_settings.width()-32,bounds.top()+150))
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
                self.overlay_settings.notice.setText(('Tersimpan.' if target is None or target.capture_excluded else 'Tersimpan. Posisi disesuaikan agar tidak menutupi area OCR.'))
        except (ValueError,OSError) as exc:
            if self.overlay_settings: self.overlay_settings.notice.setText(str(exc))

    def open_app_from_overlay(self):
        if self.overlay_settings and self.overlay_settings.isVisible(): self.overlay_settings.close()
        self.showNormal(); self.raise_(); self.activateWindow()

    def overlay_settings_closed(self,*args):
        if self.overlay_hub: self.overlay_hub.dismiss(); self.overlay_hub=None
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
        if self.selector and self.selector.isVisible(): self.selector.close()
        self.ocr_start.setEnabled(True); self.ocr_stop.setEnabled(False); self.ocr_region_button.setEnabled(False)
        self.ocr_game_profile.setEnabled(True); self.ocr_language.setEnabled(True)
        self.ocr_status.setText('OCR berhenti.'); self.showNormal()
        if self.closing: self.close()

    def compile_hotkeys(self):
        self.hotkey_codes={action:hotkeys.parse(text) for action,text in self.hotkeys.items()}

    def check_hotkey(self):
        # Recording a new shortcut must not fire the old one.
        if isinstance(QApplication.focusWidget(),QKeySequenceEdit): return
        try:
            user=ctypes.windll.user32
            down=lambda vk:bool(user.GetAsyncKeyState(vk)&0x8000)
            pressed={action:all(down(m) for m in mods) and down(vk) for action,(mods,vk) in self.hotkey_codes.items()}
            self.handle_hotkeys(pressed['overlay'],pressed['stop'],pressed['region'])
        except AttributeError: pass

    def set_background_animation(self,enabled):
        self.ui_prefs['animated_background']=bool(enabled); self.backdrop.set_animated(enabled)
        try: atomic_write(self.data/'ui-settings.json',json.dumps(self.ui_prefs).encode())
        except OSError: pass

    def save_hotkeys(self):
        values={action:edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText) for action,edit in self.hotkey_edits.items()}
        try: self.hotkeys=hotkeys.save(self.data/'hotkeys.json',values)
        except (hotkeys.HotkeyError,OSError) as exc: self.hotkey_status.setText(str(exc)); return
        self.compile_hotkeys(); self.apply_hotkey_texts(); self.hotkey_status.setText('Pintasan disimpan dan langsung aktif.')

    def reset_hotkeys(self):
        for action,edit in self.hotkey_edits.items(): edit.setKeySequence(QKeySequence(hotkeys.DEFAULTS[action]))
        self.save_hotkeys()

    def apply_hotkey_texts(self):
        for badge in self.hotkey_badges: badge.setText(self.hotkeys[badge.hotkey_action])
        for action,edit in getattr(self,'hotkey_edits',{}).items(): edit.setKeySequence(QKeySequence(self.hotkeys[action]))
        if self.ocr_worker: self.ocr_worker.stop_hint=self.hotkeys['stop']

    def handle_hotkeys(self,settings_pressed,stop_pressed,region_pressed=False):
        if stop_pressed and not self.last_hotkey and self.ocr_worker and self.ocr_worker.isRunning():
            self.stop_ocr(); self.showNormal()
        elif settings_pressed and not self.last_settings_hotkey:
            self.toggle_overlay_settings()
        elif region_pressed and not self.last_region_hotkey and self.ocr_worker and self.ocr_worker.isRunning():
            self.change_region()
        self.last_hotkey=stop_pressed; self.last_settings_hotkey=settings_pressed; self.last_region_hotkey=region_pressed

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
