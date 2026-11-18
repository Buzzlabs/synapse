from modules.schedule_service.module import _read_google_api_key


def test_key_file_wins_over_inline(tmp_path):
    f = tmp_path / "key"
    f.write_text("from-file\n")
    config = {"google_api_key_file": str(f), "google_api_key": "inline"}
    assert _read_google_api_key(config) == "from-file"


def test_empty_key_file_falls_back_to_inline(tmp_path):
    f = tmp_path / "key"
    f.write_text("\n")
    config = {"google_api_key_file": str(f), "google_api_key": "inline"}
    assert _read_google_api_key(config) == "inline"
