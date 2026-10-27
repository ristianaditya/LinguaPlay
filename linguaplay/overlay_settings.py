"""Persisted subtitle appearance and a nonmodal settings window above the game."""
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import re
import sys
from datetime import datetime
from PySide6.QtCore import Qt, QRect, QPoint, Signal, QSize, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QShortcut, QKeySequence, QGuiApplication, QPalette, QColor, QPainter, QRadialGradient
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QFormLayout, QSpinBox,
    QSlider, QComboBox, QPushButton, QFontComboBox, QFrame, QHBoxLayout, QTabWidget, QWidget, QAbstractSpinBox)
from .icons import icon as make_icon, pixmap as icon_pixmap

def icon_label(name,color,size):
    result=QLabel(); result.setPixmap(icon_pixmap(name,color,size)); result.setFixedSize(size+2,size+2); return result


PANEL_STYLE='''
QDialog#overlayPanel { background: transparent; color: #eef1ee; font-family: "Segoe UI"; font-size: 13px; }
QDialog#overlayPanel QFrame#overlayShell { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(36,39,41,246),stop:1 rgba(24,26,28,246)); border: 1px solid rgba(255,255,255,0.11); border-radius: 22px; }
QDialog#overlayPanel QWidget { color: #eef1ee; background: transparent; }
QDialog#overlayPanel QLabel { border: none; padding: 0; background: transparent; }
QDialog#overlayPanel QLabel#panelBrand { font-size: 15px; font-weight: 700; }
QDialog#overlayPanel QLabel#panelEyebrow { color: #8d958f; font-size: 10px; font-weight: 800; letter-spacing: 1.4px; }
QDialog#overlayPanel QLabel#panelRowTitle { color: #e9ede9; font-size: 13px; }
QDialog#overlayPanel QLabel#panelHint { color: #98a09b; font-size: 12px; }
QDialog#overlayPanel QLabel#panelStatus { color: #d6fb51; font-size: 11px; font-weight: 700; background: rgba(214,251,81,0.10); border: 1px solid rgba(214,251,81,0.22); border-radius: 10px; padding: 3px 10px; }
QDialog#overlayPanel QLabel#keyBadge { color: #cfd6d1; background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.08); border-radius: 7px; padding: 3px 8px; font-size: 11px; font-weight: 600; }
QDialog#overlayPanel QLabel#valueBadge { color: #f2f5ef; background: rgba(255,255,255,0.08); border-radius: 8px; padding: 4px 0; font-size: 12px; font-weight: 700; }
QDialog#overlayPanel QFrame#panelGroup { background: rgba(255,255,255,0.045); border: 1px solid rgba(255,255,255,0.05); border-radius: 16px; }
QDialog#overlayPanel QComboBox, QDialog#overlayPanel QSpinBox { background: rgba(255,255,255,0.07); color: #f2f5ef; border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 5px 9px; min-height: 20px; }
QDialog#overlayPanel QComboBox:hover, QDialog#overlayPanel QSpinBox:hover { border-color: rgba(255,255,255,0.18); }
QDialog#overlayPanel QComboBox:focus, QDialog#overlayPanel QSpinBox:focus { border: 1px solid #d6fb51; }
QDialog#overlayPanel QComboBox QAbstractItemView { background: #1f2223; color: #f2f5ef; selection-background-color: rgba(214,251,81,0.2); selection-color: white; border: 1px solid rgba(255,255,255,0.1); outline: none; }
QDialog#overlayPanel QComboBox::drop-down { border: none; width: 22px; }
QDialog#overlayPanel QSlider { background: transparent; border: none; min-height: 30px; }
QDialog#overlayPanel QSlider::groove:horizontal { background: rgba(255,255,255,0.10); height: 6px; border-radius: 3px; }
QDialog#overlayPanel QSlider::sub-page:horizontal { background: #d6fb51; border-radius: 3px; }
QDialog#overlayPanel QSlider::handle:horizontal { background: #ffffff; border: none; width: 12px; height: 22px; margin: -8px 0; border-radius: 6px; }
QDialog#overlayPanel QSlider::handle:horizontal:hover { background: #f4ffd0; }
QDialog#overlayPanel QTabWidget::pane { border: none; padding-top: 12px; }
QDialog#overlayPanel QTabBar { qproperty-drawBase: 0; }
QDialog#overlayPanel QTabBar::tab { color: #a9b1ac; background: rgba(255,255,255,0.05); border: none; padding: 7px 18px; margin-right: 6px; border-radius: 14px; min-width: 70px; font-weight: 600; }
QDialog#overlayPanel QTabBar::tab:hover { background: rgba(255,255,255,0.10); color: #f2f5ef; }
QDialog#overlayPanel QTabBar::tab:selected { color: #151b07; background: #d6fb51; }
QDialog#overlayPanel QPushButton { color: #e9eee9; background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.09); border-radius: 16px; padding: 7px 14px; min-height: 20px; font-weight: 600; }
QDialog#overlayPanel QPushButton:hover { background: rgba(255,255,255,0.12); }
QDialog#overlayPanel QPushButton:focus { border: 1px solid #d6fb51; }
QDialog#overlayPanel QPushButton#panelClose { border: none; background: transparent; padding: 0; min-height: 28px; border-radius: 10px; }
QDialog#overlayPanel QPushButton#panelClose:hover { background: rgba(255,255,255,0.10); }
QDialog#overlayPanel QPushButton#panelDone { background: #d6fb51; color: #151b07; border: none; font-weight: 700; border-radius: 17px; padding: 9px 14px; }
QDialog#overlayPanel QPushButton#panelDone:hover { background: #e3ff7a; }
'''

