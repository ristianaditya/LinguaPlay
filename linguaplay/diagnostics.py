"""User-invoked installation check, without game files or network requests."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
import time
from PIL import Image, ImageDraw, ImageFont
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from . import __version__
from .ui import MainWindow, configure_app
from .ocr import available_languages, recognize_image
from .adapters import scan_folder

def check_installation(output):
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    app=QApplication.instance() or QApplication([]); configure_app(app)
    result={'version':__version__,'frozen':bool(getattr(sys,'frozen',False))}
    try:
        languages=available_languages(); result['ocr_languages']=languages
        english=next((tag for tag in languages if tag.startswith('en')),None)
        if english:
            image=Image.new('RGB',(1000,150),'white')
            font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',48)
            ImageDraw.Draw(image).text((30,40),'Hello Nathan. Stay here!',fill='black',font=font)
            text=asyncio.run(recognize_image(image,english)); result['ocr_fixture']=text
            if 'Hello Nathan' not in text: raise RuntimeError('Windows OCR gagal membaca fixture.')
        base=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))
        from .translation import ProviderConfig, Translator
        start=time.perf_counter()
        with tempfile.TemporaryDirectory() as cache:
            config=ProviderConfig(kind='OPUS-MT lokal')
            local=Translator(config.backend,Path(cache)/'cache.sqlite',config.namespace())
            translated=local.translate('<i>Stay here, {player_name}!</i>')
            if not translated.startswith('<i>') or '{player_name}' not in translated or not translated.endswith('</i>'):
                raise RuntimeError('Model lokal gagal mempertahankan format subtitle.')
        result['local_model_translation']=translated
        result['local_model_seconds']=round(time.perf_counter()-start,3)
        result['local_model_offline']=True
        report=scan_folder(base/'examples'); result['example_files']=len(report.documents)
        if len(report.documents)!=2: raise RuntimeError('Sumber contoh tidak lengkap.')
        with tempfile.TemporaryDirectory() as directory:
            window=MainWindow(Path(directory)); window.show(); app.processEvents()
            result['desktop_pages']=window.pages.count()
            result['library_home']=window.pages.currentIndex()==4
            if result['desktop_pages']!=6 or not result['library_home'] or window.quick_target.current_code()!=window.config().target:
                raise RuntimeError('Navigasi atau pilihan bahasa dashboard tidak sesuai.')
            window.grab().save(str(output/'installation-preview.png'))
            for index,name in [(0,'translation'),(1,'ocr'),(2,'backups'),(3,'services')]:
                window.navigate(index); app.processEvents(); window.grab().save(str(output/f'desktop-{name}.png'))
            window.navigate(0); app.processEvents()
            window.toggle_overlay_settings(); app.processEvents()
            window.overlay_settings.font_size.setValue(30); app.processEvents()
            if window.settings_preview.appearance.font_size!=30:
                raise RuntimeError('Pratinjau tampilan overlay tidak diperbarui.')
            if not window.overlay_settings.windowFlags() & Qt.WindowType.FramelessWindowHint:
                raise RuntimeError('Panel overlay masih mempunyai bingkai sistem.')
            result['overlay_panel_frameless']=True
            result['overlay_panel_tabs']=window.overlay_settings.tabs.count()
            window.overlay_settings.grab().save(str(output/'overlay-settings-preview.png'))
            window.overlay_settings.accept(); app.processEvents()
            result['overlay_settings_live_preview']=True
            window.close(); app.processEvents()
        result['status']='ok'
    except Exception as exc:
        result['status']='error'; result['error']=str(exc)
    (output/'installation-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if result['status']=='ok' else 1
