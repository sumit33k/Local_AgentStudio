"""Tests for the /download endpoint — path traversal protection (P0-1)."""
import uuid
from pathlib import Path


def test_download_valid_file(client, tmp_path, monkeypatch):
    """A UUID-named file inside OUTPUT_DIR is served correctly."""
    import main
    file_id = str(uuid.uuid4())
    out_file = main.OUTPUT_DIR / f"{file_id}.md"
    out_file.write_text("# Hello", encoding="utf-8")

    res = client.get(f"/download/{file_id}.md")
    assert res.status_code == 200
    assert b"Hello" in res.content


def test_download_traversal_rejected(client):
    """Path traversal attempts must return 400, never 200."""
    for payload in ["../../etc/passwd", "../settings.json", "..%2F..%2Fetc%2Fpasswd"]:
        res = client.get(f"/download/{payload}")
        assert res.status_code in (400, 404), (
            f"Expected 400/404 for traversal payload '{payload}', got {res.status_code}"
        )


def test_download_missing_file_returns_404(client):
    """A well-formed UUID filename that doesn't exist → 404."""
    res = client.get(f"/download/{uuid.uuid4()}.md")
    assert res.status_code == 404
