from linguaplay.translation_memory import Glossary, TranslationMemory


def test_glossary_and_memory_are_language_pair_specific(tmp_path):
    glossary = Glossary(tmp_path / "glossary.json")
    glossary.set("Health Potion", "Ramuan Kesehatan")
    assert glossary.get("Health Potion") == "Ramuan Kesehatan"

    memory = TranslationMemory(tmp_path / "memory.json")
    memory.store("en", "id", "Open the door", "Buka pintunya")
    assert memory.lookup("Open the door", "en", "id") == "Buka pintunya"
    assert memory.lookup("Open the door", "en", "fr") is None

