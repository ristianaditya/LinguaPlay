from pathlib import Path

from linguaplay.library import GameLibrary


def test_game_profile_round_trip_isolated_per_game(tmp_path):
    root = tmp_path / "game"
    root.mkdir()
    exe = root / "game.exe"
    exe.write_bytes(b"stub")
    library = GameLibrary(tmp_path / "data")
    game = library.add_executable(exe, "Demo")

    profile = library.get_profile(game["id"])
    profile["target_language"] = "id"
    profile["adapter_id"] = "srt"
    library.save_profile(game["id"], profile)

    reloaded = GameLibrary(tmp_path / "data")
    assert reloaded.get_profile(game["id"])["target_language"] == "id"
    assert reloaded.get_profile("missing")["target_language"] == "id"

