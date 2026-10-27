"""Offline Marian translation; runtime never downloads files or contacts a server."""
from pathlib import Path
from threading import Lock
import re
import sys

from .translation import TranslationError

MODEL_ID = 'opus-mt-en-id-int8-v1'
MARKER = re.compile(r'(__LPT[0-9a-f]{10}X\d+__)')


def translate_segments(text, translate):
    # Small translation models cannot reliably copy opaque placeholders. Keep them
    # outside inference, together with whitespace and punctuation-only fragments.
    parts=MARKER.split(text)
    for index,part in enumerate(parts):
        if not part or MARKER.fullmatch(part) or not any(c.isalpha() for c in part):
            continue
        leading=part[:len(part)-len(part.lstrip())]
        trailing=part[len(part.rstrip()):]
        translated=translate(part.strip())
        if not translated or not translated.strip():
            raise TranslationError('Model lokal mengembalikan teks kosong.')
        parts[index]=leading+translated.strip()+trailing
    return ''.join(parts)


class LocalModel:
    def __init__(self, path=None):
        base=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))
        self.path=Path(path) if path is not None else base/'models'/'opus-mt-en-id-int8'
        self.lock=Lock()
        self.engine=None

    def _load(self):
        if self.engine is not None: return
        required=['model.bin','config.json','source.spm','target.spm']
        if not all((self.path/name).is_file() for name in required):
            raise TranslationError('File model OPUS-MT tidak ditemukan. Ekstrak seluruh paket LinguaPlay beserta folder model.')
        try:
            import ctranslate2
            import sentencepiece
            self.source=sentencepiece.SentencePieceProcessor(model_file=str(self.path/'source.spm'))
            self.target=sentencepiece.SentencePieceProcessor(model_file=str(self.path/'target.spm'))
            self.engine=ctranslate2.Translator(str(self.path),device='cpu',compute_type='int8',inter_threads=1,intra_threads=2)
        except (ImportError,RuntimeError,OSError) as exc:
            raise TranslationError('Model OPUS-MT tidak dapat dimuat. Periksa kelengkapan paket model dan runtime lokal.') from exc

    def _translate(self, text):
        tokens=self.source.encode(text,out_type=str)+['</s>']
        if len(tokens)>480:
            raise TranslationError('Teks terlalu panjang untuk OPUS-MT. Pecah menjadi dialog yang lebih pendek (maksimal 480 token).')
        try:
            result=self.engine.translate_batch([tokens],beam_size=2,max_input_length=0,max_decoding_length=512)[0].hypotheses[0]
        except (RuntimeError,ValueError) as exc:
            raise TranslationError('OPUS-MT gagal menerjemahkan teks ini.') from exc
        if len(result)>=512:
            raise TranslationError('Hasil OPUS-MT melewati batas panjang; terjemahan tidak disimpan.')
        return self.target.decode([token for token in result if token not in ('</s>','<pad>')])

    def translate(self,text):
        with self.lock:
            self._load()
            return translate_segments(text,self._translate)


_model=LocalModel()


def translate(text,source,target):
    if source!='en' or target!='id':
        raise TranslationError('OPUS-MT lokal saat ini hanya mendukung Inggris (en) ke Indonesia (id).')
    return _model.translate(text)
