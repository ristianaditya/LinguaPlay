from pathlib import Path
import shutil
import hashlib
import json
import sys
from datetime import datetime,timezone
from PySide6.QtCore import Qt,QSize,QRectF,QUrl,QFileInfo
from PySide6.QtGui import QPixmap,QPainter,QColor,QLinearGradient,QRadialGradient,QFont,QIcon,QDesktopServices,QPainterPath,QFontMetrics
from PySide6.QtWidgets import (QWidget,QFrame,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QLineEdit,
    QComboBox,QListWidget,QListWidgetItem,QAbstractItemView,QFileDialog,QFileIconProvider,
    QDialog,QDialogButtonBox,QFormLayout,QPushButton)
from .desktop_widgets import label,button,icon_label,SegmentedToggle,ACCENT
from .icons import icon as make_icon, pixmap as icon_pixmap
from .launchers import discover_other,discover_folder,SOURCES,LAUNCH_SCHEMES
from .library import GameLibrary,discover_steam,STEAM_TOOLS,game_patch_state,patches_for,set_play_mode,launch_executable,validate_launch_target
from .adapters import scan_game_root
from .adapter_packages import install_package

STATE_LABELS={'installed':'Terjemahan terpasang','ready':'Patch siap dimainkan','original':'Versi asli','recovery':'Perlu pemulihan'}


