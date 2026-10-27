from linguaplay.adapters import scan_game_root


def test_scan_game_root_reports_patch_or_ocr_only(tmp_path):
    (tmp_path / "dialog.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    (tmp_path / "packed.pak").write_bytes(b"PACKED")
    report = scan_game_root(tmp_path)
    assert report["support_level"] == "patch"
    assert report["candidates"] == ["dialog.srt"]


def test_scan_game_root_unknown_files_are_ocr_only(tmp_path):
    (tmp_path / "packed.pak").write_bytes(b"PACKED")
    report = scan_game_root(tmp_path)
    assert report["support_level"] == "ocr"