class PanelDragHandle(QFrame):
    def __init__(self):
        super().__init__(); self.offset=None
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setToolTip('Seret untuk memindahkan panel. Alt + tombol panah juga tersedia.')

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self.offset=event.globalPosition().toPoint()-self.window().pos(); event.accept()
        else: super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if self.offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move_within_screen(event.globalPosition().toPoint()-self.offset); event.accept()
        else: super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        self.offset=None; super().mouseReleaseEvent(event)

@dataclass(frozen=True)
class OverlayAppearance:
    font_family: str = 'Segoe UI'
    font_size: int = 22
    text_color: str = '#ffffff'
    background_color: str = '#0c1726'
    background_opacity: int = 85
    width_percent: int = 78
    height: int = 150
    position_x: int = 50
    position_y: int = 65

    @classmethod
    def from_dict(cls,data):
        values=asdict(cls())
        for key in values:
            if key in data: values[key]=data[key]
        for key,minimum,maximum in [('font_size',14,64),('background_opacity',0,100),('width_percent',30,95),('height',100,360),('position_x',0,100),('position_y',0,100)]:
            value=values[key]
            if type(value) is not int: raise ValueError('Nilai tampilan harus berupa angka.')
            values[key]=max(minimum,min(maximum,value))
        if not isinstance(values['font_family'],str) or not values['font_family'].strip() or len(values['font_family'])>100:
            raise ValueError('Nama font tidak valid.')
        # A font family is inserted into a Qt style string, so keep it quoted safely.
        if any(char in values['font_family'] for char in ('"',"'",';','{','}','\n','\r')):
            raise ValueError('Nama font tidak valid.')
        for key in ('text_color','background_color'):
            if not isinstance(values[key],str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',values[key]):
                raise ValueError('Warna harus berupa kode hex enam digit.')
        return cls(**values)

def load_appearance(path):
    try:
        data=json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(data,dict): return OverlayAppearance()
        return OverlayAppearance.from_dict(data)
    except (OSError,ValueError,TypeError): return OverlayAppearance()

def save_appearance(path,appearance):
    from .patches import atomic_write
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    atomic_write(path,json.dumps(asdict(appearance),indent=2).encode())

def place_overlay(bounds,region,appearance):
    width=min(bounds.width()-32,max(240,round(bounds.width()*appearance.width_percent/100)))
    height=min(bounds.height()-32,appearance.height)
    x=bounds.left()+round((bounds.width()-width)*appearance.position_x/100)
    y=bounds.top()+round((bounds.height()-height)*appearance.position_y/100)
    desired=QRect(x,y,width,height)
    if region.isEmpty() or not desired.intersects(region): return desired
    candidates=[QRect(x,region.top()-height-12,width,height),
                QRect(x,region.bottom()+13,width,height),
                QRect(region.left()-width-12,y,width,height),
                QRect(region.right()+13,y,width,height)]
    candidates=[rect for rect in candidates if bounds.contains(rect) and not rect.intersects(region)]
    if not candidates: raise ValueError('Tidak cukup ruang di luar area OCR. Kecilkan area tangkapan atau ukuran overlay.')
    return min(candidates,key=lambda r:abs(r.x()-x)+abs(r.y()-y))

class OverlaySettingsPanel(QDialog):
    changed=Signal(object)

    def __init__(self,appearance,ocr_active=False,hotkey='Ctrl+Alt+O'):
        super().__init__(None,Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.setObjectName('overlayPanel'); self.setWindowTitle('LinguaPlay • Tampilan overlay'); self.setFixedWidth(384)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose,False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        palette=self.palette()
        for role in (QPalette.ColorRole.Window,QPalette.ColorRole.Button): palette.setColor(role,QColor('#1c1f20'))
        for role in (QPalette.ColorRole.WindowText,QPalette.ColorRole.Text,QPalette.ColorRole.ButtonText): palette.setColor(role,QColor('#eef1ee'))
        palette.setColor(QPalette.ColorRole.Base,QColor('#26292a')); palette.setColor(QPalette.ColorRole.Highlight,QColor('#414e30'))
        palette.setColor(QPalette.ColorRole.HighlightedText,QColor('#ffffff')); self.setPalette(palette)
        assets=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))/'assets'
        arrow_style=f"""
        QDialog#overlayPanel QComboBox::down-arrow {{ image: url("{(assets/'chevron-down.svg').as_posix()}"); width: 10px; height: 10px; }}
        QDialog#overlayPanel QSpinBox::up-arrow {{ image: url("{(assets/'control-plus.svg').as_posix()}"); width: 9px; height: 9px; }}
        QDialog#overlayPanel QSpinBox::down-arrow {{ image: url("{(assets/'control-minus.svg').as_posix()}"); width: 9px; height: 9px; }}
        QDialog#overlayPanel QSpinBox::up-button {{ background: rgba(214,251,81,0.14); border-left: 1px solid rgba(255,255,255,0.08); border-top-right-radius: 9px; width: 20px; }}
        QDialog#overlayPanel QSpinBox::down-button {{ background: rgba(214,251,81,0.14); border-left: 1px solid rgba(255,255,255,0.08); border-bottom-right-radius: 9px; width: 20px; }}
        """
        self.setStyleSheet(PANEL_STYLE+arrow_style)
        outer=QVBoxLayout(self); outer.setContentsMargins(0,0,0,0)
        shell=QFrame(); shell.setObjectName('overlayShell'); outer.addWidget(shell)
        layout=QVBoxLayout(shell); layout.setContentsMargins(18,16,18,18); layout.setSpacing(12)
        self.drag_handle=PanelDragHandle(); header=QHBoxLayout(self.drag_handle); header.setContentsMargins(0,0,0,0); header.setSpacing(10)
        mark=icon_label('sliders','#eef1ee',18)
        brand=QLabel('Tampilan overlay'); brand.setObjectName('panelBrand')
        badge=QLabel(hotkey); badge.setObjectName('keyBadge')
        for child in (mark,brand,badge): child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        header.addWidget(mark); header.addWidget(brand,1); header.addWidget(badge)
        self.close_button=QPushButton(); self.close_button.setObjectName('panelClose'); self.close_button.setFixedSize(28,28)
        self.close_button.setIcon(make_icon('close','#c9d0cc',16)); self.close_button.setIconSize(QSize(16,16)); self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.setAccessibleName('Tutup pengaturan overlay'); self.close_button.setToolTip('Tutup panel (Esc)'); self.close_button.setAutoDefault(False)
        self.close_button.clicked.connect(self.reject); header.addWidget(self.close_button); layout.addWidget(self.drag_handle)
        status_row=QHBoxLayout(); self.status_label=QLabel('●  OCR dijeda sementara' if ocr_active else '●  Pratinjau langsung'); self.status_label.setObjectName('panelStatus')
        status_row.addWidget(self.status_label); status_row.addStretch(); layout.addLayout(status_row)
        self.tabs=QTabWidget(); self.tabs.setDocumentMode(True); self.tabs.tabBar().setDrawBase(False); self.tabs.tabBar().setCursor(Qt.CursorShape.PointingHandCursor)
        text_page=QWidget(); position_page=QWidget()
        self.tabs.addTab(text_page,make_icon('type','#a9b1ac',14),'Subtitle'); self.tabs.addTab(position_page,make_icon('move-x','#a9b1ac',14),'Posisi')
        text_layout=QVBoxLayout(text_page); text_layout.setContentsMargins(0,0,0,0); text_layout.setSpacing(10)
        position_layout=QVBoxLayout(position_page); position_layout.setContentsMargins(0,0,0,0); position_layout.setSpacing(10)
        self.font_family=QFontComboBox(); self.font_family.setCurrentFont(QFont(appearance.font_family)); self.font_family.setMaximumWidth(176)
        self.font_size=QSpinBox(); self.font_size.setRange(14,64); self.font_size.setSuffix(' px'); self.font_size.setValue(appearance.font_size); self.font_size.setFixedWidth(108)
        self.text_color=QComboBox(); self.background_color=QComboBox()
        self.fill_colors(self.text_color,[('Putih','#ffffff'),('Kuning','#ffdd55'),('Biru muda','#82cfff'),('Hijau muda','#a9f5ba'),('Hitam','#000000')],appearance.text_color)
        self.fill_colors(self.background_color,[('Biru gelap','#0c1726'),('Hitam','#000000'),('Abu gelap','#303030'),('Putih','#ffffff')],appearance.background_color)
        for combo in (self.text_color,self.background_color): combo.setFixedWidth(140)
        self.background_opacity=self.slider(appearance.background_opacity)
        self.opacity_value=self.badge(f'{appearance.background_opacity}%')
        self.background_opacity.valueChanged.connect(lambda value:self.opacity_value.setText(f'{value}%'))
        text_layout.addWidget(self.group('Teks',[('type','Font',self.font_family),('height','Ukuran',self.font_size),('drop','Warna',self.text_color)]))
        text_layout.addWidget(self.group('Latar',[('drop','Warna',self.background_color),('contrast','Kepekatan',self.pair(self.opacity_value,self.background_opacity))]))
        self.width_percent=QSpinBox(); self.width_percent.setRange(30,95); self.width_percent.setSuffix(' %'); self.width_percent.setValue(appearance.width_percent); self.width_percent.setFixedWidth(108)
        self.height_control=QSpinBox(); self.height_control.setRange(100,360); self.height_control.setSuffix(' px'); self.height_control.setValue(appearance.height); self.height_control.setFixedWidth(108)
        self.position_x=self.slider(appearance.position_x); self.position_y=self.slider(appearance.position_y)
        self.x_value=self.badge(f'{appearance.position_x}'); self.y_value=self.badge(f'{appearance.position_y}')
        self.position_x.valueChanged.connect(lambda value:self.x_value.setText(str(value))); self.position_y.valueChanged.connect(lambda value:self.y_value.setText(str(value)))
        for spin in (self.font_size,self.width_percent,self.height_control): spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.PlusMinus)
        position_layout.addWidget(self.group('Ukuran kotak',[('width','Lebar layar',self.width_percent),('height','Tinggi',self.height_control)]))
        position_layout.addWidget(self.group('Letak',[('move-x','Horizontal',self.pair(self.x_value,self.position_x)),('move-y','Vertikal',self.pair(self.y_value,self.position_y))]))
        position_layout.addStretch()
        layout.addWidget(self.tabs)
        self.notice=QLabel('Perubahan tersimpan otomatis. Geser Vertikal ke kanan penuh untuk menaruh subtitle di dasar layar.'); self.notice.setObjectName('panelHint'); self.notice.setWordWrap(True); layout.addWidget(self.notice)
        self.done_button=QPushButton('Kembali ke game'); self.done_button.setObjectName('panelDone'); self.done_button.setAutoDefault(False); self.done_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.done_button.setIcon(make_icon('play','#151b07',14)); self.done_button.clicked.connect(self.accept); layout.addWidget(self.done_button)
        footer=QHBoxLayout(); footer.setSpacing(6)
        for key,text in (('Esc','Tutup'),('Alt+←↑→↓','Geser panel')):
            chip=QLabel(key); chip.setObjectName('keyBadge'); footer.addWidget(chip); hint=QLabel(text); hint.setObjectName('panelHint'); footer.addWidget(hint); footer.addSpacing(6)
        footer.addStretch(); layout.addLayout(footer)
        self.move_shortcuts=[]
        for key,dx,dy in [('Left',-16,0),('Right',16,0),('Up',0,-16),('Down',0,16)]:
            shortcut=QShortcut(QKeySequence('Alt+'+key),self)
            shortcut.activated.connect(lambda x=dx,y=dy:self.move_within_screen(self.pos()+QPoint(x,y)))
            self.move_shortcuts.append(shortcut)
        for control in [self.font_size,self.width_percent,self.height_control,self.background_opacity,self.position_x,self.position_y]: control.valueChanged.connect(self.emit_change)
        self.font_family.currentFontChanged.connect(self.emit_change)
        self.text_color.currentIndexChanged.connect(self.emit_change); self.background_color.currentIndexChanged.connect(self.emit_change)
        self.appear=QPropertyAnimation(self,b'windowOpacity',self); self.appear.setDuration(220); self.appear.setEasingCurve(QEasingCurve.Type.OutCubic)

    def showEvent(self,event):
        super().showEvent(event)
        self.appear.stop(); self.setWindowOpacity(0.0); self.appear.setStartValue(0.0); self.appear.setEndValue(1.0); self.appear.start()

    @staticmethod
    def badge(text):
        result=QLabel(text); result.setObjectName('valueBadge'); result.setFixedWidth(44); result.setAlignment(Qt.AlignmentFlag.AlignCenter); return result

    @staticmethod
    def pair(badge,slider):
        widget=QWidget(); line=QHBoxLayout(widget); line.setContentsMargins(0,0,0,0); line.setSpacing(8)
        slider.setFixedWidth(120); line.addWidget(badge); line.addWidget(slider); return widget

    @staticmethod
    def group(title,rows):
        frame=QFrame(); frame.setObjectName('panelGroup'); layout=QVBoxLayout(frame); layout.setContentsMargins(14,12,14,12); layout.setSpacing(8)
        heading=QLabel(title.upper()); heading.setObjectName('panelEyebrow'); layout.addWidget(heading)
        for icon_name,text,control in rows:
            line=QHBoxLayout(); line.setSpacing(10); line.addWidget(icon_label(icon_name,'#d6fb51',16))
            caption=QLabel(text); caption.setObjectName('panelRowTitle'); line.addWidget(caption,1); line.addWidget(control); layout.addLayout(line)
        return frame


    def move_within_screen(self,position):
        screen=QGuiApplication.screenAt(position+self.rect().center()) or self.screen()
        bounds=screen.availableGeometry().adjusted(8,8,-8,-8)
        x=max(bounds.left(),min(position.x(),bounds.right()-self.width()+1))
        y=max(bounds.top(),min(position.y(),bounds.bottom()-self.height()+1))
        self.move(x,y)

    @staticmethod
    def slider(value):
        widget=QSlider(Qt.Orientation.Horizontal); widget.setRange(0,100); widget.setValue(value)
        widget.setCursor(Qt.CursorShape.PointingHandCursor); widget.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        return widget

    @staticmethod
    def fill_colors(combo,items,current):
        for name,color in items: combo.addItem(name,color)
        index=combo.findData(current)
        if index<0: combo.addItem(current,current); index=combo.count()-1
        combo.setCurrentIndex(index)

    def emit_change(self,*args):
        try:
            appearance=OverlayAppearance.from_dict({
                'font_family':self.font_family.currentFont().family(),'font_size':self.font_size.value(),
                'text_color':self.text_color.currentData(),'background_color':self.background_color.currentData(),
                'background_opacity':self.background_opacity.value(),'width_percent':self.width_percent.value(),
                'height':self.height_control.value(),'position_x':self.position_x.value(),'position_y':self.position_y.value()})
            self.changed.emit(appearance)
        except ValueError as exc: self.notice.setText(str(exc))


