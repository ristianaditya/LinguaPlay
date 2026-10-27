"""Desktop presentation; translation and filesystem work remain in MainWindow."""
from PySide6.QtCore import Qt
from pathlib import Path
import sys
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QWidget,QFrame,QHBoxLayout,QVBoxLayout,QStackedWidget,QLabel,
    QLineEdit,QComboBox,QProgressBar,QListWidget,QPlainTextEdit,QFormLayout,QHeaderView,QSizePolicy,QScrollArea,QLayout)
from .desktop_widgets import label,button,card,DataTable,OverlayPreview,LanguageCombo,LANGUAGES,EmptyList
from .ocr import available_languages

class DesktopLayout:
    def build_shell(self):
        root=QWidget(); root.setObjectName('appRoot'); self.setCentralWidget(root)
        outer=QHBoxLayout(root); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)
        rail=QFrame(); rail.setObjectName('libraryRail'); rail.setFixedWidth(214)
        side=QVBoxLayout(rail); side.setContentsMargins(16,24,16,16); side.setSpacing(8)
        brand=QHBoxLayout(); mark=label('','brandMark'); mark.setFixedSize(32,32); mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))/'assets'/'linguaplay-mark.svg'
        if logo.is_file(): mark.setPixmap(QPixmap(str(logo)).scaled(32,32,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        brand.addWidget(mark); brand.addWidget(label('LinguaPlay','brand')); side.addLayout(brand); side.addSpacing(26)
        self.nav=[None]*6; self.pages=QStackedWidget()
        for index,title in [(4,'Library game'),(0,'Terjemahan'),(1,'Overlay OCR'),(2,'Cadangan'),(3,'Pengaturan')]:
            nav=button(title,lambda checked=False,i=index:self.navigate(i)); nav.setObjectName('railNav'); nav.setCheckable(True)
            self.nav[index]=nav; side.addWidget(nav)
        side.addSpacing(22); side.addWidget(label('Game saya','railSection'))
        self.rail_games=QListWidget(); self.rail_games.setObjectName('railGames'); self.rail_games.setMinimumHeight(110)
        self.rail_games.itemClicked.connect(lambda item:self.select_library_game(item.data(Qt.ItemDataRole.UserRole)))
        self.rail_games.itemActivated.connect(lambda item:self.select_library_game(item.data(Qt.ItemDataRole.UserRole)))
        side.addWidget(self.rail_games,1)
        side.addWidget(button('+ Tambah game',self.add_library_game))
        self.local_status=label('●  OPUS-MT offline','localStatus')
        side.addSpacing(12); side.addWidget(self.local_status); side.addWidget(label('LinguaPlay 0.6','version'))
        outer.addWidget(rail)
        body=QWidget(); body.setObjectName('body'); layout=QVBoxLayout(body)
        layout.setContentsMargins(28,18,28,12); layout.setSpacing(18)
        toolbar=QHBoxLayout(); self.location_label=label('Library game','breadcrumb'); toolbar.addWidget(self.location_label,1)
        toolbar.addWidget(button('Tampilan overlay',self.toggle_overlay_settings)); toolbar.addWidget(label('Ctrl+Alt+O','keyBadge')); layout.addLayout(toolbar)
        layout.addWidget(self.pages,1)
        self.progress=QProgressBar(); self.progress.setTextVisible(False); self.progress.setRange(0,1); self.progress.setValue(0); layout.addWidget(self.progress)
        bottom=QHBoxLayout(); self.status=label('Pilih game dari library atau tambahkan game Anda.','small')
        bottom.addWidget(self.status,1); self.cancel_button=button('Batalkan',self.cancel_job); self.cancel_button.hide(); bottom.addWidget(self.cancel_button)
        layout.addLayout(bottom); outer.addWidget(body,1)

    def page(self,title,description):
        widget=QWidget(); layout=QVBoxLayout(widget); layout.setContentsMargins(0,0,0,0); layout.setSpacing(16)
        layout.addWidget(label(title,'heading')); layout.addWidget(label(description,'muted'))
        self.pages.addWidget(widget); return layout

    def navigate(self,index):
        self.pages.setCurrentIndex(index)
        for i,nav in enumerate(self.nav):
            if nav is not None: nav.setChecked(i==index or (i==4 and index==5))
        if hasattr(self,'location_label'): self.location_label.setText({0:'Terjemahan / Siapkan patch',1:'Overlay OCR',2:'Cadangan',3:'Pengaturan',4:'Library game',5:'Library / Detail game'}.get(index,'LinguaPlay'))
        if index in (4,5) and hasattr(self,'library'): self.refresh_library()
        if index==2 and hasattr(self,'history'): self.refresh_history()

    def overlay_card(self):
        frame,layout=card('Overlay dalam game')
        preview=OverlayPreview(self.appearance); layout.addWidget(preview)
        layout.addWidget(button('Atur tampilan overlay',self.toggle_overlay_settings))
        hint=QHBoxLayout(); hint.addWidget(label('Buka saat bermain','small'),1); hint.addWidget(label('Ctrl+Alt+O','keyBadge')); layout.addLayout(hint)
        return frame,preview

    @staticmethod
    def sidebar_scroll(widget,layout):
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        widget.setObjectName('sidebarBody')
        scroll=QScrollArea(); scroll.setObjectName('sidebarScroll'); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedWidth(294); scroll.setWidget(widget); return scroll

    def build_patch(self):
        page=QWidget(); layout=QVBoxLayout(page); layout.setContentsMargins(0,0,0,0); layout.setSpacing(16); self.pages.addWidget(page)
        header=QHBoxLayout(); header.setSpacing(12)
        game_mark=label('Aa','gameMark'); game_mark.setFixedSize(48,48); game_mark.setAlignment(Qt.AlignmentFlag.AlignCenter); header.addWidget(game_mark)
        title_col=QVBoxLayout(); title_col.setSpacing(3)
        self.game_title=label('Pilih game','heading'); self.game_title.setWordWrap(False); self.game_title.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        self.game_caption=label('Terjemahkan subtitle sebelum mulai bermain.','muted'); title_col.addWidget(self.game_title); title_col.addWidget(self.game_caption); header.addLayout(title_col,1)
        self.demo_button=button('Buka contoh',self.open_demo); self.choose_button=button('Pilih folder',self.choose_folder)
        self.translate_button=button('Terjemahkan pilihan',self.translate,True); self.translate_button.setEnabled(False)
        header.addWidget(self.demo_button); header.addWidget(self.choose_button); header.addWidget(self.translate_button); layout.addLayout(header)
        columns=QHBoxLayout(); columns.setSpacing(18); left=QWidget(); left_layout=QVBoxLayout(left); left_layout.setContentsMargins(0,0,0,0); left_layout.setSpacing(12)
        source_frame,source_layout=card()
        path_row=QHBoxLayout(); path_row.setSpacing(8)
        self.folder=QLineEdit(); self.folder.setReadOnly(True); self.folder.setPlaceholderText('Pilih folder instalasi game untuk memulai')
        self.scan_button=button('Pindai',self.scan); path_row.addWidget(self.folder,1); path_row.addWidget(self.scan_button); source_layout.addLayout(path_row)
        languages=QHBoxLayout(); languages.setSpacing(10)
        self.quick_source=LanguageCombo(); self.quick_target=LanguageCombo()
        for combo in (self.quick_source,self.quick_target):
            combo.setMinimumWidth(90)
        self.quick_target.set_code('id')
        languages.addWidget(label('Bahasa sumber','small')); languages.addWidget(self.quick_source,1)
        arrow=label('â†’','muted'); arrow.setAlignment(Qt.AlignmentFlag.AlignCenter); languages.addWidget(arrow)
        languages.addWidget(label('Terjemahkan ke','small')); languages.addWidget(self.quick_target,1); source_layout.addLayout(languages)
        left_layout.addWidget(source_frame)
        file_frame,file_layout=card(); file_head=QHBoxLayout(); file_head.addWidget(label('File subtitle','cardTitle'),1)
        self.summary=label('Belum dipindai','small'); self.summary.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); file_head.addWidget(self.summary,2); file_layout.addLayout(file_head)
        self.files=DataTable(['File / format','Dialog'],'Pindai folder game untuk menemukan file subtitle.'); self.files.setMinimumHeight(105); self.files.setMaximumHeight(166)
        self.files.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents)
        self.files.itemSelectionChanged.connect(self.show_selected); file_layout.addWidget(self.files); left_layout.addWidget(file_frame)
        translation_frame,translation_layout=card(); trans_head=QHBoxLayout(); trans_head.addWidget(label('Tinjau terjemahan','cardTitle'),1)
        translation_layout.addLayout(trans_head)
        self.preview=DataTable(['Teks asli','Terjemahan'],'Terjemahkan file pilihan untuk melihat hasilnya.'); self.preview.setMinimumHeight(138)
        self.preview.itemSelectionChanged.connect(self.update_patch_overlay); translation_layout.addWidget(self.preview,1); left_layout.addWidget(translation_frame,1)
        actions=QHBoxLayout(); self.patch_hint=label('Pilih file sesuai bahasa sumber.','small'); actions.addWidget(self.patch_hint,1)
        self.install_button=button('Pasang patch',self.install); self.install_button.setEnabled(False); actions.addWidget(self.install_button); left_layout.addLayout(actions)
        columns.addWidget(left,1)
        right=QWidget(); right_layout=QVBoxLayout(right); right_layout.setContentsMargins(0,0,0,0); right_layout.setSpacing(12)
        overlay_frame,self.patch_overlay_preview=self.overlay_card(); right_layout.addWidget(overlay_frame)
        profile_frame,profile_layout=card('Profil terjemahan')
        self.profile_pair=label('en â†’ id','languagePair'); profile_layout.addWidget(self.profile_pair)
        self.profile_provider=label('OpenAI compatible\nqwen2.5:7b','small'); profile_layout.addWidget(self.profile_provider)
        profile_layout.addWidget(button('Ubah layanan',lambda:self.navigate(3))); right_layout.addWidget(profile_frame)
        support_frame,support_layout=card('Dukungan format'); tags=QHBoxLayout()
        for text in ['SRT','WebVTT','JSON strings']: tags.addWidget(label(text,'formatTag'))
        support_layout.addLayout(tags)
        self.notice=label('Arsip game khusus, termasuk Uncharted, belum didukung. Gunakan OCR jika format belum dikenali.','small'); support_layout.addWidget(self.notice)
        self.diagnostic_button=button('Ekspor diagnostik',self.export_diagnostic); self.diagnostic_button.setEnabled(False); support_layout.addWidget(self.diagnostic_button)
        right_layout.addWidget(support_frame); right_layout.addStretch(); columns.addWidget(self.sidebar_scroll(right,right_layout))
        layout.addLayout(columns,1)

    def build_ocr(self):
        layout=self.page('Overlay OCR','Terjemahkan subtitle yang terlihat di layar sambil tetap berada di dalam game.')
        columns=QHBoxLayout(); columns.setSpacing(18); left=QWidget(); left_layout=QVBoxLayout(left); left_layout.setContentsMargins(0,0,0,0); left_layout.setSpacing(12)
        capture_frame,capture_layout=card('Pembacaan layar'); form=QFormLayout(); form.setVerticalSpacing(12)
        self.ocr_language=QComboBox()
        try: languages=available_languages()
        except Exception as exc: languages=[]; self.ocr_error=str(exc)
        self.ocr_language.addItems(languages); form.addRow('Bahasa OCR',self.ocr_language); capture_layout.addLayout(form)
        capture_layout.addWidget(label('Pilih area subtitle pada layar utama. Gunakan mode borderless/windowed.','muted'))
        actions=QHBoxLayout(); self.ocr_start=button('Pilih area dan mulai',self.select_region,True); self.ocr_stop=button('Hentikan OCR',self.stop_ocr); self.ocr_stop.setEnabled(False)
        actions.addWidget(self.ocr_start); actions.addWidget(self.ocr_stop); actions.addStretch(); capture_layout.addLayout(actions); left_layout.addWidget(capture_frame)
        output_frame,output_layout=card('Terjemahan langsung')
        self.ocr_status=label('OCR belum aktif.','small'); output_layout.addWidget(self.ocr_status)
        self.ocr_last=QPlainTextEdit(); self.ocr_last.setReadOnly(True); self.ocr_last.setPlaceholderText('Subtitle yang berhasil dibaca dan diterjemahkan akan muncul di sini.'); self.ocr_last.setMinimumHeight(200)
        output_layout.addWidget(self.ocr_last,1); left_layout.addWidget(output_frame,1); columns.addWidget(left,1)
        right=QWidget(); right_layout=QVBoxLayout(right); right_layout.setContentsMargins(0,0,0,0); right_layout.setSpacing(12)
        overlay_frame,self.ocr_overlay_preview=self.overlay_card(); right_layout.addWidget(overlay_frame)
        tips,tips_layout=card('Saat bermain')
        tips_layout.addWidget(label('Ctrl+Alt+O','keyBadge')); tips_layout.addWidget(label('Buka panel tampilan. OCR dijeda selama panel terbuka.','small'))
        tips_layout.addWidget(label('Ctrl+Alt+F10','keyBadge')); tips_layout.addWidget(label('Hentikan OCR dan kembali ke aplikasi.','small')); right_layout.addWidget(tips)
        privacy,privacy_layout=card('Pemrosesan subtitle'); privacy_layout.addWidget(label('Gambar dibaca lokal oleh Windows OCR. OPUS-MT menerjemahkan teks di PC; provider API mengirim teks ke endpoint pilihan Anda. Tidak ada pemrosesan audio.','small')); right_layout.addWidget(privacy); right_layout.addStretch()
        columns.addWidget(self.sidebar_scroll(right,right_layout)); layout.addLayout(columns,1)

    def build_history(self):
        layout=self.page('Cadangan dan pemulihan','Kembalikan file game ke kondisi sebelum patch dipasang.')
        layout.addWidget(label('Tutup game sebelum memulihkan. File yang berubah akibat update game atau mod lain tidak akan ditimpa.','notice'))
        frame,inside=card('Riwayat patch'); self.history=EmptyList('Belum ada cadangan.\nCadangan dibuat saat Anda menyiapkan patch subtitle.'); self.history.setMinimumHeight(300); inside.addWidget(self.history,1)
        row=QHBoxLayout(); self.restore_button=button('Pulihkan pilihan',self.restore,True); self.open_patch_button=button('Buka folder patch',self.open_patch_folder)
        row.addWidget(self.restore_button); row.addWidget(self.open_patch_button); row.addStretch(); row.addWidget(button('Segarkan',self.refresh_history)); inside.addLayout(row); layout.addWidget(frame,1)

    def build_settings(self):
        layout=self.page('Layanan terjemahan','Hubungkan model lokal atau API Anda, lalu tentukan bahasa terjemahan.')
        columns=QHBoxLayout(); columns.setSpacing(18)
        settings_frame,settings_layout=card('Koneksi dan bahasa'); form=QFormLayout(); form.setVerticalSpacing(14); form.setHorizontalSpacing(20)
        self.provider=QComboBox(); self.provider.addItems(['OpenAI compatible','LibreTranslate','OPUS-MT lokal']); form.addRow('Provider',self.provider)
        self.provider.setCurrentText('OPUS-MT lokal')
        self.endpoint=QLineEdit('http://localhost:11434/v1'); form.addRow('Endpoint',self.endpoint)
        self.model=QLineEdit('qwen2.5:7b'); form.addRow('Model',self.model)
        self.key=QLineEdit(); self.key.setEchoMode(QLineEdit.EchoMode.Password); self.key.setPlaceholderText('Opsional untuk server lokal; hanya selama sesi'); form.addRow('Kunci API',self.key)
        self.source=QComboBox(); self.target=QComboBox()
        for combo in (self.source,self.target): combo.setEditable(True); combo.addItems(['en','id','ja','ko','zh','de','fr','es','pt','ru','ar','th'])
        self.target.setCurrentText('id'); form.addRow('Bahasa sumber',self.source); form.addRow('Bahasa tujuan',self.target); settings_layout.addLayout(form)
        actions=QHBoxLayout(); self.test_button=button('Uji koneksi',self.test_connection,True); self.save_button=button('Simpan pengaturan',self.save_settings)
        actions.addWidget(self.test_button); actions.addWidget(self.save_button); actions.addStretch(); settings_layout.addLayout(actions)
        self.connection_status=label('Layanan belum diuji.','small'); settings_layout.addWidget(self.connection_status); settings_layout.addStretch(); columns.addWidget(settings_frame,1)
        help_frame,help_layout=card('Sebelum mulai'); help_frame.setFixedWidth(294)
        help_layout.addWidget(label('OPUS-MT lokal','section')); help_layout.addWidget(label('Model Inggris â†’ Indonesia disertakan dalam paket lengkap. Berjalan offline pada CPU, tanpa endpoint, kunci API, atau Ollama. Bahasa lain belum didukung oleh model ini.','muted'))
        help_layout.addWidget(label('Layanan lainnya','section')); help_layout.addWidget(label('Ollama: http://localhost:11434/v1\nLibreTranslate: http://localhost:5000\nCloud: gunakan endpoint HTTPS Anda.','small'))
        help_layout.addWidget(label('Privasi dan biaya','section')); help_layout.addWidget(label('OPUS-MT memproses teks di PC ini. Provider API mengirim teks ke endpoint pilihan Anda. Kunci hanya disimpan di memori; biaya mengikuti penyedia.','small')); help_layout.addStretch()
        columns.addWidget(help_frame); layout.addLayout(columns,1)

    def bind_dashboard(self):
        self.quick_source.set_code(self.source.currentText()); self.quick_target.set_code(self.target.currentText())
        self.quick_source.code_changed.connect(self.source.setCurrentText); self.source.currentTextChanged.connect(self.quick_source.set_code)
        self.quick_target.code_changed.connect(self.target.setCurrentText); self.target.currentTextChanged.connect(self.quick_target.set_code)
        for combo in (self.source,self.target,self.provider): combo.currentTextChanged.connect(self.update_profile)
        self.provider.currentTextChanged.connect(self.update_provider_controls)
        self.update_provider_controls()
        self.model.textChanged.connect(self.update_profile); self.update_profile()

    def update_profile(self,*args):
        self.local_status.setText('●  OPUS-MT offline' if self.provider.currentText()=='OPUS-MT lokal' else '●  Provider API dipilih')
        self.profile_pair.setText(f'{LANGUAGES.get(self.source.currentText(),self.source.currentText())} â†’ {LANGUAGES.get(self.target.currentText(),self.target.currentText())}')
        model={'OPUS-MT lokal':'Inggris â†’ Indonesia Â· offline','LibreTranslate':'Server LibreTranslate'}.get(self.provider.currentText(),self.model.text())
        self.profile_provider.setText(self.provider.currentText()+'\n'+model)

    def update_provider_controls(self,*args):
        local=self.provider.currentText()=='OPUS-MT lokal'
        for field in (self.endpoint,self.model,self.key): field.setEnabled(not local)
        self.test_button.setText('Uji terjemahan' if local else 'Uji koneksi')

    def update_patch_overlay(self):
        row=self.preview.currentRow(); item=self.preview.item(row,1) if row>=0 else None
        text=item.text() if item and item.text()!='Belum diterjemahkan' else 'Subtitle terjemahan\nakan muncul di sini.'
        self.patch_overlay_preview.set_text(text)