def cover_pixmap(game,size):
    result=QPixmap(size); result.fill(QColor('#1d2122'))
    painter=QPainter(result); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    image=QPixmap(game.get('cover','')) if game.get('cover') else QPixmap()
    if not image.isNull():
        image=image.scaled(size,Qt.AspectRatioMode.KeepAspectRatioByExpanding,Qt.TransformationMode.SmoothTransformation)
        painter.drawPixmap((size.width()-image.width())//2,(size.height()-image.height())//2,image)
    else:
        gradient=QLinearGradient(0,0,size.width(),size.height()); gradient.setColorAt(0,QColor('#2f3d22')); gradient.setColorAt(.55,QColor('#1a2020')); gradient.setColorAt(1,QColor('#111415'))
        painter.fillRect(result.rect(),gradient)
        glow=QRadialGradient(size.width()*.5,size.height()*.42,size.width()*.55); glow.setColorAt(0,QColor(214,251,81,70)); glow.setColorAt(1,QColor(214,251,81,0))
        painter.fillRect(result.rect(),glow)
        # Without store artwork, the game's own EXE icon is the most recognisable picture available.
        exe=game.get('executable','')
        icon=QFileIconProvider().icon(QFileInfo(exe)).pixmap(QSize(128,128)) if exe and Path(exe).is_file() else QPixmap()
        if not icon.isNull() and icon.width()>=48:
            side=min(size.width()//2,icon.width()*2,max(64,size.height()//3)); icon.setDevicePixelRatio(1); icon=icon.scaled(side,side,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap((size.width()-icon.width())//2,int(size.height()*.42-icon.height()/2),icon)
        else:
            painter.setPen(QColor('#d6fb51')); font=QFont('Segoe UI'); font.setPixelSize(max(26,size.width()//5)); font.setWeight(QFont.Weight.Black); painter.setFont(font)
            painter.drawText(QRectF(0,0,size.width(),size.height()*.84),Qt.AlignmentFlag.AlignCenter,''.join(w[0] for w in game['name'].split()[:2]).upper())
    painter.end(); return result

def game_tile(game,state):
    """Poster card: artwork fills the tile, a gradient keeps the title and status chip readable."""
    width,height=206,286
    tile=QPixmap(width,height); tile.fill(Qt.GlobalColor.transparent); painter=QPainter(tile); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip=QPainterPath(); clip.addRoundedRect(QRectF(0,0,width,height),14,14); painter.setClipPath(clip)
    painter.drawPixmap(0,0,cover_pixmap(game,QSize(width,height)))
    shade=QLinearGradient(0,height*.45,0,height); shade.setColorAt(0,QColor(8,10,10,0)); shade.setColorAt(1,QColor(8,10,10,235)); painter.fillRect(0,0,width,height,shade)
    font=QFont('Segoe UI'); font.setPixelSize(14); font.setWeight(QFont.Weight.Bold); painter.setFont(font); painter.setPen(QColor('#f7f9f5'))
    painter.drawText(14,height-42,QFontMetrics(font).elidedText(game['name'],Qt.TextElideMode.ElideRight,width-28))
    font.setPixelSize(10); font.setWeight(QFont.Weight.Bold); painter.setFont(font); text=STATE_LABELS[state].upper(); metrics=QFontMetrics(font)
    chip=QRectF(14,height-32,metrics.horizontalAdvance(text)+18,20); active=state!='original'
    painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QColor(214,251,81,46) if active else QColor(255,255,255,30)); painter.drawRoundedRect(chip,10,10)
    painter.setPen(QColor('#e3ff86') if active else QColor('#c9cfcb')); painter.drawText(chip,Qt.AlignmentFlag.AlignCenter,text)
    painter.setClipping(False); painter.setPen(QColor(255,255,255,24)); painter.setBrush(Qt.BrushStyle.NoBrush); painter.drawRoundedRect(QRectF(.5,.5,width-1,height-1),14,14)
    painter.end(); return tile


class GameArtwork(QFrame):
    def __init__(self):
        super().__init__(); self.game=None; self.setMinimumHeight(232); self.setObjectName('gameArtwork')
    def paintEvent(self,event):
        painter=QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip=QPainterPath(); clip.addRoundedRect(QRectF(self.rect()),20,20); painter.setClipPath(clip)
        base=QLinearGradient(0,0,self.width(),self.height()); base.setColorAt(0,QColor('#26321a')); base.setColorAt(1,QColor('#121516')); painter.fillRect(self.rect(),base)
        if self.game and (self.game.get('hero') or self.game.get('cover')):
            banner=dict(self.game,cover=self.game.get('hero') or self.game.get('cover'))
            painter.drawPixmap(self.rect(),cover_pixmap(banner,self.size()))
        shade=QLinearGradient(0,0,self.width(),0); shade.setColorAt(0,QColor(10,12,12,245)); shade.setColorAt(.5,QColor(10,12,12,170)); shade.setColorAt(1,QColor(10,12,12,20))
        painter.fillRect(self.rect(),shade)
        bottom=QLinearGradient(0,self.height()*.5,0,self.height()); bottom.setColorAt(0,QColor(10,12,12,0)); bottom.setColorAt(1,QColor(10,12,12,200)); painter.fillRect(self.rect(),bottom)
        painter.setClipping(False); painter.setPen(QColor(255,255,255,22)); painter.drawRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),20,20); painter.end()


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
        intro=QWidget(); hero=QHBoxLayout(intro); hero.setContentsMargins(0,4,0,4); hero.setSpacing(10)
        title=QVBoxLayout(); title.setSpacing(4); title.addWidget(label('Library game','libraryHeading')); title.addWidget(label('Pilih game, atur terjemahan, lalu mainkan.','muted')); hero.addLayout(title,1)
        detect=button('Deteksi game',self.detect_library_games,icon='radar'); detect.setToolTip('Steam, Epic Games, GOG, Ubisoft Connect, EA app dan folder Games di setiap drive'); hero.addWidget(detect,0,Qt.AlignmentFlag.AlignBottom)
        hero.addWidget(button('Pindai folder',self.scan_game_folder,icon='folder'),0,Qt.AlignmentFlag.AlignBottom); hero.addWidget(button('Tambah game',self.add_library_game,kind='pill',icon='plus'),0,Qt.AlignmentFlag.AlignBottom); layout.addWidget(intro)
        heading=QHBoxLayout(); heading.setSpacing(10); heading.addWidget(label('Koleksi Anda','sectionTitle')); self.library_count=label('0 game','formatTag'); self.library_count.setWordWrap(False); heading.addWidget(self.library_count); heading.addStretch()
        self.library_search=QLineEdit(); self.library_search.setPlaceholderText('Cari game di library'); self.library_search.setMaximumWidth(260); self.library_search.textChanged.connect(self.refresh_library)
        self.library_search.addAction(make_icon('search','#8a928d',16),QLineEdit.ActionPosition.LeadingPosition); self.library_search.setClearButtonEnabled(True); heading.addWidget(self.library_search)
        self.library_filter=QComboBox(); self.library_filter.addItems(['Semua game','Dengan patch','Tanpa patch']); self.library_filter.currentIndexChanged.connect(self.refresh_library); heading.addWidget(self.library_filter); layout.addLayout(heading)
        self.game_grid=QListWidget(); self.game_grid.setObjectName('gameGrid'); self.game_grid.setViewMode(QListWidget.ViewMode.IconMode); self.game_grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.game_grid.setMovement(QListWidget.Movement.Static); self.game_grid.setIconSize(QSize(206,286)); self.game_grid.setGridSize(QSize(232,314)); self.game_grid.setSpacing(2); self.game_grid.setWordWrap(True)
        self.game_grid.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection); self.game_grid.setCursor(Qt.CursorShape.PointingHandCursor); self.game_grid.setMouseTracking(True)
        self.game_grid.itemClicked.connect(lambda item:self.select_library_game(item.data(Qt.ItemDataRole.UserRole))); self.game_grid.itemActivated.connect(lambda item:self.select_library_game(item.data(Qt.ItemDataRole.UserRole)))
        self.library_empty=QFrame(); self.library_empty.setObjectName('libraryEmpty'); empty=QVBoxLayout(self.library_empty); empty.setContentsMargins(0,8,0,8); empty.setSpacing(18)
        welcome=QHBoxLayout(); welcome.setSpacing(18); glow=QLabel(); glow.setObjectName('heroIcon'); glow.setFixedSize(96,96); glow.setAlignment(Qt.AlignmentFlag.AlignCenter); glow.setPixmap(icon_pixmap('gamepad',ACCENT,44)); welcome.addWidget(glow)
        words=QVBoxLayout(); words.setSpacing(6); words.addStretch(); words.addWidget(label('Library Anda dimulai di sini.','emptyTitle')); self.library_empty_text=label('Tambahkan EXE game atau deteksi instalasi Steam.\nGame bisa dimainkan dengan versi asli maupun terjemahan.','muted'); words.addWidget(self.library_empty_text); words.addStretch()
        welcome.addLayout(words,1); empty.addLayout(welcome)
        empty.addWidget(label('MULAI DALAM 3 LANGKAH','eyebrow'))
        steps=QHBoxLayout(); steps.setSpacing(14)
        for number,heading_text,detail,action in [('1','Tambah game','Pilih EXE game atau deteksi dari Steam.',button('Tambah game',self.add_library_game,kind='pill',icon='plus')),
                                                 ('2','Siapkan terjemahan','Pindai subtitle lalu terjemahkan offline.',button('Pindai subtitle',self.prepare_library_game,icon='scan')),
                                                 ('3','Main dengan subtitle','Tekan Play atau pakai overlay OCR.',button('Overlay OCR',lambda:self.navigate(1),icon='scan'))]:
            step=QFrame(); step.setObjectName('stepCard'); inside=QVBoxLayout(step); inside.setContentsMargins(20,18,20,18); inside.setSpacing(8)
            top=QHBoxLayout(); badge=label(number,'stepNumber'); badge.setFixedSize(26,26); badge.setAlignment(Qt.AlignmentFlag.AlignCenter); top.addWidget(badge); top.addWidget(label(heading_text,'stepTitle'),1); inside.addLayout(top)
            inside.addWidget(label(detail,'small')); inside.addStretch(); inside.addWidget(action,0,Qt.AlignmentFlag.AlignLeft); steps.addWidget(step,1)
        empty.addLayout(steps); empty.addStretch()
        layout.addWidget(self.library_empty,1); layout.addWidget(self.game_grid,1)
        foot=QHBoxLayout(); foot.addWidget(icon_label('info','#7d8681',15)); foot.addWidget(label('Patch mengganti file subtitle yang didukung. Gunakan overlay OCR untuk format game yang belum dikenali.','small'),1); layout.addLayout(foot)
        self.build_game_detail(); self.refresh_library()
        if self.library.load_warning: self.status.setText(self.library.load_warning)

    def build_game_detail(self):
        page=QWidget(); layout=QVBoxLayout(page); layout.setContentsMargins(0,0,0,0); layout.setSpacing(18); self.pages.addWidget(page)
        self.detail_hero=GameArtwork(); hero=QVBoxLayout(self.detail_hero); hero.setContentsMargins(30,26,30,26); hero.setSpacing(8)
        chips=QHBoxLayout(); chips.setSpacing(8); self.detail_platform=label('PC GAME','platformChip'); self.detail_platform.setWordWrap(False); chips.addWidget(self.detail_platform)
        self.detail_status=label('Versi asli','gameState'); self.detail_status.setWordWrap(False); chips.addWidget(self.detail_status); chips.addStretch(); hero.addLayout(chips)
        self.detail_title=label('Pilih game','gameHeading'); hero.addWidget(self.detail_title); hero.addStretch()
        controls=QHBoxLayout(); controls.setSpacing(12)
        self.play_mode=QComboBox(); self.play_mode.addItem('Mainkan versi asli','original'); self.play_mode.addItem('Mainkan dengan terjemahan','translated'); self.play_mode.hide()
        self.play_toggle=SegmentedToggle(self.play_mode,['Asli','Terjemahan']); self.play_toggle.setMinimumWidth(240); controls.addWidget(self.play_toggle)
        self.play_button=button('Play',self.play_library_game,True,icon='play'); self.play_button.setMinimumWidth(140); self.play_button.setMinimumHeight(42)
        controls.addWidget(self.play_button); controls.addStretch(); controls.addWidget(button('Atur game',self.edit_library_game,icon='edit')); hero.addLayout(controls); layout.addWidget(self.detail_hero)
        columns=QHBoxLayout(); columns.setSpacing(18); main=QVBoxLayout(); main.setSpacing(14)
        self.detail_patch_text=label('Belum ada patch terjemahan untuk game ini.','muted')
        self.detail_compat=label('Dukungan belum dipindai.','small')
        main.addWidget(self.control_group('Subtitle','Terjemahan subtitle','translate',[self.detail_patch_text,self.detail_compat],[('Siapkan terjemahan',self.prepare_library_game,'zap',True),('Scan dukungan',self.scan_library_support,'search',False),('Analisis mendalam',self.analyze_library_game,'sparkles',False),('Lihat cadangan',lambda:self.navigate(2),'history',False)]))
        main.addWidget(self.control_group('Overlay','Overlay saat bermain','layers',[label('Baca subtitle di layar dan tampilkan terjemahan di atas game, seperti overlay Steam atau Discord.','muted')],[('Buka overlay OCR',lambda:self.navigate(1),'scan',False),('Atur tampilan',self.toggle_overlay_settings,'sliders',False)]))
        self.detail_play_note=label('Pilihan mode diterapkan saat Play. Tutup game sebelum memasang atau memulihkan patch.','small'); main.addWidget(self.detail_play_note)
        main.addStretch(); columns.addLayout(main,1)
        info=QFrame(); info.setObjectName('detailInfo'); inside=QVBoxLayout(info); inside.setContentsMargins(20,20,20,20); inside.setSpacing(12); info.setFixedWidth(280)
        inside.addWidget(label('INSTALASI','eyebrow')); place=QHBoxLayout(); place.setSpacing(10); place.addWidget(icon_label('folder',ACCENT,17),0,Qt.AlignmentFlag.AlignTop)
        self.detail_location=label('','small'); self.detail_location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); place.addWidget(self.detail_location,1); inside.addLayout(place)
        inside.addWidget(button('Buka folder game',self.open_library_folder,icon='folder')); inside.addStretch()
        inside.addWidget(button('Impor Support Pack',self.import_support_pack,icon='download'))
        inside.addWidget(label('PINTASAN','eyebrow')); key=QHBoxLayout(); badge=self.hotkey_badge('overlay'); key.addWidget(badge); key.addWidget(label('Overlay dalam game','small'),1); inside.addLayout(key)
        columns.addWidget(info); layout.addLayout(columns,1)
        remove=QHBoxLayout(); remove.addWidget(button('Hapus dari library',self.remove_library_game,icon='trash')); remove.addWidget(label('File game dan cadangan tetap tersimpan.','small'),1); layout.addLayout(remove)

    def control_group(self,eyebrow,title,icon_name,descriptions,actions):
        frame=QFrame(); frame.setObjectName('controlGroup'); layout=QVBoxLayout(frame); layout.setContentsMargins(20,18,20,18); layout.setSpacing(10)
        layout.addWidget(label(eyebrow.upper(),'eyebrow'))
        head=QHBoxLayout(); head.setSpacing(10); head.addWidget(icon_label(icon_name,ACCENT,18)); head.addWidget(label(title,'sectionTitle'),1); layout.addLayout(head)
        for description in descriptions: layout.addWidget(description)
        line=QHBoxLayout(); line.setSpacing(8)
        for text,callback,icon_name,primary in actions: line.addWidget(button(text,callback,primary,icon=icon_name))
        line.addStretch(); layout.addLayout(line); return frame

    def refresh_library(self,*args):
        if not hasattr(self,'game_grid'): return
        self.rail_games.clear(); self.game_grid.clear(); query=self.library_search.text().strip().casefold(); filter_index=self.library_filter.currentIndex(); visible=0
        for game in sorted(self.library.games,key=lambda g:g['name'].casefold()):
            rail=QListWidgetItem(make_icon('gamepad','#8a928d',16),game['name']); rail.setData(Qt.ItemDataRole.UserRole,game['id']); self.rail_games.addItem(rail)
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
        state=game_patch_state(game,self.storage); self.detail_hero.game=game; self.detail_hero.update(); self.detail_title.setText(game['name']); self.detail_platform.setText('STEAM' if game.get('steam_id') else SOURCES.get(game.get('source',''),'PC • GAME LOKAL'))
        self.detail_status.setText(STATE_LABELS[state]); self.detail_location.setText(game['root'].replace('\\',' / '))
        self.detail_patch_text.setText({'original':'Belum ada patch. Siapkan terjemahan untuk subtitle yang didukung, atau mainkan versi asli.','ready':'Patch tersimpan dan siap digunakan. Pilih terjemahan lalu tekan Play untuk memasangnya.','installed':'Terjemahan aktif. Pilih versi asli lalu tekan Play untuk memulihkan subtitle asli.','recovery':'Pemasangan sebelumnya belum selesai. Buka Cadangan dan pulihkan sebelum bermain.'}[state])
        profile=self.library.get_profile(game['id'])
        level={'patch':'Dukungan patch tersedia.','ocr':'Teks game belum bisa dipatch — gunakan Overlay OCR.','unsupported':'Teks game belum ditemukan.','unknown':'Dukungan belum dipindai. Tekan Scan dukungan.'}.get(profile.get('support_level'),'Dukungan belum dipindai.')
        engine=(f"Mesin: {profile['engine_name']}. " if profile.get('engine_name') else '')
        self.detail_compat.setText(engine+(profile.get('engine_note') or level))
        self.play_button.setEnabled(state!='recovery'); self.play_mode.model().item(1).setEnabled(state not in ('original','recovery')); self.play_toggle.update()

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
        if game: self.library.remove(game['id']); self.selected_game_id=None; self.refresh_library(); self.nav_history=[i for i in self.nav_history if i!=5]; self.navigate(4,record=False)

    def merge_discovered(self,games,label_text):
        added=artwork=0
        roots={str(Path(g['root']).resolve()).casefold():g for g in self.library.games}
        for game in games:
            # A game already in the library under another source (e.g. added by EXE) is not duplicated.
            existing=roots.get(str(Path(game['root']).resolve()).casefold())
            if existing is None or existing['id']==game['id']: existing=self.library.add(game)
            if existing is game: added+=1; roots[str(Path(game['root']).resolve()).casefold()]=game; continue
            for key in ('cover','hero'):
                if game.get(key) and (not existing.get(key) or not Path(existing[key]).is_file()):
                    existing[key]=game[key]; artwork+=key=='cover'
        self.library.games=[g for g in self.library.games if g.get('steam_id') not in STEAM_TOOLS]
        self.library.save(); self.refresh_library()
        where=f' {label_text}' if label_text else ''
        if not games: self.status.setText(f'Tidak ada game{where} yang ditemukan. Anda dapat menambahkan EXE secara manual.')
        else: self.status.setText(f'{added} game baru{where} ditambahkan'+(f', cover {artwork} game diperbarui.' if artwork else '.'))

    def scan_game_folder(self):
        folder=QFileDialog.getExistingDirectory(self,'Pilih folder yang berisi game (mis. F:\\Games)')
        if folder: self.run_job(lambda progress:discover_folder(folder),lambda games:self.merge_discovered(games,'dari folder'))

    def detect_library_games(self):
        def find(progress):
            progress('Mencari game Steam…'); games=discover_steam()
            progress('Mencari game Epic, GOG, Ubisoft, EA dan folder Games…'); games+=discover_other()
            return games
        self.run_job(find,lambda games:self.merge_discovered(games,''))

    def prepare_library_game(self):
        game=self.current_library_game()
        if not game: return
        profile=self.library.get_profile(game['id'])
        if profile.get('anticheat'):
            self.status.setText(profile.get('engine_note') or 'Game ini dilindungi anti-cheat; gunakan Overlay OCR.'); self.navigate(1); return
        self.folder.setText(game['root']); self.navigate(0); self.scan()

    def scan_library_support(self):
        game=self.current_library_game()
        if not game: return
        def done(report):
            profile=self.library.get_profile(game['id']); profile.update(support_level=report['support_level'],adapter_id=report.get('adapter_id',''),last_scan=datetime.now(timezone.utc).isoformat(),
                           engine_name=report.get('engine_name',''),anticheat=report.get('anticheat',''),engine_note=report.get('engine_note','')); self.library.save_profile(game['id'],profile); self.refresh_game_detail(); self.status.setText('Pemindaian dukungan selesai.')
        self.run_job(lambda progress: scan_game_root(game['root']),done,False)

    def analyze_library_game(self):
        game=self.current_library_game()
        if game: self.run_deep_analysis(game['root'],game['name'])

    def open_library_folder(self):
        game=self.current_library_game()
        if game: QDesktopServices.openUrl(QUrl.fromLocalFile(game['root']))

    def import_support_pack(self):
        folder=QFileDialog.getExistingDirectory(self,'Pilih folder Support Pack')
        if not folder: return
        try:
            target=install_package(folder,self.data/'support-packs')
            self.status.setText(f'Support Pack {target.name} berhasil diimpor dan divalidasi.')
        except (OSError,ValueError) as exc:
            self.error(str(exc))

    def play_library_game(self):
        game=self.current_library_game()
        if not game: return
        mode=self.play_mode.currentData()
        def launched(_):
            try:
                if game.get('steam_id'):
                    if not str(game['steam_id']).isdigit() or not QDesktopServices.openUrl(QUrl('steam://rungameid/'+game['steam_id'])): raise ValueError('Steam tidak dapat membuka game ini.')
                elif game.get('launch_uri','').startswith(LAUNCH_SCHEMES) and not game.get('executable'):
                    if not QDesktopServices.openUrl(QUrl(game['launch_uri'])): raise ValueError('Launcher game tidak dapat dibuka.')
                elif game.get('launch_uri','').startswith(LAUNCH_SCHEMES) and game.get('source') in ('epic','ubisoft'):
                    # These stores expect their launcher to start the game (sign-in, DRM).
                    if not QDesktopServices.openUrl(QUrl(game['launch_uri'])): launch_executable(game)
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
