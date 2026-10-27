import tempfile
import unittest
from pathlib import Path
from linguaplay.text_finder import analyze, english_sentences

class TextFinderTests(unittest.TestCase):
    def test_finds_localization_and_ignores_legal_text_and_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'mods').mkdir(); (root/'mods'/'game.pot').write_text(''.join(f'msgid "Press start to continue the game {i}"\nmsgstr ""\n\n' for i in range(20)))
            (root/'licenses').mkdir(); (root/'licenses'/'LICENSE.txt').write_text('You may use this file for any purpose and you can share it with your friends. '*200)
            (root/'data.bin').write_bytes(b'\x00\x01'*500+b'Namespace.Type::Method_Name() is not set to the instance'*50)
            found=analyze(root)
            self.assertEqual([f.path for f in found],[str(Path('mods')/'game.pot')])
            self.assertEqual(found[0].kind,'Gettext PO/POT'); self.assertTrue(found[0].localization)

    def test_sentence_filter_rejects_letter_salad_and_identifiers(self):
        self.assertEqual(english_sentences("A!Ia all  C;i;i,s's's's'  Foo.Bar::BazQux.Value"),[])
        self.assertEqual(english_sentences('You found a sharp knife in the old house.'),['You found a sharp knife in the old house.'])

if __name__=='__main__': unittest.main()
