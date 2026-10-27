import time
from PySide6.QtCore import (Qt,Signal,QSize,QRectF,QObject,QEvent,QEasingCurve,QVariantAnimation,
    QPropertyAnimation,QPoint,QAbstractAnimation)
from PySide6.QtGui import QColor,QPainter,QPen,QLinearGradient,QFontMetrics,QFont
from PySide6.QtWidgets import (QLabel,QPushButton,QFrame,QVBoxLayout,QHBoxLayout,QTableWidget,QWidget,
    QHeaderView,QAbstractItemView,QComboBox,QListWidget,QProgressBar,QGraphicsOpacityEffect,QPlainTextEdit)
from PySide6.QtWidgets import QGraphicsDropShadowEffect
from .icons import icon as make_icon, pixmap as icon_pixmap

ACCENT='#d6fb51'
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

def icon_label(name,color='#c9d0cc',size=18):
    result=QLabel(); result.setPixmap(icon_pixmap(name,color,size)); result.setFixedSize(size+2,size+2)
    result.setAlignment(Qt.AlignmentFlag.AlignCenter); return result

class HoverGlow(QObject):
    """Animated accent glow behind primary buttons on hover/focus."""
    def __init__(self,widget,color=ACCENT):
        super().__init__(widget); self.widget=widget
        self.effect=QGraphicsDropShadowEffect(widget); self.effect.setOffset(0,0); self.effect.setBlurRadius(0)
        self.color=QColor(color); self.effect.setColor(self.color); widget.setGraphicsEffect(self.effect)
        self.animation=QVariantAnimation(self); self.animation.setDuration(220); self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self.paint); widget.installEventFilter(self); self.level=0.0

    def paint(self,value):
        self.level=float(value); self.effect.setBlurRadius(26*self.level)
        color=QColor(self.color); color.setAlpha(round(150*self.level)); self.effect.setColor(color)

    def eventFilter(self,obj,event):
        kind=event.type()
        if kind in (QEvent.Type.Enter,QEvent.Type.FocusIn) and self.widget.isEnabled(): self.run(1.0)
        elif kind in (QEvent.Type.Leave,QEvent.Type.FocusOut,QEvent.Type.EnabledChange): self.run(1.0 if self.widget.underMouse() and self.widget.isEnabled() else 0.0)
        return False

    def run(self,target):
        self.animation.stop(); self.animation.setStartValue(self.level); self.animation.setEndValue(target); self.animation.start()

ICON_COLORS={'primary':'#151b07','pill':'#101213'}

def button(text,callback,primary=False,icon=None,kind=None):
    result=QPushButton(text); result.clicked.connect(callback); result.setCursor(Qt.CursorShape.PointingHandCursor)
    kind='primary' if primary else kind
    if kind: result.setObjectName(kind)
    if icon:
        result.setIcon(make_icon(icon,ICON_COLORS.get(kind,'#e9edeb'),16)); result.setIconSize(QSize(16,16))
    if kind in ('primary','pill'): HoverGlow(result,ACCENT if kind=='primary' else '#ffffff')
    return result

def icon_button(name,callback,tooltip):
    result=QPushButton(); result.setObjectName('iconButton'); result.clicked.connect(callback)
    result.setIcon(make_icon(name,'#c9d0cc',16)); result.setIconSize(QSize(16,16)); result.setFixedSize(32,32)
    result.setToolTip(tooltip); result.setAccessibleName(tooltip); result.setCursor(Qt.CursorShape.PointingHandCursor)
    return result

def card(title=None,icon=None,eyebrow=None):
    # No QGraphicsEffect here: nested effects (button glow, status fade) would not render inside it.
    frame=QFrame(); frame.setObjectName('card')
    layout=QVBoxLayout(frame); layout.setContentsMargins(18,16,18,16); layout.setSpacing(10)
    if eyebrow: layout.addWidget(label(eyebrow.upper(),'eyebrow'))
    if title:
        head=QHBoxLayout(); head.setSpacing(9)
        if icon: head.addWidget(icon_label(icon,ACCENT,17))
        head.addWidget(label(title,'cardTitle'),1); layout.addLayout(head)
    return frame,layout

