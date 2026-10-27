from pathlib import Path
import shutil
import hashlib
import json
import sys
from datetime import datetime,timezone
from PySide6.QtCore import Qt,QSize,QRectF,QUrl,QFileInfo
from PySide6.QtGui import QPixmap,QPainter,QColor,QLinearGradient,QFont,QIcon,QDesktopServices,QPainterPath,QFontMetrics
from PySide6.QtWidgets import (QWidget,QFrame,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QLineEdit,
    QComboBox,QListWidget,QListWidgetItem,QAbstractItemView,QFileDialog,QFileIconProvider,
    QDialog,QDialogButtonBox,QFormLayout,QPushButton)
from .desktop_widgets import label,button
from .library import GameLibrary,discover_steam,game_patch_state,patches_for,set_play_mode,launch_executable,validate_launch_target
from .adapters import scan_game_root

STATE_LABELS={'installed':'Terjemahan terpasang','ready':'Patch siap dimainkan','original':'Versi asli','recovery':'Perlu pemulihan'}


def cover_pixmap(game,size):
    result=QPixmap(size); result.fill(QColor('#23282a'))
    painter=QPainter(result); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    image=QPixmap(game.get('cover','')) if game.get('cover') else QPixmap()
    if not image.isNull():
        image=image.scaled(size,Qt.AspectRatioMode.KeepAspectRatioByExpanding,Qt.TransformationMode.SmoothTransformation)
        painter.drawPixmap((size.width()-image.width())//2,(size.height()-image.height())//2,image)
    else:
        gradient=QLinearGradient(0,0,size.width(),size.height()); gradient.setColorAt(0,QColor('#334440')); gradient.setColorAt(1,QColor('#171b20'))
        painter.fillRect(result.rect(),gradient); painter.setPen(QColor('#d6fb51')); painter.setFont(QFont('Segoe UI',max(24,size.width()//5),QFont.Weight.DemiBold))
        painter.drawText(result.rect(),Qt.AlignmentFlag.AlignCenter,''.join(w[0] for w in game['name'].split()[:2]).upper())
    painter.end(); return result

def game_tile(game,state):
    tile=QPixmap(206,286); tile.fill(QColor('#1d2021')); painter=QPainter(tile)
    painter.drawPixmap(0,0,cover_pixmap(game,QSize(206,218)))
    font=QFont('Segoe UI'); font.setPixelSize(13); font.setWeight(QFont.Weight.DemiBold); painter.setFont(font); painter.setPen(QColor('#f4f5f3'))
    painter.drawText(10,244,QFontMetrics(font).elidedText(game['name'],Qt.TextElideMode.ElideRight,186))
    font.setPixelSize(11); font.setWeight(QFont.Weight.Normal); painter.setFont(font); painter.setPen(QColor('#d6eb9d') if state!='original' else QColor('#a8adaa'))
    painter.drawText(10,268,STATE_LABELS[state]); painter.end(); return tile


class GameArtwork(QFrame):
    def __init__(self):
        super().__init__(); self.game=None; self.setMinimumHeight(208); self.setObjectName('gameArtwork')
    def paintEvent(self,event):
        painter=QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip=QPainterPath(); clip.addRoundedRect(QRectF(self.rect()),12,12); painter.setClipPath(clip)
        painter.fillRect(self.rect(),QColor('#1e2625'))
        if self.game and self.game.get('cover'):
            painter.drawPixmap(self.rect(),cover_pixmap(self.game,self.size()))
        shade=QLinearGradient(0,0,self.width(),0); shade.setColorAt(0,QColor(15,20,19,245)); shade.setColorAt(.45,QColor(15,20,19,190)); shade.setColorAt(1,QColor(15,20,19,15))
        painter.fillRect(self.rect(),shade); painter.end()


class GameEditor(QDialog):
    def __init__(self,parent,game=None):
        super().__init__(parent); self.setWindowTitle('Pengaturan game' if game else 'Tambah game'); self.setMinimumWidth(580)
        layout=QVBoxLayout(self); layout.setSpacing(16); form=QFormLayout(); form.setVerticalSpacing(12)
        self.name=QLineEdit((game or {}).get('name','')); form.addRow('Nama game',self.name)
        self.exe=QLineEdit((game or {}).get('executable','')); self.root=QLineEdit((game or {}).get('root','')); self.cover=QLineEdit((game or {}).get('cover',''))
        for title,field,callback in [('File EXE',self.exe,self.choose_exe),('Folder game',self.root,self.choose_root),('Cover',self.cover,self.choose_cover)]:
            row=QHBoxLayout(); row.addWidget(field,1); picker=button('Pilih',callback)
            if game and game.get('steam_id') and title!='Cover': picker.setEnabled(False)
            row.addWidget(picker); form.addRow(title,row)
        if game and game.get('steam_id'): self.exe.setEnabled(False); self.root.setReadOnly(True)
        layout.addLayout(form); layout.addWidget(label('Folder game mencakup file EXE dan subtitle. Cover bersifat opsional.','small'))
        self.message=label('','errorText'); layout.addWidget(self.message)
        actions=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); actions.accepted.connect(self.validate); actions.rejected.connect(self.reject); layout.addWidget(actions)
        self.steam=bool(game and game.get('steam_id'))
        self.steam_root=(game or {}).get('root','')
    def choose_exe(self):
        path,_=QFileDialog.getOpenFileName(self,'Pilih EXE game','','Aplikasi Windows (*.exe)')
        if path:
            self.exe.setText(path); self.root.setText(str(Path(path).parent))
            if not self.name.text(): self.name.setText(Path(path).stem)
    def choose_root(self):
        path=QFileDialog.getExistingDirectory(self,'Folder instalasi game')
        if path: self.root.setText(path)
    def choose_cover(self):
        path,_=QFileDialog.getOpenFileName(self,'Pilih cover game','','Gambar (*.png *.jpg *.jpeg *.webp)')
        if path: self.cover.setText(path)
    def validate(self):
        try:
            if not self.name.text().strip(): raise ValueError('Isi nama game.')
            root=Path(self.root.text()).resolve(strict=True)
            if not root.is_dir(): raise ValueError('Folder game tidak valid.')
            if self.steam and root!=Path(self.steam_root).resolve(): raise ValueError('Lokasi game Steam mengikuti instalasi yang terdeteksi.')
            if not self.steam:
                exe=Path(self.exe.text()).resolve(strict=True)
                if exe.suffix.lower()!='.exe' or not exe.is_file() or not exe.is_relative_to(root): raise ValueError('Pilih EXE yang berada di dalam folder game.')
            if self.cover.text() and QPixmap(self.cover.text()).isNull(): raise ValueError('Gambar cover tidak dapat dibaca.')
            self.accept()
        except (OSError,ValueError) as exc: self.message.setText(str(exc))


class LibraryUI:
    def build_library(self):
        self.library=GameLibrary(self.data); self.selected_game_id=None
        page=QWidget(); layout=QVBoxLayout(page); layout.setContentsMargins(0,0,0,0); layout.setSpacing(20); self.pages.addWidget(page)
        intro=QWidget(); intro.setFixedHeight(100); hero=QHBoxLayout(intro); hero.setContentsMargins(0,8,0,8)
        title=QVBoxLayout(); title.addWidget(label('Library game','libraryHeading')); title.addWidget(label('Pilih game, atur terjemahan, lalu mainkan.','muted')); hero.addLayout(title,1)
        hero.addWidget(button('Deteksi Steam',self.detect_library_games)); hero.addWidget(button('+ Tambah game',self.add_library_game,True)); layout.addWidget(intro)
        heading=QHBoxLayout(); heading.addWidget(label('Koleksi Anda','sectionTitle')); self.library_count=label('0 game','small'); heading.addWidget(self.library_count); heading.addStretch()
        self.library_search=QLineEdit(); self.library_search.setPlaceholderText('Cari game di library'); self.library_search.setMaximumWidth(240); self.library_search.textChanged.connect(self.refresh_library); heading.addWidget(self.library_search)
        self.library_filter=QComboBox(); self.library_filter.addItems(['Semua game','Dengan patch','Tanpa patch']); self.library_filter.currentIndexChanged.connect(self.refresh_library); heading.addWidget(self.library_filter); layout.addLayout(heading)
        self.game_grid=QListWidget(); self.game_grid.setObjectName('gameGrid'); self.game_grid.setViewMode(QListWidget.ViewMode.IconMode); self.game_grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.game_grid.setMovement(QListWidget.Movement.Static); self.game_grid.setIconSize(QSize(206,286)); self.game_grid.setGridSize(QSize(242,326)); self.game_grid.setSpacing(2); self.game_grid.setWordWrap(True)
        self.game_grid.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.game_grid.itemClicked.connect(lambda item:self.select_library_game(item.data(Qt.ItemDataRole.UserRole))); self.game_grid.itemActivated.connect(lambda item:self.select_library_game(item.data(Qt.ItemDataRole.UserRole)))
        self.library_empty=QFrame(); self.library_empty.setObjectName('libraryEmpty'); empty=QVBoxLayout(self.library_empty); empty.setContentsMargins(40,32,40,32); empty.addStretch()
        empty.addWidget(label('Library Anda dimulai di sini.','emptyTitle')); self.library_empty_text=label('Tambahkan EXE game atau deteksi instalasi Steam.\nGame bisa dimainkan dengan versi asli maupun terjemahan.','muted'); empty.addWidget(self.library_empty_text)
        row=QHBoxLayout(); row.addWidget(button('Tambah game pertama',self.add_library_game,True)); row.addWidget(button('Coba file subtitle contoh',self.open_library_demo)); row.addStretch(); empty.addLayout(row); empty.addStretch()
        layout.addWidget(self.library_empty,1); layout.addWidget(self.game_grid,1)
        layout.addWidget(label('Patch mengganti file subtitle yang didukung. Gunakan overlay OCR untuk format game yang belum dikenali.','small'))
        self.build_game_detail(); self.refresh_library()
        if self.library.load_warning: self.status.setText(self.library.load_warning)

    def build_game_detail(self):
        page=QWidget(); layout=QVBoxLayout(page); layout.setContentsMargins(0,0,0,0); layout.setSpacing(20); self.pages.addWidget(page)
        self.detail_hero=GameArtwork(); hero=QVBoxLayout(self.detail_hero); hero.setContentsMargins(28,25,28,25)
        self.detail_platform=label('PC GAME','small'); hero.addWidget(self.detail_platform)
        self.detail_title=label('Pilih game','gameHeading'); hero.addWidget(self.detail_title); self.detail_status=label('Versi asli','gameState'); hero.addWidget(self.detail_status); hero.addStretch()
        row=QHBoxLayout(); self.play_mode=QComboBox(); self.play_mode.addItem('Mainkan versi asli','original'); self.play_mode.addItem('Mainkan dengan terjemahan','translated'); row.addWidget(self.play_mode)
        self.play_button=button('Play',self.play_library_game,True); self.play_button.setMinimumWidth(130)
        asset=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))/'assets'/'control-play.svg'; self.play_button.setIcon(QIcon(str(asset))); self.play_button.setIconSize(QSize(14,14))
        row.addWidget(self.play_button); row.addStretch(); row.addWidget(button('Atur game',self.edit_library_game)); hero.addLayout(row); layout.addWidget(self.detail_hero)
        columns=QHBoxLayout(); columns.setSpacing(22); main=QVBoxLayout(); main.setSpacing(16)
        self.detail_patch_text=label('Belum ada patch terjemahan untuk game ini.','muted')
        self.detail_compat=label('Dukungan belum dipindai.','muted')
        main.addWidget(self.control_group('Terjemahan subtitle',self.detail_patch_text,[('Siapkan terjemahan',self.prepare_library_game),('Scan dukungan',self.scan_library_support),('Lihat cadangan',lambda:self.navigate(2))]))
        main.addWidget(self.detail_compat)
        self.detail_play_note=label('Pilihan mode diterapkan saat Play. Tutup game sebelum memasang atau memulihkan patch.','small'); main.addWidget(self.detail_play_note)
        main.addWidget(self.control_group('Overlay saat bermain',label('Baca subtitle di layar dan tampilkan terjemahan di atas game.','muted'),[('Buka overlay OCR',lambda:self.navigate(1)),('Atur tampilan',self.toggle_overlay_settings)]))
        main.addStretch(); columns.addLayout(main,1)
        info=QFrame(); info.setObjectName('detailInfo'); inside=QVBoxLayout(info); inside.setContentsMargins(20,20,20,20); inside.setSpacing(14); info.setFixedWidth(264)
        inside.addWidget(label('Instalasi game','section')); self.detail_location=label('','small'); self.detail_location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); inside.addWidget(self.detail_location)
        inside.addWidget(button('Buka folder game',self.open_library_folder)); inside.addStretch(); inside.addWidget(label('Ctrl+Alt+O','keyBadge')); inside.addWidget(label('Buka pengaturan overlay di dalam game.','small')); columns.addWidget(info); layout.addLayout(columns,1)
        remove=QHBoxLayout(); remove.addWidget(button('Hapus dari library',self.remove_library_game)); remove.addWidget(label('File game dan cadangan tetap tersimpan.','small'),1); layout.addLayout(remove)

    def control_group(self,title,description,actions):
        frame=QFrame(); frame.setObjectName('controlGroup'); layout=QVBoxLayout(frame); layout.setContentsMargins(20,18,20,18); layout.setSpacing(14)
        layout.addWidget(label(title,'sectionTitle')); layout.addWidget(description); row=QHBoxLayout()
        for text,callback in actions: row.addWidget(button(text,callback))
        row.addStretch(); layout.addLayout(row); return frame

    def refresh_library(self,*args):
        if not hasattr(self,'game_grid'): return
        self.rail_games.clear(); self.game_grid.clear(); query=self.library_search.text().strip().casefold(); filter_index=self.library_filter.currentIndex(); visible=0
        for game in sorted(self.library.games,key=lambda g:g['name'].casefold()):
            rail=QListWidgetItem(game['name']); rail.setData(Qt.ItemDataRole.UserRole,game['id']); self.rail_games.addItem(rail)
            state=game_patch_state(game,self.storage); patched=state!='original'
            if query not in game['name'].casefold() or (filter_index==1 and not patched) or (filter_index==2 and patched): continue
            icon=game_tile(game,state); item=QListWidgetItem(QIcon(icon),''); item.setData(Qt.ItemDataRole.UserRole,game['id']); item.setData(Qt.ItemDataRole.AccessibleTextRole,game['name']+' '+STATE_LABELS[state]); item.setToolTip(game['name']+' — '+STATE_LABELS[state]); item.setSizeHint(QSize(226,310)); self.game_grid.addItem(item); visible+=1
        self.library_count.setText(f'{len(self.library.games)} game'); self.game_grid.setVisible(visible>0); self.library_empty.setVisible(visible==0)
        self.library_empty_text.setText('Tidak ada game yang cocok. Ubah pencarian atau filter.' if self.library.games else 'Tambahkan EXE game atau deteksi instalasi Steam.\nGame bisa dimainkan dengan versi asli maupun terjemahan.')
        self.refresh_game_detail()

    def current_library_game(self):
        return next((g for g in self.library.games if g['id']==self.selected_game_id),None)

    def select_library_game(self,identity):
        self.selected_game_id=identity; self.refresh_game_detail()
        game=self.current_library_game()
        if game: self.play_mode.setCurrentIndex(1 if game_patch_state(game,self.storage)=='installed' else 0)
        self.navigate(5)

    def refresh_game_detail(self):
        game=self.current_library_game()
        if not game: return
        state=game_patch_state(game,self.storage); self.detail_hero.game=game; self.detail_hero.update(); self.detail_title.setText(game['name']); self.detail_platform.setText('STEAM' if game.get('steam_id') else 'PC • GAME LOKAL')
        self.detail_status.setText(STATE_LABELS[state]); self.detail_location.setText(game['root'].replace('\\',' / '))
        self.detail_patch_text.setText({'original':'Belum ada patch. Siapkan terjemahan untuk subtitle yang didukung, atau mainkan versi asli.','ready':'Patch tersimpan dan siap digunakan. Pilih terjemahan lalu tekan Play untuk memasangnya.','installed':'Terjemahan aktif. Pilih versi asli lalu tekan Play untuk memulihkan subtitle asli.','recovery':'Pemasangan sebelumnya belum selesai. Buka Cadangan dan pulihkan sebelum bermain.'}[state])
        profile=self.library.get_profile(game['id'])
        self.detail_compat.setText({'patch':'Dukungan patch tersedia','ocr':'Format file belum dikenal — gunakan OCR','unsupported':'Subtitle belum ditemukan','unknown':'Dukungan belum dipindai'}.get(profile.get('support_level'),'Dukungan belum dipindai'))
        self.play_button.setEnabled(state!='recovery'); self.play_mode.model().item(1).setEnabled(state not in ('original','recovery'))

    def _store_cover(self,path):
        if not path: return ''
        source=Path(path); target=self.data/'covers'; target.mkdir(exist_ok=True); destination=target/(hashlib.sha256(source.read_bytes()).hexdigest()[:20]+source.suffix.lower()); shutil.copyfile(source,destination) if source.resolve()!=destination.resolve() else None; return str(destination)

    def add_library_game(self):
        dialog=GameEditor(self)
        if dialog.exec()!=QDialog.DialogCode.Accepted: return
        try:
            game=self.library.add_executable(dialog.exe.text(),dialog.name.text().strip()); game['root']=str(Path(dialog.root.text()).resolve()); game['cover']=self._store_cover(dialog.cover.text()); self.library.save(); self.refresh_library(); self.select_library_game(game['id'])
        except (OSError,ValueError) as exc: self.error(str(exc))

    def edit_library_game(self):
        game=self.current_library_game()
        if not game: return
        dialog=GameEditor(self,game)
        if dialog.exec()!=QDialog.DialogCode.Accepted: return
        try:
            game.update(name=dialog.name.text().strip(),root=str(Path(dialog.root.text()).resolve()),executable=dialog.exe.text(),cover=self._store_cover(dialog.cover.text())); self.library.save(); self.refresh_library()
        except (OSError,ValueError) as exc: self.error(str(exc))

    def remove_library_game(self):
        game=self.current_library_game()
        if game: self.library.remove(game['id']); self.selected_game_id=None; self.refresh_library(); self.navigate(4)

    def detect_library_games(self):
        def done(games):
            before=len(self.library.games)
            for game in games: self.library.add(game)
            self.refresh_library(); self.status.setText(f'{len(self.library.games)-before} game Steam ditambahkan.' if games else 'Instalasi game Steam tidak ditemukan. Anda dapat menambahkan EXE secara manual.')
        self.run_job(lambda progress:discover_steam(),done)

    def prepare_library_game(self):
        game=self.current_library_game()
        if game: self.folder.setText(game['root']); self.navigate(0); self.scan()

    def scan_library_support(self):
        game=self.current_library_game()
        if not game: return
        def done(report):
            profile=self.library.get_profile(game['id']); profile.update(support_level=report['support_level'],adapter_id=report.get('adapter_id',''),last_scan=datetime.now(timezone.utc).isoformat()); self.library.save_profile(game['id'],profile); self.refresh_game_detail(); self.status.setText('Pemindaian dukungan selesai.')
        self.run_job(lambda progress: scan_game_root(game['root']),done,False)

    def open_library_demo(self):
        self.navigate(0); self.open_demo()

    def open_library_folder(self):
        game=self.current_library_game()
        if game: QDesktopServices.openUrl(QUrl.fromLocalFile(game['root']))

    def play_library_game(self):
        game=self.current_library_game()
        if not game: return
        mode=self.play_mode.currentData()
        def launched(_):
            try:
                if game.get('steam_id'):
                    if not str(game['steam_id']).isdigit() or not QDesktopServices.openUrl(QUrl('steam://rungameid/'+game['steam_id'])): raise ValueError('Steam tidak dapat membuka game ini.')
                else: launch_executable(game)
                game['last_played']=datetime.now(timezone.utc).isoformat(); self.library.save(); self.refresh_library(); self.status.setText('Permintaan menjalankan '+game['name']+' dikirim. Mode: '+('terjemahan' if mode=='translated' else 'asli')+'.')
            except (OSError,ValueError) as exc: self.error(str(exc))
        def prepare(progress):
            validate_launch_target(game)
            set_play_mode(game,self.storage,mode)
        self.run_job(prepare,launched,False)

    def process_root_for_patch(self,folder):
        manifest=json.loads((Path(folder)/'manifest.json').read_text(encoding='utf-8'))
        root=Path(manifest['root']).resolve()
        candidates=[Path(g['root']).resolve() for g in self.library.games if root.is_relative_to(Path(g['root']).resolve())]
        return max(candidates,key=lambda p:len(p.parts)) if candidates else root
