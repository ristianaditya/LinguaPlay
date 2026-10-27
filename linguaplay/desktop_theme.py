"""Dark desktop palette, separate from the in-game panel's appearance."""
from pathlib import Path
import sys
import ctypes
from PySide6.QtGui import QPalette, QColor

_assets=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))/'assets'
STYLE='''
QWidget { font-family: "Segoe UI"; font-size: 13px; color: #f4f5f3; }
QMainWindow, QWidget#appRoot, QWidget#body { background: #101112; }
QScrollArea#sidebarScroll, QWidget#sidebarBody { background: #101112; border: none; }
QDialog, QMessageBox { background: #1b1d1f; }
QLabel { background: transparent; }
QFrame#topbar { background: #151617; border-bottom: 1px solid #252c36; }
QLabel#brand { font-size: 18px; font-weight: 700; color: #f7fbff; }
QLabel#version { color: #80909d; font-size: 11px; }
QLabel#heading { font-size: 25px; font-weight: 700; color: #f5f8fc; }
QLabel#muted { color: #a0adbb; }
QLabel#section, QLabel#cardTitle { color: #e2eaf2; font-size: 14px; font-weight: 600; }
QLabel#small { color: #9ba9b7; font-size: 12px; }
QLabel#keyBadge { color: #b8c9d8; background: #292d2e; border-radius: 5px; padding: 5px 8px; font-size: 11px; }
QLabel#gameMark { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #273b50,stop:1 #173c43); color: #8cf1ff; font-size: 20px; font-weight: 700; border-radius: 10px; }
QLabel#languagePair { color: #f4f8fd; font-size: 23px; font-weight: 600; }
QLabel#formatTag { background: #212b35; color: #a5d9e6; border-radius: 4px; padding: 5px 7px; font-size: 11px; }
QLabel#notice { color: #b4c4d3; background: #19232e; padding: 12px; border-radius: 8px; }
QLabel#emptyState { color: #8393a2; background: transparent; font-size: 12px; }
QFrame#card { background: #1b1d1f; border: none; border-radius: 10px; }
QFrame#previewStage { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #1c3540,stop:1 #111c2a); border: 1px solid #304653; border-radius: 8px; }
QPushButton { background: #282b2d; color: #e4ecf4; border: 1px solid #383d3f; border-radius: 6px; padding: 7px 12px; min-height: 20px; }
QPushButton:hover { background: #2c3744; border-color: #577084; }
QPushButton:focus { border: 2px solid #d6fb51; }
QPushButton:disabled { color: #73818e; background: #1b232d; border-color: #2b3541; }
QPushButton#primary { background: #d6fb51; color: #171d0c; border: none; border-radius: 7px; font-weight: 700; padding: 10px 20px; }
QPushButton#primary:hover { background: #e4ff82; }
QPushButton#primary:disabled { background: #353c2a; color: #a7b196; }
QPushButton#nav { background: transparent; border: none; color: #98a8b9; padding: 9px 14px; min-height: 18px; }
QPushButton#nav:hover { background: #1b2530; color: white; }
QPushButton#nav:checked { color: #e9fbff; background: #20323e; }
QLineEdit, QComboBox { background: #242729; color: #f4f5f3; border: 1px solid #383d3f; border-radius: 5px; padding: 7px 9px; min-height: 19px; selection-background-color: #165871; }
QLineEdit:read-only { color: #a6b7c6; background: #161819; }
QLineEdit:focus, QComboBox:focus { border: 1px solid #d6fb51; }
QComboBox::drop-down { width: 24px; border: none; }
QComboBox::down-arrow { image: url("__CHEVRON__"); width: 10px; height: 10px; }
QComboBox QAbstractItemView { background: #242729; color: #f4f5f3; selection-background-color: #24495b; selection-color: white; }
QTableWidget, QPlainTextEdit, QListWidget { background: #161819; alternate-background-color: #1c1f20; color: #e4e7e4; border: none; border-radius: 6px; selection-background-color: #3c4930; selection-color: #f4fcff; }
QTableWidget { gridline-color: #2b3031; }
QTableWidget::item { padding: 8px 10px; border-bottom: 1px solid #292e2f; }
QTableView::indicator { width: 15px; height: 15px; }
QHeaderView::section { background: #232627; color: #9fb0c1; border: none; padding: 9px 10px; font-size: 12px; font-weight: 600; text-align: left; }
QListWidget::item { padding: 14px; border-bottom: 1px solid #2b3540; }
QListWidget::item:selected { background: #3c4930; border-radius: 5px; }
QPlainTextEdit { padding: 10px; }
QScrollBar:vertical { background: #17191a; width: 8px; border: none; margin: 0; }
QScrollBar::handle:vertical { background: #444b4a; min-height: 24px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QProgressBar { border: none; background: #212b36; height: 3px; max-height: 3px; border-radius: 1px; }
QProgressBar::chunk { background: #d6fb51; }
QToolTip { background: #243341; color: #eff9ff; border: 1px solid #587283; padding: 6px; }

QFrame#libraryRail { background: #151617; border-right: 1px solid #292c2d; }
QLabel#brandMark { background: #d6fb51; color: #182008; border-radius: 7px; font-size: 23px; font-weight: 800; }
QLabel#brand { font-size: 19px; }
QLabel#breadcrumb { color: #a8adaa; font-size: 12px; }
QPushButton#railNav { text-align: left; border: none; background: transparent; color: #b5bcb7; padding: 10px 12px; min-height: 22px; }
QPushButton#railNav:hover { background: #252928; color: #f4f5f3; }
QPushButton#railNav:checked { background: #30372a; color: #d6fb51; font-weight: 600; }
QLabel#railSection { color: #a8adaa; font-size: 12px; font-weight: 600; padding-left: 10px; }
QListWidget#railGames { background: transparent; border: none; outline: none; font-size: 12px; }
QListWidget#railGames::item { border: none; padding: 9px 8px; margin-bottom: 2px; }
QListWidget#railGames::item:selected { background: #2d332b; color: #e9f7d8; }
QLabel#localStatus { color: #c3db99; font-size: 11px; }
QLabel#libraryHeading { font-size: 30px; font-weight: 700; color: #f4f5f3; }
QLabel#gameHeading { font-size: 34px; font-weight: 700; color: #f4f5f3; }
QLabel#sectionTitle { font-size: 17px; font-weight: 600; color: #eff2ed; }
QLabel#gameState { color: #d6fb51; font-size: 13px; }
QLabel#emptyTitle { font-size: 23px; font-weight: 600; color: #eff2ed; }
QFrame#libraryEmpty { background: #191c1d; border-radius: 12px; }
QListWidget#gameGrid { background: transparent; border: none; outline: none; font-size: 13px; }
QListWidget#gameGrid::item { background: #1d2021; border: 1px solid transparent; border-radius: 10px; padding: 8px 8px 10px; margin: 0 8px 12px 0; }
QListWidget#gameGrid::item:hover { background: #292e2d; border-color: #555f50; }
QListWidget#gameGrid::item:selected { background: #30382a; border-color: #d6fb51; }
QFrame#controlGroup, QFrame#detailInfo { background: #1c1f20; border: none; border-radius: 10px; }
QLabel#errorText { color: #ffb4a5; }
QLineEdit:disabled, QComboBox:disabled { color: #8d9690; background: #1c1f20; border-color: #303536; }
'''.replace('__CHEVRON__',(_assets/'chevron-down.svg').as_posix())