def row(icon,title,widget=None,detail=None):
    """Icon + text on the left, an optional control on the right (like an in-game panel row)."""
    container=QWidget(); container.setObjectName('panelRow'); line=QHBoxLayout(container); line.setContentsMargins(0,2,0,2); line.setSpacing(12)
    line.addWidget(icon_label(icon,'#aeb6b1',17)); text=QVBoxLayout(); text.setSpacing(1); text.addWidget(label(title,'rowTitle'))
    if detail: text.addWidget(label(detail,'small'))
    line.addLayout(text,1)
    if widget is not None: line.addWidget(widget)
    return container

class Spinner(QWidget):
    def __init__(self,size=18,color=ACCENT):
        super().__init__(); self.setFixedSize(size,size); self.angle=0.0; self.color=QColor(color)
        self.animation=QVariantAnimation(self); self.animation.setStartValue(0.0); self.animation.setEndValue(360.0)
        self.animation.setDuration(900); self.animation.setLoopCount(-1); self.animation.valueChanged.connect(self.tick); self.hide()

    def tick(self,value): self.angle=float(value); self.update()
    def start(self): self.show(); self.animation.start()
    def stop(self): self.animation.stop(); self.hide()

    def paintEvent(self,event):
        painter=QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=QRectF(2,2,self.width()-4,self.height()-4); pen=QPen(QColor(255,255,255,28),2.2); painter.setPen(pen); painter.drawEllipse(rect)
        pen.setColor(self.color); pen.setCapStyle(Qt.PenCapStyle.RoundCap); painter.setPen(pen)
        painter.drawArc(rect,int(-self.angle*16),int(-110*16))

class ActivityBar(QProgressBar):
    """Thin progress line; an indeterminate range (0,0) shows a travelling shimmer."""
    def __init__(self):
        super().__init__(); self.setTextVisible(False); self.setFixedHeight(3); self.phase=0.0
        self.animation=QVariantAnimation(self); self.animation.setStartValue(0.0); self.animation.setEndValue(1.0)
        self.animation.setDuration(1300); self.animation.setLoopCount(-1); self.animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.animation.valueChanged.connect(self.tick)

    def tick(self,value): self.phase=float(value); self.update()

    def setRange(self,minimum,maximum):
        super().setRange(minimum,maximum)
        if minimum==maximum==0: self.animation.start()
        else: self.animation.stop(); self.update()

    def paintEvent(self,event):
        painter=QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(),QColor(255,255,255,12))
        if self.maximum()==0:
            span=self.width()*.38; x=-span+(self.width()+span)*self.phase
            gradient=QLinearGradient(x,0,x+span,0)
            for stop,alpha in ((0,0),(.5,255),(1,0)):
                color=QColor(ACCENT); color.setAlpha(alpha); gradient.setColorAt(stop,color)
            painter.fillRect(QRectF(x,0,span,self.height()),gradient)
        elif self.maximum()>self.minimum() and self.value()>self.minimum():
            share=(self.value()-self.minimum())/(self.maximum()-self.minimum())
            painter.fillRect(QRectF(0,0,self.width()*share,self.height()),QColor(ACCENT))

class StatusLabel(QLabel):
    """Fades new messages in; rapid progress updates are shown without re-animating."""
    def __init__(self,text,kind='small'):
        super().__init__(text); self.setObjectName(kind); self.setWordWrap(True); self.last_change=0.0
        self.effect=QGraphicsOpacityEffect(self); self.effect.setOpacity(1.0); self.setGraphicsEffect(self.effect)
        self.animation=QPropertyAnimation(self.effect,b'opacity',self); self.animation.setDuration(280); self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def setText(self,text):
        if text==self.text(): return
        now=time.monotonic(); quiet=now-self.last_change>.6; self.last_change=now
        super().setText(text)
        if quiet:
            self.animation.stop(); self.animation.setStartValue(.15); self.animation.setEndValue(1.0); self.animation.start()

