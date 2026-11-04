"""The web root (public/) must hold only static front-end files."""
import os, pathlib

PUBLIC = pathlib.Path(__file__).resolve().parent.parent / "public"
BAD_SUFFIX = {".env", ".db", ".sqlite", ".py", ".sh", ".json", ".log", ".toml", ".ini"}


def test_public_exists_and_has_index():
    assert (PUBLIC / "index.html").is_file()


def test_public_has_no_secrets_or_source():
    for p in PUBLIC.rglob("*"):
        assert not p.name.startswith("."), p
        assert p.suffix not in BAD_SUFFIX, p


def test_default_db_path_is_outside_repo(monkeypatch):
    monkeypatch.delenv("DB_PATH", raising=False)
    import importlib, db
    importlib.reload(db)
    repo = PUBLIC.parent
    assert repo not in pathlib.Path(db.DB_PATH).resolve().parents
