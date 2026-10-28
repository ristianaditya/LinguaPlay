"""Desktop presentation; translation and filesystem work remain in MainWindow."""
from PySide6.QtCore import Qt, QSize, QEasingCurve, QPropertyAnimation, QRect
from pathlib import Path
import sys
from PySide6.QtGui import QPixmap, QKeySequence, QShortcut
from PySide6.QtWidgets import QKeySequenceEdit, QCheckBox
from .hotkeys import LABELS as HOTKEY_LABELS
from PySide6.QtWidgets import (QWidget,QFrame,QHBoxLayout,QVBoxLayout,QStackedWidget,QLabel,
    QLineEdit,QComboBox,QListWidget,QPlainTextEdit,QFormLayout,QHeaderView,QSizePolicy,QScrollArea,QLayout,QAbstractItemView)
from .desktop_widgets import (label,button,card,row,icon_label,DataTable,OverlayPreview,LanguageCombo,LANGUAGES,EmptyList,
    Spinner,ActivityBar,StatusLabel,ReviewPanel,Backdrop,fade_in,ACCENT)
from .icons import icon as make_icon, pixmap as icon_pixmap
from .ocr import available_languages

NAV=[(4,'Library game','library'),(0,'Terjemahan','translate'),(1,'Overlay OCR','scan'),(2,'Cadangan','history'),(3,'Pengaturan','sliders')]
LOCATIONS={0:'TERJEMAHAN  /  SIAPKAN PATCH',1:'OVERLAY OCR',2:'CADANGAN',3:'PENGATURAN',4:'LIBRARY GAME',5:'LIBRARY  /  DETAIL GAME'}

