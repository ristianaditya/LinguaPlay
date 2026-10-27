"""Small resumable offline translation job manifest."""
from dataclasses import dataclass
from pathlib import Path
import json
from .patches import atomic_write


@dataclass
class TranslationJobStatus:
    state: str
    completed_units: int
    total_units: int
    outputs: list[str]


class TranslationJob:
    def __init__(self, manifest, units, translate):
        self.manifest = Path(manifest)
        self.manifest.parent.mkdir(parents=True, exist_ok=True)
        self.units = list(units)
        self.translate = translate
        self._load()

    def _load(self):
        try:
            data = json.loads(self.manifest.read_text(encoding='utf-8')) if self.manifest.exists() else {}
        except (OSError, UnicodeError, ValueError):
            data = {}
        self.outputs = list(data.get('outputs', [])) if isinstance(data, dict) else []

    def _save(self, state):
        atomic_write(self.manifest, json.dumps({'state': state, 'outputs': self.outputs}, ensure_ascii=False).encode())

    def run(self, max_units=None):
        if len(self.outputs) > len(self.units):
            self.outputs = []
        start = len(self.outputs)
        end = len(self.units) if max_units is None else min(len(self.units), start + max_units)
        for unit in self.units[start:end]:
            self.outputs.append(self.translate(unit))
        state = 'completed' if len(self.outputs) == len(self.units) else 'paused'
        self._save(state)
        return TranslationJobStatus(state, len(self.outputs), len(self.units), list(self.outputs))