def apply_palette(app):
    palette=QPalette()
    colors={QPalette.ColorRole.Window:'#1b1d1f',QPalette.ColorRole.WindowText:'#f4f5f3',
            QPalette.ColorRole.Base:'#161819',QPalette.ColorRole.AlternateBase:'#1c1f20',
            QPalette.ColorRole.Text:'#e4e7e4',QPalette.ColorRole.Button:'#282b2d',
            QPalette.ColorRole.ButtonText:'#f4f5f3',QPalette.ColorRole.Highlight:'#3c4930',
            QPalette.ColorRole.HighlightedText:'#f4fcff',QPalette.ColorRole.ToolTipBase:'#243341',
            QPalette.ColorRole.ToolTipText:'#eff9ff',QPalette.ColorRole.PlaceholderText:'#7f91a2'}
    for role,color in colors.items(): palette.setColor(role,QColor(color))
    app.setPalette(palette)

def apply_window_chrome(window):
    from PySide6.QtGui import QGuiApplication
    if QGuiApplication.platformName()!='windows': return
    try:
        setter=ctypes.windll.dwmapi.DwmSetWindowAttribute
        setter.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_void_p,ctypes.c_uint]
        hwnd=ctypes.c_void_p(int(window.winId()))
        for attribute,value in [(20,1),(35,0x16110e),(36,0xf7f2ed)]:
            setting=ctypes.c_int(value)
            setter(hwnd,attribute,ctypes.byref(setting),ctypes.sizeof(setting))
    except (AttributeError,OSError): pass
