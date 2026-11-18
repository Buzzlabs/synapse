from modules.vod_service.module import _read_service_token


def test_token_file_wins_over_inline(tmp_path):
    f = tmp_path / "token"
    f.write_text("from-file\n")
    config = {"service_token_file": str(f), "service_token": "inline"}
    assert _read_service_token(config) == "from-file"


def test_empty_token_file_falls_back_to_inline(tmp_path):
    f = tmp_path / "token"
    f.write_text("\n")
    config = {"service_token_file": str(f), "service_token": "inline"}
    assert _read_service_token(config) == "inline"