class SegmentedToggle(QWidget):
    """Pill switch mirroring a QComboBox (which stays the source of truth), with a sliding knob."""
    def __init__(self,combo,labels=None):
        super().__init__(); self.combo=combo; self.labels=labels or [combo.itemText(i) for i in range(combo.count())]
        self.position=float(max(0,combo.currentIndex())); self.setFixedHeight(42); self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus); self.setAccessibleName('Mode bermain')
        self.animation=QVariantAnimation(self); self.animation.setDuration(260); self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self.slide); combo.currentIndexChanged.connect(self.sync)
        font=QFont('Segoe UI'); font.setPixelSize(13); font.setWeight(QFont.Weight.DemiBold); self.setFont(font)

    def sizeHint(self):
        metrics=QFontMetrics(self.font()); return QSize(sum(metrics.horizontalAdvance(t)+40 for t in self.labels)+8,42)

    def slide(self,value): self.position=float(value); self.update()

    def sync(self,index):
        self.animation.stop(); self.animation.setStartValue(self.position); self.animation.setEndValue(float(max(0,index))); self.animation.start()

    def enabled_at(self,index):
        item=self.combo.model().item(index) if hasattr(self.combo.model(),'item') else None
        return self.isEnabled() and (item is None or item.isEnabled())

    def choose(self,index):
        if 0<=index<len(self.labels) and self.enabled_at(index): self.combo.setCurrentIndex(index)

    def mousePressEvent(self,event):
        self.choose(int(event.position().x()//(self.width()/len(self.labels))))

    def keyPressEvent(self,event):
        step={Qt.Key.Key_Left:-1,Qt.Key.Key_Right:1}.get(event.key())
        if step: self.choose(self.combo.currentIndex()+step)
        else: super().keyPressEvent(event)

    def paintEvent(self,event):
        painter=QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track=QRectF(self.rect()).adjusted(.5,.5,-.5,-.5); radius=track.height()/2
        painter.setPen(QPen(QColor(255,255,255,26),1)); painter.setBrush(QColor(255,255,255,14)); painter.drawRoundedRect(track,radius,radius)
        width=(track.width()-8)/len(self.labels)
        knob=QRectF(track.left()+4+width*self.position,track.top()+4,width,track.height()-8)
        painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QColor(ACCENT if self.isEnabled() else '#4a5040')); painter.drawRoundedRect(knob,knob.height()/2,knob.height()/2)
        for index,text in enumerate(self.labels):
            segment=QRectF(track.left()+4+width*index,track.top(),width,track.height())
            closeness=max(0.0,1-abs(self.position-index))
            color=QColor('#151b07') if closeness>.5 else QColor('#d9dfdb' if self.enabled_at(index) else '#5d6460')
            painter.setPen(color); painter.drawText(segment,Qt.AlignmentFlag.AlignCenter,text)
        if self.hasFocus():
            painter.setPen(QPen(QColor(ACCENT),1.5)); painter.setBrush(Qt.BrushStyle.NoBrush); painter.drawRoundedRect(track,radius,radius)

def fade_in(widget,duration=280,offset=14):
    """Fade + rise a widget into place; the effect is removed afterwards so it costs nothing at rest."""
    effect=QGraphicsOpacityEffect(widget); effect.setOpacity(0.0); widget.setGraphicsEffect(effect)
    fade=QPropertyAnimation(effect,b'opacity',widget); fade.setDuration(duration); fade.setStartValue(0.0); fade.setEndValue(1.0); fade.setEasingCurve(QEasingCurve.Type.OutCubic)
    end=widget.pos(); rise=QPropertyAnimation(widget,b'pos',widget); rise.setDuration(duration+60); rise.setStartValue(end+QPoint(0,offset)); rise.setEndValue(end); rise.setEasingCurve(QEasingCurve.Type.OutCubic)
    fade.finished.connect(lambda:widget.setGraphicsEffect(None))
    fade.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped); rise.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
    return fade

