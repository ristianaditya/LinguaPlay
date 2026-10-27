"""Persisted subtitle appearance and a nonmodal settings window above the game."""
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import re
import sys
from PySide6.QtCore import Qt, QRect, QPoint, Signal
from PySide6.QtGui import QFont, QShortcut, QKeySequence, QGuiApplication, QPalette, QColor
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QFormLayout, QSpinBox,
    QSlider, QComboBox, QPushButton, QFontComboBox, QFrame, QHBoxLayout, QTabWidget, QWidget, QAbstractSpinBox)

PANEL_STYLE='''
QDialog#overlayPanel { background: transparent; color: #e6eeec; font-family: "Segoe UI"; font-size: 13px; }
QDialog#overlayPanel QFrame#overlayShell { background: #17191a; border: 1px solid #373c3c; border-radius: 12px; }
QDialog#overlayPanel QWidget { color: #e6eeec; background: transparent; }
QDialog#overlayPanel QLabel { border: none; padding: 0; background: transparent; }
QDialog#overlayPanel QLabel#panelBrand { font-size: 16px; font-weight: 700; }
QDialog#overlayPanel QLabel#brandMark { background: #d6fb51; color: #1b230b; border-radius: 6px; font-size: 12px; font-weight: 700; }
QDialog#overlayPanel QLabel#panelHint { color: #a9b1ab; font-size: 12px; }
QDialog#overlayPanel QLabel#panelStatus { color: #d6eb9d; font-size: 12px; }
QDialog#overlayPanel QLabel#keyBadge { color: #bfd3ce; background: #2b302c; border-radius: 4px; padding: 4px 6px; font-size: 11px; }
QDialog#overlayPanel QComboBox, QDialog#overlayPanel QSpinBox { background: #252a28; color: #eff8f5; border: 1px solid #48514a; border-radius: 5px; padding: 5px 8px; min-height: 20px; }
QDialog#overlayPanel QComboBox:focus, QDialog#overlayPanel QSpinBox:focus { border: 1px solid #d6fb51; }
QDialog#overlayPanel QComboBox QAbstractItemView { background: #252a28; color: #eff8f5; selection-background-color: #414e30; selection-color: white; border: 1px solid #5d6b52; }
QDialog#overlayPanel QComboBox::drop-down { border: none; width: 22px; }
QDialog#overlayPanel QSlider { background: #17191a; border: none; min-height: 30px; }
QDialog#overlayPanel QSlider::groove:horizontal { background: #454c46; height: 4px; border-radius: 2px; }
QDialog#overlayPanel QSlider::sub-page:horizontal { background: #d6fb51; border-radius: 2px; }
QDialog#overlayPanel QSlider::handle:horizontal { background: #efffc2; border: none; width: 16px; margin: -6px 0; border-radius: 5px; }
QDialog#overlayPanel QSlider:focus::handle:horizontal { background: white; border: 1px solid #d6fb51; }
QDialog#overlayPanel QTabWidget::pane { border: none; padding-top: 14px; }
QDialog#overlayPanel QTabBar::tab { color: #a9b1ab; background: transparent; border: none; border-bottom: 2px solid #343c34; padding: 10px 20px; min-width: 80px; }
QDialog#overlayPanel QTabBar::tab:selected { color: #f4f9e9; border-bottom: 2px solid #d6fb51; }
QDialog#overlayPanel QTabBar::tab:focus { background: #30372b; }
QDialog#overlayPanel QPushButton { color: #d9ede6; background: #2b312b; border: 1px solid #4c5846; border-radius: 5px; padding: 7px 12px; min-height: 20px; }
QDialog#overlayPanel QPushButton:hover { background: #3b4633; }
QDialog#overlayPanel QPushButton:focus { border: 2px solid #d6fb51; }
QDialog#overlayPanel QPushButton#panelClose { border: none; background: transparent; font-size: 20px; padding: 0; min-height: 28px; }
QDialog#overlayPanel QPushButton#panelClose:hover { background: #414b38; }
QDialog#overlayPanel QPushButton#panelDone { background: #d6fb51; color: #1b230b; border: none; font-weight: 600; }
QDialog#overlayPanel QPushButton#panelDone:hover { background: #e5ff8d; }
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

    def __init__(self,appearance,ocr_active=False):
        super().__init__(None,Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.setObjectName('overlayPanel'); self.setWindowTitle('LinguaPlay â€¢ Tampilan overlay'); self.setFixedWidth(364)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose,False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        palette=self.palette()
        for role in (QPalette.ColorRole.Window,QPalette.ColorRole.Button): palette.setColor(role,QColor('#17191a'))
        for role in (QPalette.ColorRole.WindowText,QPalette.ColorRole.Text,QPalette.ColorRole.ButtonText): palette.setColor(role,QColor('#e6eeec'))
        palette.setColor(QPalette.ColorRole.Base,QColor('#252a28')); palette.setColor(QPalette.ColorRole.Highlight,QColor('#414e30'))
        palette.setColor(QPalette.ColorRole.HighlightedText,QColor('#ffffff')); self.setPalette(palette)
        assets=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))/'assets'
        arrow_style=f'''
        QDialog#overlayPanel QComboBox::down-arrow {{ image: url("{(assets/'chevron-down.svg').as_posix()}"); width: 10px; height: 10px; }}
        QDialog#overlayPanel QSpinBox::up-arrow {{ image: url("{(assets/'control-plus.svg').as_posix()}"); width: 9px; height: 9px; }}
        QDialog#overlayPanel QSpinBox::down-arrow {{ image: url("{(assets/'control-minus.svg').as_posix()}"); width: 9px; height: 9px; }}
        QDialog#overlayPanel QSpinBox::up-button {{ background: #2b4338; border-left: 1px solid #48514a; border-bottom: 1px solid #48514a; width: 20px; }}
        QDialog#overlayPanel QSpinBox::down-button {{ background: #2b4338; border-left: 1px solid #48514a; width: 20px; }}
        '''
        self.setStyleSheet(PANEL_STYLE+arrow_style)
        outer=QVBoxLayout(self); outer.setContentsMargins(0,0,0,0)
        shell=QFrame(); shell.setObjectName('overlayShell'); outer.addWidget(shell)
        layout=QVBoxLayout(shell); layout.setContentsMargins(18,16,18,16); layout.setSpacing(12)
        self.drag_handle=PanelDragHandle(); header=QHBoxLayout(self.drag_handle); header.setContentsMargins(0,0,0,0); header.setSpacing(9)
        mark=QLabel('LP'); mark.setObjectName('brandMark'); mark.setAlignment(Qt.AlignmentFlag.AlignCenter); mark.setFixedSize(28,28)
        brand=QLabel('LinguaPlay'); brand.setObjectName('panelBrand')
        badge=QLabel('Ctrl+Alt+O'); badge.setObjectName('keyBadge')
        for child in (mark,brand,badge): child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        header.addWidget(mark); header.addWidget(brand,1); header.addWidget(badge)
        self.close_button=QPushButton('Ã—'); self.close_button.setObjectName('panelClose'); self.close_button.setFixedSize(28,28)
        self.close_button.setAccessibleName('Tutup pengaturan overlay'); self.close_button.setToolTip('Tutup panel (Esc)'); self.close_button.setAutoDefault(False)
        self.close_button.clicked.connect(self.reject); header.addWidget(self.close_button); layout.addWidget(self.drag_handle)
        self.status_label=QLabel('OCR dijeda sementara' if ocr_active else 'Pratinjau tampilan'); self.status_label.setObjectName('panelStatus'); layout.addWidget(self.status_label)
        self.tabs=QTabWidget(); self.tabs.setDocumentMode(True); self.tabs.tabBar().setDrawBase(False)
        text_page=QWidget(); position_page=QWidget()
        self.tabs.addTab(text_page,'Subtitle'); self.tabs.addTab(position_page,'Posisi')
        form=QFormLayout(text_page); form.setContentsMargins(0,0,0,0); form.setVerticalSpacing(12); form.setHorizontalSpacing(14)
        position_form=QFormLayout(position_page); position_form.setContentsMargins(0,0,0,0); position_form.setVerticalSpacing(12); position_form.setHorizontalSpacing(14)
        for current in (form,position_form): current.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.font_family=QFontComboBox(); self.font_family.setCurrentFont(QFont(appearance.font_family)); form.addRow('Font',self.font_family)
        self.font_size=QSpinBox(); self.font_size.setRange(14,64); self.font_size.setSuffix(' px'); self.font_size.setValue(appearance.font_size); form.addRow('Ukuran teks',self.font_size)
        self.text_color=QComboBox(); self.background_color=QComboBox()
        self.fill_colors(self.text_color,[('Putih','#ffffff'),('Kuning','#ffdd55'),('Biru muda','#82cfff'),('Hijau muda','#a9f5ba'),('Hitam','#000000')],appearance.text_color)
        self.fill_colors(self.background_color,[('Biru gelap','#0c1726'),('Hitam','#000000'),('Abu gelap','#303030'),('Putih','#ffffff')],appearance.background_color)
        form.addRow('Warna teks',self.text_color); form.addRow('Warna latar',self.background_color)
        self.background_opacity=self.slider(appearance.background_opacity)
        opacity_row=QWidget(); opacity_layout=QHBoxLayout(opacity_row); opacity_layout.setContentsMargins(0,0,0,0); opacity_layout.setSpacing(8)
        self.opacity_value=QLabel(f'{appearance.background_opacity}%'); self.opacity_value.setFixedWidth(34)
        opacity_layout.addWidget(self.background_opacity,1); opacity_layout.addWidget(self.opacity_value)
        self.background_opacity.valueChanged.connect(lambda value:self.opacity_value.setText(f'{value}%')); form.addRow('Kepekatan',opacity_row)
        self.width_percent=QSpinBox(); self.width_percent.setRange(30,95); self.width_percent.setSuffix(' % layar'); self.width_percent.setValue(appearance.width_percent); position_form.addRow('Lebar',self.width_percent)
        self.height_control=QSpinBox(); self.height_control.setRange(100,360); self.height_control.setSuffix(' px'); self.height_control.setValue(appearance.height); position_form.addRow('Tinggi',self.height_control)
        self.position_x=self.slider(appearance.position_x); self.position_y=self.slider(appearance.position_y)
        for spin in (self.font_size,self.width_percent,self.height_control): spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.PlusMinus)
        position_form.addRow('Horizontal',self.position_x); position_form.addRow('Vertikal',self.position_y)
        layout.addWidget(self.tabs)
        self.notice=QLabel('Perubahan tersimpan otomatis. Posisi subtitle tetap di luar area OCR.'); self.notice.setObjectName('panelHint'); self.notice.setWordWrap(True); layout.addWidget(self.notice)
        self.done_button=QPushButton('Kembali ke game'); self.done_button.setObjectName('panelDone'); self.done_button.setAutoDefault(False); self.done_button.clicked.connect(self.accept); layout.addWidget(self.done_button)
        footer=QLabel('Esc  Tutup panel     Ctrl+Alt+F10  Hentikan OCR'); footer.setObjectName('panelHint'); layout.addWidget(footer)
        self.move_shortcuts=[]
        for key,dx,dy in [('Left',-16,0),('Right',16,0),('Up',0,-16),('Down',0,16)]:
            shortcut=QShortcut(QKeySequence('Alt+'+key),self)
            shortcut.activated.connect(lambda x=dx,y=dy:self.move_within_screen(self.pos()+QPoint(x,y)))
            self.move_shortcuts.append(shortcut)
        for control in [self.font_size,self.width_percent,self.height_control,self.background_opacity,self.position_x,self.position_y]: control.valueChanged.connect(self.emit_change)
        self.font_family.currentFontChanged.connect(self.emit_change)
        self.text_color.currentIndexChanged.connect(self.emit_change); self.background_color.currentIndexChanged.connect(self.emit_change)

    def move_within_screen(self,position):
        screen=QGuiApplication.screenAt(position+self.rect().center()) or self.screen()
        bounds=screen.availableGeometry().adjusted(8,8,-8,-8)
        x=max(bounds.left(),min(position.x(),bounds.right()-self.width()+1))
        y=max(bounds.top(),min(position.y(),bounds.bottom()-self.height()+1))
        self.move(x,y)

    @staticmethod
    def slider(value):
        widget=QSlider(Qt.Orientation.Horizontal); widget.setRange(0,100); widget.setValue(value)
        widget.setStyleSheet('QSlider { background-color: #17191a; }')
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
