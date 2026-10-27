"""Dark desktop palette, separate from the in-game panel's appearance."""
from pathlib import Path
import sys
import ctypes
from PySide6.QtGui import QPalette, QColor

_assets=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))/'assets'
STYLE='''
QWidget { font-family: "Segoe UI"; font-size: 13px; color: #eef1ee; }
QMainWindow, QWidget#body { background: transparent; }
QStackedWidget, QScrollArea#sidebarScroll, QWidget#sidebarBody { background: transparent; border: none; }
QDialog, QMessageBox { background: #16191a; }
QLabel { background: transparent; }
QLabel#brand { font-size: 18px; font-weight: 700; color: #f7f9f6; }
QLabel#version { color: #6f7772; font-size: 11px; }
QLabel#heading { font-size: 26px; font-weight: 700; color: #f6f8f4; }
QLabel#muted { color: #a3aba6; }
QLabel#section, QLabel#cardTitle { color: #f0f3ef; font-size: 14px; font-weight: 600; }
QLabel#rowTitle { color: #e9ede9; font-size: 13px; font-weight: 500; }
QLabel#eyebrow { color: #8a928d; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; }
QLabel#small { color: #99a29c; font-size: 12px; }
QLabel#keyBadge { color: #cfd6d1; background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.08); border-radius: 7px; padding: 4px 9px; font-size: 11px; font-weight: 600; }
QLabel#gameMark { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 rgba(214,251,81,0.22),stop:1 rgba(214,251,81,0.05)); border: 1px solid rgba(214,251,81,0.28); border-radius: 14px; }
QLabel#languagePair { color: #f6f8f4; font-size: 22px; font-weight: 700; }
QLabel#formatTag { background: rgba(214,251,81,0.10); color: #dff58f; border: 1px solid rgba(214,251,81,0.22); border-radius: 10px; padding: 4px 10px; font-size: 11px; font-weight: 600; }
QLabel#notice { color: #d5dbd6; background: rgba(214,251,81,0.06); border: 1px solid rgba(214,251,81,0.16); padding: 12px 14px; border-radius: 12px; }
QLabel#emptyState { color: #7d8681; background: transparent; font-size: 12px; }
QFrame#card { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(34,38,39,0.92),stop:1 rgba(24,27,28,0.92)); border: 1px solid rgba(255,255,255,0.075); border-radius: 18px; }
QFrame#previewStage { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 rgba(38,52,30,0.85),stop:1 rgba(17,21,22,0.9)); border: 1px solid rgba(214,251,81,0.18); border-radius: 14px; }
QPushButton { background: rgba(255,255,255,0.065); color: #e9eee9; border: 1px solid rgba(255,255,255,0.09); border-radius: 18px; padding: 8px 16px; min-height: 20px; font-weight: 500; }
QPushButton:hover { background: rgba(255,255,255,0.11); border-color: rgba(255,255,255,0.18); }
QPushButton:pressed { background: rgba(255,255,255,0.05); }
QPushButton:focus { border: 1px solid #d6fb51; }
QPushButton:disabled { color: #5f6762; background: rgba(255,255,255,0.03); border-color: rgba(255,255,255,0.05); }
QPushButton#primary { background: #d6fb51; color: #151b07; border: none; border-radius: 19px; font-weight: 700; padding: 10px 22px; }
QPushButton#primary:hover { background: #e3ff7a; }
QPushButton#primary:pressed { background: #c3e844; }
QPushButton#primary:disabled { background: #2c3122; color: #737b62; }
QPushButton#pill { background: #f4f6f2; color: #101213; border: none; border-radius: 19px; font-weight: 700; padding: 10px 22px; }
QPushButton#pill:hover { background: #ffffff; }
QPushButton#iconButton { background: transparent; border: none; border-radius: 10px; padding: 0; }
QPushButton#iconButton:hover { background: rgba(255,255,255,0.09); }
QLineEdit, QComboBox { background: rgba(255,255,255,0.05); color: #eef1ee; border: 1px solid rgba(255,255,255,0.09); border-radius: 12px; padding: 8px 12px; min-height: 19px; selection-background-color: #3d4a1d; }
QLineEdit:hover, QComboBox:hover { border-color: rgba(255,255,255,0.17); }
QLineEdit:read-only { color: #a9b1ac; background: rgba(0,0,0,0.18); }
QLineEdit:focus, QComboBox:focus { border: 1px solid #d6fb51; background: rgba(214,251,81,0.04); }
QComboBox::drop-down { width: 26px; border: none; }
QComboBox::down-arrow { image: url("__CHEVRON__"); width: 10px; height: 10px; }
QComboBox QAbstractItemView { background: #1d2021; color: #eef1ee; border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; padding: 4px; selection-background-color: rgba(214,251,81,0.18); selection-color: white; outline: none; }
QTableWidget, QPlainTextEdit, QListWidget { background: rgba(0,0,0,0.16); alternate-background-color: rgba(255,255,255,0.022); color: #e3e7e3; border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; selection-background-color: rgba(214,251,81,0.16); selection-color: #f7fbef; }
QTableWidget { gridline-color: transparent; outline: none; }
QTableWidget::item { padding: 8px 12px; border-bottom: 1px solid rgba(255,255,255,0.04); }
QTableWidget::item:hover { background: rgba(255,255,255,0.04); }
QTableView::indicator { width: 16px; height: 16px; }
QHeaderView::section { background: transparent; color: #8a928d; border: none; border-bottom: 1px solid rgba(255,255,255,0.07); padding: 10px 12px; font-size: 11px; font-weight: 700; text-align: left; }
QListWidget::item { padding: 14px; border-bottom: 1px solid rgba(255,255,255,0.05); }
QListWidget::item:hover { background: rgba(255,255,255,0.04); }
QListWidget::item:selected { background: rgba(214,251,81,0.14); border-radius: 10px; }
QPlainTextEdit { padding: 12px; }
QScrollBar:vertical { background: transparent; width: 8px; border: none; margin: 2px; }
QScrollBar::handle:vertical { background: rgba(255,255,255,0.14); min-height: 28px; border-radius: 3px; }
QScrollBar::handle:vertical:hover { background: rgba(214,251,81,0.5); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical, QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { height: 0; background: transparent; }
QToolTip { background: #1d2120; color: #f1f5ef; border: 1px solid rgba(214,251,81,0.35); border-radius: 8px; padding: 6px 9px; }

QFrame#libraryRail { background: rgba(14,16,16,0.82); border-right: 1px solid rgba(255,255,255,0.06); }
QFrame#navIndicator { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 rgba(214,251,81,0.20),stop:1 rgba(214,251,81,0.04)); border: 1px solid rgba(214,251,81,0.22); border-radius: 12px; }
QLabel#brandMark { background: transparent; }
QLabel#breadcrumb { color: #8f9893; font-size: 12px; font-weight: 600; }
QPushButton#railNav { text-align: left; border: none; background: transparent; color: #aab2ad; padding: 10px 12px; min-height: 22px; border-radius: 12px; font-weight: 500; }
QPushButton#railNav:hover { background: rgba(255,255,255,0.05); color: #f4f6f2; }
QPushButton#railNav:checked { background: transparent; color: #f4ffd6; font-weight: 700; }
QPushButton#railNav:focus { border: none; }
QLabel#railSection { color: #737b76; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; padding-left: 12px; }
QListWidget#railGames { background: transparent; border: none; outline: none; font-size: 12px; }
QListWidget#railGames::item { border: none; padding: 9px 10px; margin-bottom: 2px; border-radius: 10px; color: #c4cbc6; }
QListWidget#railGames::item:hover { background: rgba(255,255,255,0.05); }
QListWidget#railGames::item:selected { background: rgba(214,251,81,0.12); color: #ecf9c4; }
QLabel#localStatus { color: #c6e27a; font-size: 11px; font-weight: 600; background: rgba(214,251,81,0.07); border-radius: 10px; padding: 6px 10px; }
QLabel#libraryHeading { font-size: 32px; font-weight: 800; color: #f6f8f4; }
QLabel#gameHeading { font-size: 36px; font-weight: 800; color: #ffffff; }
QLabel#sectionTitle { font-size: 16px; font-weight: 700; color: #eff2ed; }
QLabel#gameState { color: #d6fb51; font-size: 12px; font-weight: 700; background: rgba(214,251,81,0.12); border: 1px solid rgba(214,251,81,0.28); border-radius: 11px; padding: 4px 11px; }
QLabel#platformChip { color: #d7ddd9; font-size: 11px; font-weight: 700; letter-spacing: 1px; background: rgba(0,0,0,0.35); border-radius: 10px; padding: 4px 10px; }
QLabel#emptyTitle { font-size: 26px; font-weight: 800; color: #f2f5ef; }
QFrame#libraryEmpty { background: transparent; }
QFrame#stepCard { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(34,38,39,0.9),stop:1 rgba(22,25,26,0.9)); border: 1px solid rgba(255,255,255,0.07); border-radius: 18px; }
QLabel#stepNumber { color: #151b07; background: #d6fb51; border-radius: 13px; font-size: 12px; font-weight: 800; }
QLabel#stepTitle { color: #f2f5ef; font-size: 15px; font-weight: 700; }
QLabel#heroIcon { background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 rgba(214,251,81,0.28), stop:1 rgba(214,251,81,0)); border-radius: 48px; }
QListWidget#gameGrid { background: transparent; border: none; outline: none; font-size: 13px; }
QListWidget#gameGrid::item { background: transparent; border: 2px solid transparent; border-radius: 16px; padding: 4px; margin: 0 8px 12px 0; }
QListWidget#gameGrid::item:hover { border-color: rgba(255,255,255,0.22); background: rgba(255,255,255,0.03); }
QListWidget#gameGrid::item:selected { border-color: #d6fb51; background: rgba(214,251,81,0.06); }
QFrame#controlGroup, QFrame#detailInfo { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(34,38,39,0.9),stop:1 rgba(23,26,27,0.9)); border: 1px solid rgba(255,255,255,0.07); border-radius: 18px; }
QLabel#errorText { color: #ffb4a5; font-size: 12px; }
QFrame#reviewPanel { background: rgba(0,0,0,0.18); border: 1px solid rgba(214,251,81,0.14); border-radius: 14px; }
QLabel#reviewOriginal { color: #f6f8f4; font-size: 15px; font-weight: 500; padding: 2px 0 4px 0; }
QPlainTextEdit#reviewEditor { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.10); border-radius: 10px; font-size: 14px; padding: 8px; color: #f2f5ef; }
QPlainTextEdit#reviewEditor:focus { border: 1px solid #d6fb51; }
QLabel#reviewBadge { color: #c9d0cc; background: rgba(255,255,255,0.07); border-radius: 9px; padding: 2px 9px; font-size: 10px; font-weight: 800; letter-spacing: 1px; }
QLabel#reviewBadge[state="edited"] { color: #151b07; background: #d6fb51; }
QLineEdit:disabled, QComboBox:disabled { color: #6f7772; background: rgba(255,255,255,0.025); border-color: rgba(255,255,255,0.05); }
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