class Backdrop(QWidget):
    """Window background: drifting aurora glows over a dot grid and film grain, with a vignette.
    The glow is drawn at low resolution and scaled up; animation runs only while the window is active."""
    BLOBS=((214,251,81,70,.82,.08,.42,.11,.07),(64,214,190,46,.18,.86,.38,.08,.12),(140,110,255,34,.62,.72,.30,.13,.09))

    def __init__(self):
        super().__init__(); self.setObjectName('appRoot'); self.phase=0.0; self.animated=True
        self.dots=self._dot_tile(); self.grain=self._grain_tile(); self.glow=None
        from PySide6.QtCore import QTimer
        self.timer=QTimer(self); self.timer.setInterval(66); self.timer.timeout.connect(self.tick); self.timer.start()

    @staticmethod
    def _dot_tile():
        from PySide6.QtGui import QPixmap
        tile=QPixmap(26,26); tile.fill(Qt.GlobalColor.transparent); painter=QPainter(tile); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QColor(255,255,255,13)); painter.drawEllipse(QRectF(12,12,1.6,1.6)); painter.end(); return tile

    @staticmethod
    def _grain_tile():
        import random
        from PySide6.QtGui import QImage, QPixmap
        rng=random.Random(7); image=QImage(160,160,QImage.Format.Format_ARGB32); image.fill(Qt.GlobalColor.transparent)
        for _ in range(2600):
            value=rng.randint(150,255); image.setPixelColor(rng.randrange(160),rng.randrange(160),QColor(value,value,value,rng.randint(4,11)))
        return QPixmap.fromImage(image)

    def set_animated(self,enabled):
        self.animated=bool(enabled)
        if self.animated: self.timer.start()
        else: self.timer.stop()
        self.glow=None; self.update()

    def tick(self):
        window=self.window()
        if not self.animated or not self.isVisible() or window.isMinimized() or not window.isActiveWindow(): return
        self.phase+=.066; self.glow=None; self.update()

    def resizeEvent(self,event):
        self.glow=None; super().resizeEvent(event)

    def _render_glow(self):
        import math
        from PySide6.QtGui import QPixmap, QRadialGradient
        w,h=max(1,self.width()//6),max(1,self.height()//6)
        pixmap=QPixmap(w,h); pixmap.fill(QColor('#0a0c0c')); painter=QPainter(pixmap); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for r,g,b,a,x,y,size,sx,sy in self.BLOBS:
            cx=w*(x+sx*math.sin(self.phase*.23+r)); cy=h*(y+sy*math.cos(self.phase*.19+g)); radius=max(w,h)*size*(1+.08*math.sin(self.phase*.31+b))
            gradient=QRadialGradient(cx,cy,radius); gradient.setColorAt(0,QColor(r,g,b,a)); gradient.setColorAt(1,QColor(r,g,b,0)); painter.fillRect(pixmap.rect(),gradient)
        painter.end(); return pixmap

    def paintEvent(self,event):
        from PySide6.QtGui import QRadialGradient
        if self.glow is None: self.glow=self._render_glow()
        painter=QPainter(self); painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(self.rect(),self.glow)
        painter.drawTiledPixmap(self.rect(),self.dots); painter.drawTiledPixmap(self.rect(),self.grain)
        vignette=QRadialGradient(self.width()*.55,self.height()*.45,max(self.width(),self.height())*.8)
        vignette.setColorAt(.55,QColor(0,0,0,0)); vignette.setColorAt(1,QColor(0,0,0,150)); painter.fillRect(self.rect(),vignette)

class ReviewEditor(QPlainTextEdit):
    submitted=Signal()
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.submitted.emit(); return
        super().keyPressEvent(event)

class ReviewPanel(QFrame):
    """Side-by-side English/translation editor for checking, correcting and learning."""
    save_requested=Signal(str)
    revert_requested=Signal()
    step_requested=Signal(int)

    def __init__(self):
        super().__init__(); self.setObjectName('reviewPanel')
        layout=QVBoxLayout(self); layout.setContentsMargins(16,14,16,14); layout.setSpacing(8)
        top=QHBoxLayout(); top.setSpacing(8); top.addWidget(label('BAHASA INGGRIS','eyebrow'),1)
        self.position=label('','small'); self.position.setWordWrap(False); top.addWidget(self.position); layout.addLayout(top)
        self.original=QLabel('Pilih baris untuk melihat dan mengedit terjemahannya.'); self.original.setObjectName('reviewOriginal'); self.original.setWordWrap(True)
        self.original.setTextFormat(Qt.TextFormat.PlainText); self.original.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); layout.addWidget(self.original)
        head=QHBoxLayout(); head.addWidget(label('TERJEMAHAN ANDA','eyebrow'),1); self.badge=label('','reviewBadge'); self.badge.setWordWrap(False); head.addWidget(self.badge); layout.addLayout(head)
        self.editor=ReviewEditor(); self.editor.setObjectName('reviewEditor'); self.editor.setFixedHeight(74); self.editor.setPlaceholderText('Tulis atau perbaiki terjemahan di sini…')
        self.editor.submitted.connect(lambda:self.save_requested.emit(self.editor.toPlainText())); layout.addWidget(self.editor)
        self.tokens=label('','small'); layout.addWidget(self.tokens)
        actions=QHBoxLayout(); actions.setSpacing(8)
        self.prev_button=button('Sebelumnya',lambda:self.step_requested.emit(-1),icon='arrow-left')
        self.next_button=button('Berikutnya',lambda:self.step_requested.emit(1),icon='arrow-right')
        self.revert_button=button('Pakai terjemahan mesin',lambda:self.revert_requested.emit(),icon='refresh')
        self.save_button=button('Simpan',lambda:self.save_requested.emit(self.editor.toPlainText()),True,icon='check')
        self.message=label('Ctrl+Enter: simpan lalu lanjut ke baris berikutnya.','small')
        for widget in (self.prev_button,self.next_button): actions.addWidget(widget)
        actions.addWidget(self.message,1); actions.addWidget(self.revert_button); actions.addWidget(self.save_button); layout.addLayout(actions)
        self.set_entry(None)

    def set_entry(self,original,translation='',edited=False,machine=None,position='',tokens=()):
        active=original is not None
        self.original.setText(original if active else 'Pilih baris untuk melihat dan mengedit terjemahannya.')
        self.editor.setPlainText(translation if active else ''); self.editor.setEnabled(active)
        self.badge.setText('DIEDIT' if edited else ('MESIN' if machine else ('BELUM' if active else '')))
        self.badge.setProperty('state','edited' if edited else 'machine'); self.badge.style().unpolish(self.badge); self.badge.style().polish(self.badge)
        self.position.setText(position)
        self.tokens.setText(('Wajib dipertahankan:  '+'   '.join(tokens)) if tokens else '')
        self.tokens.setVisible(bool(tokens))
        for widget in (self.save_button,self.prev_button,self.next_button): widget.setEnabled(active)
        self.revert_button.setEnabled(active and edited and bool(machine))
        if active: self.message.setText('Ctrl+Enter: simpan lalu lanjut ke baris berikutnya.')

    def show_message(self,text,error=False):
        self.message.setText(text); self.message.setObjectName('errorText' if error else 'small')
        self.message.style().unpolish(self.message); self.message.style().polish(self.message)