class OverlayHub(QWidget):
    """Full-screen in-game layer (like the Steam/Discord overlay): dims the game, shows a top bar,
    quick actions and the last subtitle. Clicking the backdrop returns to the game."""
    dismissed=Signal()

    def __init__(self,screen,actions=(),subtitle='',ocr_active=False,hotkey='Ctrl+Alt+O'):
        super().__init__(None,Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setObjectName('overlayHub'); self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground); self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setGeometry(screen.geometry()); self.setStyleSheet(HUB_STYLE)
        layout=QVBoxLayout(self); layout.setContentsMargins(28,22,28,28); layout.setSpacing(0)
        bar=QFrame(); bar.setObjectName('hubBar'); top=QHBoxLayout(bar); top.setContentsMargins(16,10,16,10); top.setSpacing(12)
        logo=QLabel('LP'); logo.setObjectName('hubLogo'); logo.setFixedSize(30,30); logo.setAlignment(Qt.AlignmentFlag.AlignCenter); top.addWidget(logo)
        name=QLabel('LinguaPlay'); name.setObjectName('hubTitle'); top.addWidget(name)
        state=QLabel('●  OCR dijeda' if ocr_active else '●  Overlay'); state.setObjectName('hubChip'); top.addWidget(state); top.addStretch()
        self.clock=QLabel(); self.clock.setObjectName('hubClock'); top.addWidget(self.clock)
        key=QLabel(hotkey); key.setObjectName('hubKey'); top.addWidget(key); back=QLabel('kembali ke game'); back.setObjectName('hubHint'); top.addWidget(back)
        layout.addWidget(bar); layout.addSpacing(12)
        # Actions and the last line sit at the top: the bottom of the screen belongs to the subtitles.
        pills=QHBoxLayout(); pills.setSpacing(10)
        for icon_name,text,callback in actions:
            pill=QPushButton(text); pill.setObjectName('hubPill'); pill.setIcon(make_icon(icon_name,'#eef1ee',16)); pill.setIconSize(QSize(16,16))
            pill.setCursor(Qt.CursorShape.PointingHandCursor); pill.clicked.connect(callback); pills.addWidget(pill)
        pills.addStretch(); layout.addLayout(pills)
        if subtitle:
            card=QFrame(); card.setObjectName('hubCard'); inside=QVBoxLayout(card); inside.setContentsMargins(16,12,16,14); inside.setSpacing(6)
            heading=QHBoxLayout(); heading.addWidget(icon_label('translate','#d6fb51',16)); caption=QLabel('SUBTITLE TERAKHIR'); caption.setObjectName('hubEyebrow'); heading.addWidget(caption,1); inside.addLayout(heading)
            text=QLabel(subtitle); text.setObjectName('hubSubtitle'); text.setWordWrap(True); inside.addWidget(text); card.setMinimumWidth(380); card.setMaximumWidth(520)
            layout.addSpacing(12); layout.addWidget(card,0,Qt.AlignmentFlag.AlignLeft)
        layout.addStretch()
        self.timer=QTimer(self); self.timer.timeout.connect(self.tick); self.timer.start(1000); self.tick()
        self.fade=QPropertyAnimation(self,b'windowOpacity',self); self.fade.setDuration(240); self.fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.closing=False

    def tick(self):
        self.clock.setText(datetime.now().strftime('%H:%M'))

    def paintEvent(self,event):
        painter=QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(),QColor(4,6,6,150))
        glow=QRadialGradient(self.width()*.5,self.height()*.45,max(self.width(),self.height())*.75)
        glow.setColorAt(0,QColor(0,0,0,0)); glow.setColorAt(1,QColor(0,0,0,120)); painter.fillRect(self.rect(),glow)

    def present(self):
        self.setWindowOpacity(0.0); self.show(); self.fade.stop(); self.fade.setStartValue(0.0); self.fade.setEndValue(1.0); self.fade.start()

    def dismiss(self):
        if self.closing: return
        self.closing=True; self.timer.stop(); self.fade.stop(); self.fade.setStartValue(self.windowOpacity()); self.fade.setEndValue(0.0)
        self.fade.finished.connect(self.close); self.fade.start()

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton: self.dismissed.emit()

    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape: self.dismissed.emit()
        else: super().keyPressEvent(event)

