"""Run with the bundled environment; native OCR test uses a generated image."""
import unittest
import asyncio
import tempfile
import time
from pathlib import Path
from threading import Event
from unittest.mock import patch
from PIL import Image, ImageDraw, ImageFont

class DesktopTests(unittest.TestCase):
    def test_ocr_worker_translates_fixture_and_stops(self):
        from PySide6.QtWidgets import QApplication
        from linguaplay.ocr import available_languages, OcrWorker
        from linguaplay.translation import Translator
        app=QApplication.instance() or QApplication([])
        language=next((x for x in available_languages() if x.startswith('en')),None)
        if not language: self.skipTest('English OCR unavailable')
        image=Image.new('RGB',(900,150),'white')
        ImageDraw.Draw(image).text((30,40),'Hello Nathan!',fill='black',font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',48))
        cancel=Event(); result=[]; failures=[]
        with tempfile.TemporaryDirectory() as directory:
            translator=Translator(lambda text:text.replace('Hello','Halo'),Path(directory)/'cache.sqlite','ocr-fixture')
            worker=OcrWorker((0,0,900,150),language,translator,cancel)
            def received(text): result.append(text); cancel.set()
            worker.subtitle.connect(received); worker.failure.connect(failures.append)
            with patch('linguaplay.ocr.ImageGrab.grab',return_value=image):
                worker.start(); deadline=time.monotonic()+10
                while worker.isRunning() and time.monotonic()<deadline:
                    app.processEvents(); time.sleep(.01)
                cancel.set(); worker.wait(3000); app.processEvents()
            self.assertFalse(worker.isRunning()); self.assertEqual(failures,[])
            self.assertTrue(any('Halo Nathan' in text for text in result))

    def test_windows_ocr_fixture(self):
        from linguaplay.ocr import recognize_image, available_languages
        langs=available_languages()
        english=next((tag for tag in langs if tag.startswith('en')),None)
        if not english: self.skipTest('English OCR language pack unavailable')
        image=Image.new('RGB',(1100,150),'white')
        draw=ImageDraw.Draw(image)
        font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',48)
        draw.text((30,40),'Hello Nathan. Stay here!',fill='black',font=font)
        text=asyncio.run(recognize_image(image,english))
        self.assertIn('Hello Nathan',text)
        self.assertIn('Stay here',text)

if __name__=='__main__': unittest.main()