class DataTable(QTableWidget):
    def __init__(self,headers,empty_text):
        super().__init__(0,len(headers)); self.setHorizontalHeaderLabels(headers)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.verticalHeader().hide(); self.setAlternatingRowColors(True); self.setShowGrid(False)
        self.verticalHeader().setDefaultSectionSize(40)
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
        super().__init__(); self.setObjectName('previewStage'); self.setMinimumHeight(124)
        layout=QVBoxLayout(self); layout.setContentsMargins(14,12,14,14)
        layout.addWidget(label('PRATINJAU','eyebrow')); layout.addStretch()
        self.subtitle=QLabel(); self.subtitle.setWordWrap(True); self.subtitle.setTextFormat(Qt.TextFormat.PlainText)
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(self.subtitle)
        self.current_text=''; self.apply_appearance(appearance)
        self.set_text('Subtitle terjemahan\nakan muncul di sini.')

    def set_text(self,text):
        self.current_text=text; self.subtitle.setText(text)

    def apply_appearance(self,appearance):
        color=QColor(appearance.background_color); alpha=round(255*appearance.background_opacity/100)
        size=max(13,min(22,round(appearance.font_size*.7)))
        self.subtitle.setStyleSheet(f'color: {appearance.text_color}; background: rgba({color.red()},{color.green()},{color.blue()},{alpha}); border: none; border-radius: 8px; padding: 10px; font: {size}px "{appearance.font_family}";')

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