HUB_STYLE="""
QWidget#overlayHub { font-family: "Segoe UI"; color: #eef1ee; }
QFrame#hubBar { background: rgba(22,24,26,235); border: 1px solid rgba(255,255,255,0.09); border-radius: 18px; }
QLabel#hubLogo { background: #d6fb51; color: #151b07; border-radius: 9px; font-weight: 800; font-size: 12px; }
QLabel#hubTitle { font-size: 15px; font-weight: 700; color: #f6f8f4; }
QLabel#hubChip { color: #d6fb51; background: rgba(214,251,81,0.10); border: 1px solid rgba(214,251,81,0.22); border-radius: 10px; padding: 3px 10px; font-size: 11px; font-weight: 700; }
QLabel#hubClock { color: #f2f5ef; font-size: 15px; font-weight: 700; padding-right: 8px; }
QLabel#hubKey { color: #cfd6d1; background: rgba(255,255,255,0.08); border-radius: 7px; padding: 3px 8px; font-size: 11px; font-weight: 700; }
QLabel#hubHint { color: #98a09b; font-size: 12px; }
QFrame#hubCard { background: rgba(26,29,30,232); border: 1px solid rgba(255,255,255,0.09); border-radius: 18px; }
QLabel#hubEyebrow { color: #8d958f; font-size: 10px; font-weight: 800; letter-spacing: 1.4px; }
QLabel#hubSubtitle { color: #f2f5ef; font-size: 14px; }
QPushButton#hubPill { color: #eef1ee; background: rgba(40,43,45,235); border: 1px solid rgba(255,255,255,0.12); border-radius: 22px; padding: 11px 20px; font-size: 14px; font-weight: 600; }
QPushButton#hubPill:hover { background: rgba(58,62,64,245); border-color: rgba(214,251,81,0.5); }
"""
