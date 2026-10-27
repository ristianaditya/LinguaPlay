import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from linguaplay.translation import ProviderConfig, TranslationError, Translator
from linguaplay.local_mt import translate_segments, LocalModel


class LocalTranslationTests(unittest.TestCase):
    @unittest.skipUnless((LocalModel().path/'model.bin').is_file(),'model package not present')
    def test_real_model_runs_offline_and_rejects_oversized_text(self):
        model=LocalModel()
        self.assertIsNone(model.engine)
        with patch('socket.socket',side_effect=AssertionError('network forbidden')):
            with tempfile.TemporaryDirectory() as folder:
                translator=Translator(model.translate,Path(folder)/'cache.sqlite','actual-local')
                source='<i>Stay here, {player_name}!</i>'
                result=translator.translate(source)
                self.assertNotEqual(result,source)
                self.assertTrue(result.startswith('<i>'))
                self.assertTrue(result.endswith('{player_name}!</i>'))
                with self.assertRaisesRegex(TranslationError,'terlalu panjang'):
                    translator.translate('hello '*1500)

    def test_placeholders_markup_and_linebreaks_never_enter_model(self):
        calls=[]
        def translate(text):
            calls.append(text)
            return {'Stay here,':'Tetap di sini,','You have':'Anda memiliki','coins.':'koin.'}[text]
        with tempfile.TemporaryDirectory() as folder:
            translator=Translator(lambda text:translate_segments(text,translate),Path(folder)/'cache.sqlite','local-test')
            result=translator.translate('<i>Stay here, {name}!</i>\nYou have {count} coins.')
        self.assertEqual(result,'<i>Tetap di sini, {name}!</i>\nAnda memiliki {count} koin.')
        self.assertEqual(calls,['Stay here,','You have','coins.'])

    def test_local_provider_rejects_unsupported_language_before_network(self):
        config=ProviderConfig(kind='OPUS-MT lokal',source='ja',target='id')
        with patch('urllib.request.build_opener',side_effect=AssertionError('network forbidden')):
            with self.assertRaisesRegex(TranslationError,'Inggris.*Indonesia'):
                config.backend('Hello')

    def test_missing_model_is_actionable_and_never_downloads(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(TranslationError,'model.*tidak ditemukan'):
                LocalModel(Path(folder)).translate('Hello')

    def test_local_cache_namespace_ignores_unused_api_fields(self):
        a=ProviderConfig(kind='OPUS-MT lokal',endpoint='https://unused.example',model='unused')
        b=ProviderConfig(kind='OPUS-MT lokal',endpoint='',model='')
        self.assertEqual(a.namespace(),b.namespace())
        b.target='ja'
        self.assertNotEqual(a.namespace(),b.namespace())