class DesktopLayout:
    def build_shell(self):
        root=Backdrop(); self.backdrop=root; self.setCentralWidget(root)
        outer=QHBoxLayout(root); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)
        rail=QFrame(); rail.setObjectName('libraryRail'); rail.setFixedWidth(224); self.rail=rail
        side=QVBoxLayout(rail); side.setContentsMargins(14,22,14,16); side.setSpacing(4)
        brand=QHBoxLayout(); brand.setSpacing(10); mark=label('','brandMark'); mark.setFixedSize(34,34); mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))/'assets'/'linguaplay-mark.svg'
        if logo.is_file(): mark.setPixmap(QPixmap(str(logo)).scaled(34,34,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        brand.addWidget(mark); brand.addWidget(label('LinguaPlay','brand'),1); side.addLayout(brand); side.addSpacing(24)
        # The highlight slides between navigation entries instead of jumping.
        self.nav_indicator=QFrame(rail); self.nav_indicator.setObjectName('navIndicator'); self.nav_indicator.hide()
        self.nav_animation=QPropertyAnimation(self.nav_indicator,b'geometry',self); self.nav_animation.setDuration(320); self.nav_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.nav=[None]*6; self.pages=QStackedWidget()
        for index,title,icon_name in NAV:
            nav=button('  '+title,lambda checked=False,i=index:self.navigate(i)); nav.setObjectName('railNav'); nav.setCheckable(True)
            nav.setIcon(make_icon(icon_name,'#aab2ad',18)); nav.setIconSize(QSize(18,18)); nav.icon_name=icon_name
            self.nav[index]=nav; side.addWidget(nav)
        side.addSpacing(22); side.addWidget(label('GAME SAYA','railSection')); side.addSpacing(4)
        self.rail_games=QListWidget(); self.rail_games.setObjectName('railGames'); self.rail_games.setMinimumHeight(110)
        self.rail_games.setIconSize(QSize(16,16)); self.rail_games.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.rail_games.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.rail_games.itemClicked.connect(lambda item:self.select_library_game(item.data(Qt.ItemDataRole.UserRole)))
        self.rail_games.itemActivated.connect(lambda item:self.select_library_game(item.data(Qt.ItemDataRole.UserRole)))
        side.addWidget(self.rail_games,1)
        side.addWidget(button('Tambah game',self.add_library_game,icon='plus'))
        self.local_status=label('●  OPUS-MT offline','localStatus')
        side.addSpacing(12); side.addWidget(self.local_status); side.addSpacing(4); side.addWidget(label('LinguaPlay 0.7','version'))
        outer.addWidget(rail)
        body=QWidget(); body.setObjectName('body'); layout=QVBoxLayout(body)
        layout.setContentsMargins(30,18,30,14); layout.setSpacing(18)
        toolbar=QHBoxLayout(); toolbar.setSpacing(10)
        self.back_button=button('Kembali',self.go_back,icon='arrow-left'); self.back_button.setToolTip('Kembali ke halaman sebelumnya (Alt+←)'); self.back_button.hide(); toolbar.addWidget(self.back_button)
        self.location_label=label('LIBRARY GAME','breadcrumb'); toolbar.addWidget(self.location_label,1)
        toolbar.addWidget(button('Tampilan overlay',self.toggle_overlay_settings,icon='layers')); toolbar.addWidget(self.hotkey_badge('overlay')); layout.addLayout(toolbar)
        layout.addWidget(self.pages,1)
        self.progress=ActivityBar(); self.progress.setRange(0,1); self.progress.setValue(0); layout.addWidget(self.progress)
        bottom=QHBoxLayout(); bottom.setSpacing(10); self.spinner=Spinner(16); bottom.addWidget(self.spinner)
        self.status=StatusLabel('Pilih game dari library atau tambahkan game Anda.')
        bottom.addWidget(self.status,1); self.cancel_button=button('Batalkan',self.cancel_job,icon='stop'); self.cancel_button.hide(); bottom.addWidget(self.cancel_button)
        layout.addLayout(bottom); outer.addWidget(body,1)
        self.page_animation=None; self.nav_history=[]
        for sequence in (QKeySequence('Alt+Left'),QKeySequence(QKeySequence.StandardKey.Back)):
            QShortcut(sequence,self,activated=self.go_back)

    def page(self,title,description,icon_name=None):
        widget=QWidget(); layout=QVBoxLayout(widget); layout.setContentsMargins(0,0,0,0); layout.setSpacing(16)
        head=QHBoxLayout(); head.setSpacing(14)
        if icon_name:
            badge=QLabel(); badge.setObjectName('gameMark'); badge.setFixedSize(48,48); badge.setAlignment(Qt.AlignmentFlag.AlignCenter); badge.setPixmap(icon_pixmap(icon_name,ACCENT,24)); head.addWidget(badge)
        text=QVBoxLayout(); text.setSpacing(2); text.addWidget(label(title,'heading')); text.addWidget(label(description,'muted')); head.addLayout(text,1)
        layout.addLayout(head)
        self.pages.addWidget(widget); return layout

    def go_back(self):
        if self.nav_history: self.navigate(self.nav_history.pop(),record=False)

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.BackButton: self.go_back(); event.accept(); return
        super().mousePressEvent(event)

    def navigate(self,index,record=True):
        changed=self.pages.currentIndex()!=index
        if changed and record and hasattr(self,'nav_history'):
            self.nav_history=(self.nav_history+[self.pages.currentIndex()])[-30:]
        if hasattr(self,'back_button'): self.back_button.setVisible(bool(getattr(self,'nav_history',[])))
        self.pages.setCurrentIndex(index)
        for i,nav in enumerate(self.nav):
            if nav is not None:
                active=i==index or (i==4 and index==5); nav.setChecked(active)
                nav.setIcon(make_icon(nav.icon_name,ACCENT if active else '#aab2ad',18))
        if hasattr(self,'location_label'): self.location_label.setText(LOCATIONS.get(index,'LINGUAPLAY'))
        self.move_nav_indicator(animated=self.isVisible())
        if changed and self.isVisible(): self.page_animation=fade_in(self.pages.currentWidget())
        if index in (4,5) and hasattr(self,'library'): self.refresh_library()
        if index==2 and hasattr(self,'history'): self.refresh_history()

    def move_nav_indicator(self,animated=True):
        active=next((nav for nav in self.nav if nav is not None and nav.isChecked()),None)
        if active is None or not active.isVisible(): self.nav_indicator.hide(); return
        target=QRect(active.geometry()); self.nav_indicator.show(); self.nav_indicator.lower()
        if animated and self.nav_indicator.geometry().height()>0:
            self.nav_animation.stop(); self.nav_animation.setStartValue(self.nav_indicator.geometry()); self.nav_animation.setEndValue(target); self.nav_animation.start()
        else: self.nav_indicator.setGeometry(target)

    def hotkey_badge(self,action):
        """Key badge that follows the user's shortcut settings."""
        badge=label(self.hotkeys[action],'keyBadge'); badge.setWordWrap(False); badge.hotkey_action=action
        self.hotkey_badges.append(badge); return badge

    def build_hotkey_card(self):
        frame,layout=card('Pintasan keyboard','keyboard')
        layout.addWidget(label('Berlaku di mana saja, termasuk saat game aktif. Klik kolom lalu tekan kombinasi baru.','small'))
        self.hotkey_edits={}
        for action,text in HOTKEY_LABELS.items():
            edit=QKeySequenceEdit(QKeySequence(self.hotkeys[action])); edit.setMaximumSequenceLength(1); edit.setClearButtonEnabled(True); edit.setFixedWidth(190)
            self.hotkey_edits[action]=edit; layout.addWidget(row({'overlay':'layers','region':'crop','stop':'stop'}[action],text,edit))
        actions=QHBoxLayout(); actions.setSpacing(8)
        actions.addWidget(button('Simpan pintasan',self.save_hotkeys,True,icon='check')); actions.addWidget(button('Kembalikan default',self.reset_hotkeys,icon='refresh')); actions.addStretch(); layout.addLayout(actions)
        self.hotkey_status=StatusLabel(''); layout.addWidget(self.hotkey_status)
        self.animation_toggle=QCheckBox('Animasi latar belakang (cahaya bergerak)'); self.animation_toggle.setChecked(self.ui_prefs.get('animated_background',True))
        self.animation_toggle.toggled.connect(self.set_background_animation); layout.addWidget(self.animation_toggle)
        return frame

    def overlay_card(self):
        frame,layout=card('Overlay dalam game','layers')
        preview=OverlayPreview(self.appearance); layout.addWidget(preview)
        layout.addWidget(button('Atur tampilan overlay',self.toggle_overlay_settings,icon='sliders'))
        hint=QHBoxLayout(); hint.addWidget(label('Buka saat bermain','small'),1); hint.addWidget(self.hotkey_badge('overlay')); layout.addLayout(hint)
        return frame,preview

    @staticmethod
    def sidebar_scroll(widget,layout):
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        widget.setObjectName('sidebarBody')
        scroll=QScrollArea(); scroll.setObjectName('sidebarScroll'); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedWidth(304); scroll.setWidget(widget); return scroll

    def build_patch(self):
        page=QWidget(); layout=QVBoxLayout(page); layout.setContentsMargins(0,0,0,0); layout.setSpacing(16); self.pages.addWidget(page)
        header=QHBoxLayout(); header.setSpacing(14)
        game_mark=QLabel(); game_mark.setObjectName('gameMark'); game_mark.setFixedSize(52,52); game_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        game_mark.setPixmap(icon_pixmap('translate',ACCENT,26)); header.addWidget(game_mark)
        title_col=QVBoxLayout(); title_col.setSpacing(3)
        self.game_title=label('Pilih game','heading'); self.game_title.setWordWrap(False); self.game_title.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        self.game_caption=label('Terjemahkan subtitle sebelum mulai bermain.','muted'); title_col.addWidget(self.game_title); title_col.addWidget(self.game_caption); header.addLayout(title_col,1)
        self.choose_button=button('Pilih folder',self.choose_folder,icon='folder')
        self.translate_button=button('Terjemahkan pilihan',self.translate,True,icon='zap'); self.translate_button.setEnabled(False)
        header.addWidget(self.choose_button); header.addWidget(self.translate_button); layout.addLayout(header)
        columns=QHBoxLayout(); columns.setSpacing(18); left=QWidget(); left_layout=QVBoxLayout(left); left_layout.setContentsMargins(0,0,0,0); left_layout.setSpacing(14)
        source_frame,source_layout=card(eyebrow='Sumber')
        path_row=QHBoxLayout(); path_row.setSpacing(8)
        self.folder=QLineEdit(); self.folder.setReadOnly(True); self.folder.setPlaceholderText('Pilih folder instalasi game untuk memulai')
        self.folder.addAction(make_icon('folder','#8a928d',16),QLineEdit.ActionPosition.LeadingPosition)
        self.scan_button=button('Pindai',self.scan,icon='search'); path_row.addWidget(self.folder,1); path_row.addWidget(self.scan_button); source_layout.addLayout(path_row)
        languages=QHBoxLayout(); languages.setSpacing(10)
        self.quick_source=LanguageCombo(); self.quick_target=LanguageCombo()
        for combo in (self.quick_source,self.quick_target):
            combo.setMinimumWidth(90)
        self.quick_target.set_code('id')
        languages.addWidget(icon_label('globe','#8a928d',16)); languages.addWidget(label('Dari','small')); languages.addWidget(self.quick_source,1)
        languages.addWidget(icon_label('arrow-right',ACCENT,18))
        languages.addWidget(label('Ke','small')); languages.addWidget(self.quick_target,1); source_layout.addLayout(languages)
        left_layout.addWidget(source_frame)
        file_frame,file_layout=card(); file_head=QHBoxLayout(); file_head.addWidget(icon_label('file',ACCENT,17)); file_head.addWidget(label('File subtitle','cardTitle'),1)
        self.summary=label('Belum dipindai','small'); self.summary.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); file_head.addWidget(self.summary,2); file_layout.addLayout(file_head)
        self.files=DataTable(['FILE / FORMAT','DIALOG'],'Pindai folder game untuk menemukan file subtitle.'); self.files.setMinimumHeight(96); self.files.setMaximumHeight(140)
        self.files.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents)
        self.files.itemSelectionChanged.connect(self.show_selected); file_layout.addWidget(self.files); left_layout.addWidget(file_frame)
        translation_frame,translation_layout=card()
        review_head=QHBoxLayout(); review_head.setSpacing(8); review_head.addWidget(icon_label('translate',ACCENT,17)); review_head.addWidget(label('Tinjau & edit','cardTitle'))
        self.review_count=label('','formatTag'); self.review_count.setWordWrap(False); self.review_count.hide(); review_head.addWidget(self.review_count); review_head.addStretch()
        self.review_search=QLineEdit(); self.review_search.setPlaceholderText('Cari kata Inggris atau Indonesia'); self.review_search.setClearButtonEnabled(True); self.review_search.setMaximumWidth(260)
        self.review_search.addAction(make_icon('search','#8a928d',16),QLineEdit.ActionPosition.LeadingPosition); self.review_search.textChanged.connect(self.apply_review_filter); review_head.addWidget(self.review_search)
        self.review_filter=QComboBox(); self.review_filter.addItems(['Semua baris','Sudah saya edit','Terjemahan mesin','Belum diterjemahkan']); self.review_filter.currentIndexChanged.connect(self.apply_review_filter); review_head.addWidget(self.review_filter)
        translation_layout.addLayout(review_head)
        self.preview=DataTable(['TEKS ASLI','TERJEMAHAN','STATUS'],'Terjemahkan file pilihan untuk melihat hasilnya.'); self.preview.setMinimumHeight(150)
        self.preview.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.ResizeToContents); self.preview.setWordWrap(False)
        self.preview.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.preview.setToolTip('Klik dua kali kolom Terjemahan, atau gunakan editor di bawah, untuk memperbaiki terjemahan.')
        self.preview.itemSelectionChanged.connect(self.update_patch_overlay); self.preview.itemSelectionChanged.connect(self.load_review_entry); self.preview.itemChanged.connect(self.review_cell_changed)
        translation_layout.addWidget(self.preview,1)
        self.review_panel=ReviewPanel(); self.review_panel.save_requested.connect(self.save_review_entry); self.review_panel.revert_requested.connect(self.revert_review_entry)
        self.review_panel.step_requested.connect(self.step_review); translation_layout.addWidget(self.review_panel); left_layout.addWidget(translation_frame,1)
        actions=QHBoxLayout(); actions.addWidget(icon_label('info','#8a928d',16)); self.patch_hint=label('Pilih file sesuai bahasa sumber.','small'); actions.addWidget(self.patch_hint,1)
        self.install_button=button('Pasang patch',self.install,True,icon='download'); self.install_button.setEnabled(False); actions.addWidget(self.install_button); left_layout.addLayout(actions)
        # Scroll the work column on short windows instead of squeezing the table and editor together.
        self.preview.setMinimumHeight(220); left.setMinimumHeight(780); left.setObjectName('sidebarBody')
        left_scroll=QScrollArea(); left_scroll.setObjectName('sidebarScroll'); left_scroll.setWidgetResizable(True); left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); left_scroll.setWidget(left); columns.addWidget(left_scroll,1)
        right=QWidget(); right_layout=QVBoxLayout(right); right_layout.setContentsMargins(0,0,0,0); right_layout.setSpacing(14)
        overlay_frame,self.patch_overlay_preview=self.overlay_card(); right_layout.addWidget(overlay_frame)
        profile_frame,profile_layout=card('Profil terjemahan','cpu')
        self.profile_pair=label('en → id','languagePair'); profile_layout.addWidget(self.profile_pair)
        self.profile_provider=label('OpenAI compatible\nqwen2.5:7b','small'); profile_layout.addWidget(self.profile_provider)
        profile_layout.addWidget(button('Ubah layanan',lambda:self.navigate(3),icon='sliders')); right_layout.addWidget(profile_frame)
        support_frame,support_layout=card('Dukungan format','shield'); tags=QHBoxLayout(); tags.setSpacing(6)
        for text in ['SRT','WebVTT','JSON','PSARC']: tags.addWidget(label(text,'formatTag'))
        tags.addStretch(); support_layout.addLayout(tags)
        self.notice=label('Uncharted: The Nathan Drake Collection: subtitle dialog dan teks in-game (menu, HUD, petunjuk tombol, objektif, item). Gunakan OCR jika format belum dikenali.','small'); support_layout.addWidget(self.notice)
        self.diagnostic_button=button('Ekspor diagnostik',self.export_diagnostic,icon='download'); self.diagnostic_button.setEnabled(False); support_layout.addWidget(self.diagnostic_button)
        self.analysis_button=button('Analisis mendalam',lambda:self.folder.text() and self.run_deep_analysis(self.folder.text()),icon='sparkles'); self.analysis_button.setToolTip('Cari di mana game menyimpan teks Inggris, termasuk di dalam arsip.'); support_layout.addWidget(self.analysis_button)
        right_layout.addWidget(support_frame); right_layout.addStretch(); columns.addWidget(self.sidebar_scroll(right,right_layout))
        layout.addLayout(columns,1)

    def build_ocr(self):
        layout=self.page('Overlay OCR','Terjemahkan subtitle yang terlihat di layar sambil tetap berada di dalam game.','scan')
        columns=QHBoxLayout(); columns.setSpacing(18); left=QWidget(); left_layout=QVBoxLayout(left); left_layout.setContentsMargins(0,0,0,0); left_layout.setSpacing(14)
        capture_frame,capture_layout=card('Pembacaan layar','scan')
        self.ocr_language=QComboBox(); self.ocr_language.setMinimumWidth(150)
        try: languages=available_languages()
        except Exception as exc: languages=[]; self.ocr_error=str(exc)
        self.ocr_language.addItems(languages); capture_layout.addWidget(row('globe','Bahasa OCR',self.ocr_language,'Paket bahasa Windows yang dipakai membaca layar'))
        capture_layout.addWidget(row('crop','Area subtitle',None,'Pilih area subtitle di layar utama. Gunakan mode borderless/windowed.'))
        actions=QHBoxLayout(); actions.setSpacing(8); self.ocr_start=button('Pilih area dan mulai',self.select_region,True,icon='play'); self.ocr_stop=button('Hentikan OCR',self.stop_ocr,icon='stop'); self.ocr_stop.setEnabled(False)
        self.ocr_region_button=button('Ubah area',self.change_region,icon='crop'); self.ocr_region_button.setEnabled(False); self.ocr_region_button.setToolTip('Pilih ulang area subtitle tanpa menghentikan OCR.')
        actions.addWidget(self.ocr_start); actions.addWidget(self.ocr_region_button); actions.addWidget(self.ocr_stop); actions.addStretch(); capture_layout.addLayout(actions); left_layout.addWidget(capture_frame)
        output_frame,output_layout=card('Terjemahan langsung','translate')
        self.ocr_status=StatusLabel('OCR belum aktif.'); output_layout.addWidget(self.ocr_status)
        self.ocr_last=QPlainTextEdit(); self.ocr_last.setReadOnly(True); self.ocr_last.setPlaceholderText('Subtitle yang berhasil dibaca dan diterjemahkan akan muncul di sini.'); self.ocr_last.setMinimumHeight(200)
        output_layout.addWidget(self.ocr_last,1); left_layout.addWidget(output_frame,1); columns.addWidget(left,1)
        right=QWidget(); right_layout=QVBoxLayout(right); right_layout.setContentsMargins(0,0,0,0); right_layout.setSpacing(14)
        overlay_frame,self.ocr_overlay_preview=self.overlay_card(); right_layout.addWidget(overlay_frame)
        tips,tips_layout=card('Saat bermain','keyboard')
        for action,text in [('overlay','Buka overlay dalam game. OCR dijeda selama overlay terbuka.'),('region','Ubah area subtitle tanpa menghentikan OCR.'),('stop','Hentikan OCR dan kembali ke aplikasi.')]:
            line=QHBoxLayout(); line.setSpacing(10); line.addWidget(self.hotkey_badge(action),0,Qt.AlignmentFlag.AlignTop); line.addWidget(label(text,'small'),1); tips_layout.addLayout(line)
        tips_layout.addWidget(button('Ubah pintasan',lambda:self.navigate(3),icon='keyboard'))
        right_layout.addWidget(tips)
        privacy,privacy_layout=card('Pemrosesan subtitle','shield'); privacy_layout.addWidget(label('Gambar dibaca lokal oleh Windows OCR. OPUS-MT menerjemahkan teks di PC; provider API mengirim teks ke endpoint pilihan Anda. Tidak ada pemrosesan audio.','small')); right_layout.addWidget(privacy); right_layout.addStretch()
        columns.addWidget(self.sidebar_scroll(right,right_layout)); layout.addLayout(columns,1)

    def build_history(self):
        layout=self.page('Cadangan dan pemulihan','Kembalikan file game ke kondisi sebelum patch dipasang.','history')
        layout.addWidget(label('Tutup game sebelum memulihkan. File yang berubah akibat update game atau mod lain tidak akan ditimpa.','notice'))
        frame,inside=card('Riwayat patch','shield'); self.history=EmptyList('Belum ada cadangan.\nCadangan dibuat saat Anda menyiapkan patch subtitle.'); self.history.setMinimumHeight(300); inside.addWidget(self.history,1)
        line=QHBoxLayout(); line.setSpacing(8); self.restore_button=button('Pulihkan pilihan',self.restore,True,icon='history'); self.open_patch_button=button('Buka folder patch',self.open_patch_folder,icon='folder')
        line.addWidget(self.restore_button); line.addWidget(self.open_patch_button); line.addStretch(); line.addWidget(button('Segarkan',self.refresh_history,icon='refresh')); inside.addLayout(line); layout.addWidget(frame,1)

    def build_settings(self):
        layout=self.page('Layanan terjemahan','Hubungkan model lokal atau API Anda, lalu tentukan bahasa terjemahan.','sliders')
        columns=QHBoxLayout(); columns.setSpacing(18)
        settings_frame,settings_layout=card('Koneksi dan bahasa','cpu'); form=QFormLayout(); form.setVerticalSpacing(14); form.setHorizontalSpacing(20)
        self.provider=QComboBox(); self.provider.addItems(['OpenAI compatible','LibreTranslate','OPUS-MT lokal']); form.addRow('Provider',self.provider)
        self.provider.setCurrentText('OPUS-MT lokal')
        self.endpoint=QLineEdit('http://localhost:11434/v1'); form.addRow('Endpoint',self.endpoint)
        self.model=QLineEdit('qwen2.5:7b'); form.addRow('Model',self.model)
        self.key=QLineEdit(); self.key.setEchoMode(QLineEdit.EchoMode.Password); self.key.setPlaceholderText('Opsional untuk server lokal; hanya selama sesi'); form.addRow('Kunci API',self.key)
        self.source=QComboBox(); self.target=QComboBox()
        for combo in (self.source,self.target): combo.setEditable(True); combo.addItems(['en','id','ja','ko','zh','de','fr','es','pt','ru','ar','th'])
        self.target.setCurrentText('id'); form.addRow('Bahasa sumber',self.source); form.addRow('Bahasa tujuan',self.target); settings_layout.addLayout(form)
        actions=QHBoxLayout(); actions.setSpacing(8); self.test_button=button('Uji koneksi',self.test_connection,True,icon='zap'); self.save_button=button('Simpan pengaturan',self.save_settings,icon='check')
        actions.addWidget(self.test_button); actions.addWidget(self.save_button); actions.addStretch(); settings_layout.addLayout(actions)
        self.connection_status=StatusLabel('Layanan belum diuji.'); settings_layout.addWidget(self.connection_status)
        main_column=QVBoxLayout(); main_column.setSpacing(14); main_column.addWidget(settings_frame); main_column.addWidget(self.build_hotkey_card()); main_column.addStretch(); columns.addLayout(main_column,1)
        help_frame,help_layout=card('Sebelum mulai','info'); help_frame.setFixedWidth(304)
        for title,text,kind in [('OPUS-MT lokal','Model Inggris → Indonesia disertakan dalam paket lengkap. Berjalan offline pada CPU, tanpa endpoint, kunci API, atau Ollama. Bahasa lain belum didukung oleh model ini.','muted'),
                                ('Layanan lainnya','Ollama: http://localhost:11434/v1\nLibreTranslate: http://localhost:5000\nCloud: gunakan endpoint HTTPS Anda.','small'),
                                ('Privasi dan biaya','OPUS-MT memproses teks di PC ini. Provider API mengirim teks ke endpoint pilihan Anda. Kunci hanya disimpan di memori; biaya mengikuti penyedia.','small')]:
            help_layout.addWidget(label(title.upper(),'eyebrow')); help_layout.addWidget(label(text,kind)); help_layout.addSpacing(4)
        help_layout.addStretch(); columns.addWidget(help_frame); layout.addLayout(columns,1)

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
        self.profile_pair.setText(f'{LANGUAGES.get(self.source.currentText(),self.source.currentText())} → {LANGUAGES.get(self.target.currentText(),self.target.currentText())}')
        model={'OPUS-MT lokal':'Inggris → Indonesia · offline','LibreTranslate':'Server LibreTranslate'}.get(self.provider.currentText(),self.model.text())
        self.profile_provider.setText(self.provider.currentText()+'\n'+model)

    def update_provider_controls(self,*args):
        local=self.provider.currentText()=='OPUS-MT lokal'
        for field in (self.endpoint,self.model,self.key): field.setEnabled(not local)
        self.test_button.setText('Uji terjemahan' if local else 'Uji koneksi')

    def update_patch_overlay(self):
        row_index=self.preview.currentRow(); item=self.preview.item(row_index,1) if row_index>=0 else None
        text=item.text() if item and item.text()!='Belum diterjemahkan' else 'Subtitle terjemahan\nakan muncul di sini.'
        self.patch_overlay_preview.set_text(text)
