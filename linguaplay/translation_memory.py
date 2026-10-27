"""Small, local, human-editable glossary and translation memory stores."""
from pathlib import Path
import json
from .patches import atomic_write


class _JsonStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self):
        try:
            value = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
            return value if isinstance(value, dict) else {}
        except (OSError, UnicodeError, ValueError):
            return {}

    def _write(self, value):
        atomic_write(self.path, json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8"))


class Glossary(_JsonStore):
    def get(self, source_text):
        value = self._read().get(str(source_text))
        return value if isinstance(value, str) else None

    def set(self, source_text, target_text):
        data = self._read()
        data[str(source_text)] = str(target_text)
        self._write(data)


class TranslationMemory(_JsonStore):
    def lookup(self, source_text, source_lang, target_lang):
        key = f"{source_lang}>{target_lang}\0{source_text}"
        value = self._read().get(key)
        return value if isinstance(value, str) else None

    def store(self, source_lang, target_lang, source_text, target_text):
        data = self._read()
        data[f"{source_lang}>{target_lang}\0{source_text}"] = str(target_text)
        self._write(data)


class UserEdits(_JsonStore):
    """Translations corrected by the player, keyed by language pair and source text, so a
    correction applies everywhere that sentence appears and survives rescans/retranslation."""
    def __init__(self, path, source_lang, target_lang):
        super().__init__(path); self.prefix = f"{source_lang}>{target_lang}\0"; self.cache = self._read()

    def lookup(self, source_text):
        value = self.cache.get(self.prefix + source_text)
        return value if isinstance(value, str) else None

    def store(self, source_text, target_text):
        self.cache[self.prefix + source_text] = str(target_text); self._write(self.cache)

    def remove(self, source_text):
        if self.cache.pop(self.prefix + source_text, None) is not None: self._write(self.cache)

    def count(self):
        return sum(1 for key in self.cache if key.startswith(self.prefix))
