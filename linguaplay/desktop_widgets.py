from PySide6.QtCore import Qt,Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QLabel,QPushButton,QFrame,QVBoxLayout,QTableWidget,
    QHeaderView,QAbstractItemView,QComboBox,QListWidget)
from PySide6.QtWidgets import QGraphicsDropShadowEffect

LANGUAGES={'en':'Inggris','id':'Indonesia','ja':'Jepang','ko':'Korea','zh':'Mandarin','de':'Jerman','fr':'Prancis','es':'Spanyol','pt':'Portugis','ru':'Rusia','ar':'Arab','th':'Thai'}

class LanguageCombo(QComboBox):
    code_changed=Signal(str)
    def __init__(self):
        super().__init__(); self.setEditable(True); self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        for code,name in LANGUAGES.items(): self.addItem(name,code)
        self.currentTextChanged.connect(lambda _:self.code_changed.emit(self.current_code()))

    def current_code(self):
        index=self.findText(self.currentText())
        data=self.itemData(index) if index>=0 else None
        return data if isinstance(data,str) and data else self.currentText().strip()

    def set_code(self,code):
        # The settings field echoes every keypress back here. Never replace an
        # originating partial code ("en") with its display name while typing en-US.
        if code==self.current_code(): return
        index=self.findData(code)
        if index>=0: self.setCurrentIndex(index)
        else: self.setEditText(code)

def label(text,kind=None):
    result=QLabel(text); result.setWordWrap(True)
    if kind: result.setObjectName(kind)
    return result

def button(text,callback,primary=False):
    result=QPushButton(text); result.clicked.connect(callback); result.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary: result.setObjectName('primary')
    return result

def card(title=None):
    frame=QFrame(); frame.setObjectName('card')
    shadow=QGraphicsDropShadowEffect(frame); shadow.setBlurRadius(24); shadow.setOffset(0,8); shadow.setColor(QColor(0,0,0,105)); frame.setGraphicsEffect(shadow)
    layout=QVBoxLayout(frame); layout.setContentsMargins(16,14,16,14); layout.setSpacing(10)
    if title: layout.addWidget(label(title,'cardTitle'))
    return frame,layout

class DataTable(QTableWidget):
    def __init__(self,headers,empty_text):
        super().__init__(0,len(headers)); self.setHorizontalHeaderLabels(headers)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.verticalHeader().hide(); self.setAlternatingRowColors(True); self.setShowGrid(False)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.empty=label(empty_text,'emptyState'); self.empty.setParent(self.viewport())
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter); self.empty.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.model().rowsInserted.connect(self.update_empty); self.model().rowsRemoved.connect(self.update_empty)
        self.model().modelReset.connect(self.update_empty); self.update_empty()

    def update_empty(self,*args):
        self.empty.setGeometry(self.viewport().rect().adjusted(20,8,-20,-8)); self.empty.setVisible(self.rowCount()==0)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'empty'): self.update_empty()

class OverlayPreview(QFrame):
    def __init__(self,appearance):
        super().__init__(); self.setObjectName('previewStage'); self.setMinimumHeight(116)
        layout=QVBoxLayout(self); layout.setContentsMargins(12,12,12,14)
        layout.addWidget(label('Pratinjau overlay','small')); layout.addStretch()
        self.subtitle=QLabel(); self.subtitle.setWordWrap(True); self.subtitle.setTextFormat(Qt.TextFormat.PlainText)
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(self.subtitle)
        self.current_text=''; self.apply_appearance(appearance)
        self.set_text('Subtitle terjemahan\nakan muncul di sini.')

    def set_text(self,text):
        self.current_text=text; self.subtitle.setText(text)

    def apply_appearance(self,appearance):
        color=QColor(appearance.background_color); alpha=round(255*appearance.background_opacity/100)
        size=max(13,min(22,round(appearance.font_size*.7)))
        self.subtitle.setStyleSheet(f'color: {appearance.text_color}; background: rgba({color.red()},{color.green()},{color.blue()},{alpha}); border: none; border-radius: 5px; padding: 10px; font: {size}px "{appearance.font_family}";')

class EmptyList(QListWidget):
    def __init__(self,text):
        super().__init__()
        self.empty=label(text,'emptyState'); self.empty.setParent(self.viewport()); self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.model().rowsInserted.connect(self.update_empty); self.model().rowsRemoved.connect(self.update_empty); self.model().modelReset.connect(self.update_empty)
        self.update_empty()

    def update_empty(self,*args):
        self.empty.setGeometry(self.viewport().rect().adjusted(24,16,-24,-16)); self.empty.setVisible(self.count()==0)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'empty'): self.update_empty()
