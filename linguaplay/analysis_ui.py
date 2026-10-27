"""Dialog presenting a deep text analysis: where the game's English text lives and what can be done."""
import json
from dataclasses import asdict
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTableWidgetItem, QHeaderView, QFileDialog, QLabel
from .desktop_widgets import label, button, DataTable, icon_label, ACCENT

STATUS = {'patch': ('Bisa dipatch', '#d6fb51'), 'found': ('Teks ditemukan', '#8fd3ff'),
          'archive': ('Di dalam arsip', '#f5c46b'), 'locked': ('Terkunci', '#ff9d8a')}


class AnalysisDialog(QDialog):
    def __init__(self, parent, game_name, findings, engine=None):
        super().__init__(parent); self.findings = findings
        self.setWindowTitle(f'Analisis teks • {game_name}'); self.resize(1080, 680)
        layout = QVBoxLayout(self); layout.setContentsMargins(22, 20, 22, 20); layout.setSpacing(12)
        head = QHBoxLayout(); head.addWidget(icon_label('search', ACCENT, 20)); head.addWidget(label(f'Analisis mendalam: {game_name}', 'sectionTitle'), 1); layout.addLayout(head)
        counts = {key: sum(f.status == key for f in findings) for key in STATUS}
        summary = ' • '.join(f'{STATUS[k][0]}: {v}' for k, v in counts.items() if v) or 'Tidak ada teks Inggris yang ditemukan di file game.'
        engine_text = (f"Mesin: {engine['engine_name']}. " if engine and engine.get('engine_name') else '') + (engine.get('note', '') if engine else '')
        layout.addWidget(label(summary, 'muted'))
        if engine_text.strip(): layout.addWidget(label(engine_text, 'notice'))
        layout.addWidget(label('Hasil diurutkan dari yang paling menjanjikan. "Bisa dipatch" langsung bisa diterjemahkan; yang lain menunjukkan lokasi '
                               'teks dan alasan belum bisa dipatch. Overlay OCR tetap bisa dipakai untuk semua game.', 'small'))
        self.table = DataTable(['STATUS', 'JENIS', 'KALIMAT', 'FILE'], 'Tidak ada temuan.')
        header = self.table.horizontalHeader()
        for column in (0, 1, 2): header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch); self.table.setWordWrap(False)
        self.table.setRowCount(len(findings))
        for row, finding in enumerate(findings):
            text, color = STATUS[finding.status]
            cells = [text, finding.kind, f'±{finding.english}', finding.path]
            for column, value in enumerate(cells):
                item = QTableWidgetItem(value); item.setToolTip(finding.path if column == 3 else value)
                if column == 0: item.setForeground(QColor(color))
                self.table.setItem(row, column, item)
        self.table.itemSelectionChanged.connect(self.show_detail); layout.addWidget(self.table, 1)
        self.detail = QLabel(); self.detail.setObjectName('notice'); self.detail.setWordWrap(True); self.detail.setTextFormat(Qt.TextFormat.PlainText)
        self.detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); self.detail.setMinimumHeight(96); layout.addWidget(self.detail)
        actions = QHBoxLayout(); actions.addWidget(button('Simpan laporan', self.export, icon='download')); actions.addStretch()
        actions.addWidget(button('Tutup', self.accept, True, icon='check')); layout.addLayout(actions)
        if findings: self.table.selectRow(0)
        else: self.detail.setText('Teks mungkin terenkripsi, dikompres, atau ditulis langsung ke gambar. Gunakan Overlay OCR untuk menerjemahkan teks di layar.')

    def show_detail(self):
        row = self.table.currentRow()
        if not 0 <= row < len(self.findings): return
        finding = self.findings[row]
        samples = '\n'.join(f'• {s[:160]}' for s in finding.samples) or '(tidak ada contoh yang terbaca)'
        self.detail.setText(f'{finding.path}\n{finding.note}\n\nContoh teks:\n{samples}')

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Simpan laporan analisis', 'analisis-teks-linguaplay.json', 'JSON (*.json)')
        if path:
            with open(path, 'w', encoding='utf-8') as stream:
                json.dump([asdict(f) for f in self.findings], stream, ensure_ascii=False, indent=2)
