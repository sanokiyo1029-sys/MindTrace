"""Scan photos survive a wiped disk (free hosts reset it on restart): they're restored from the database."""
from app import config
from app.config import MEDIA_DIR
from tests.scanhelp import login, photo, printed, upload


def test_scan_photo_comes_back_after_the_disk_is_wiped(client):
    H = login(client)
    aid, _, pages, _ = printed(client, H)
    sc = upload(client, H, aid, photo(pages[0], ["A", "B", "C"]), roll_number="03").json()
    url = sc["image_url"]
    (MEDIA_DIR / "scans" / url.rsplit("/", 1)[-1]).unlink()            # what a Render restart does
    assert client.get(url, headers=H).status_code == 200                # restored from the database
    assert client.get(sc["answers"][0]["crop_url"], headers=H).status_code == 200


def test_health_says_whether_storage_survives_restarts(client, monkeypatch):
    assert client.get("/api/health").json()["storage"] == "persistent"   # local SQLite: the disk stays
    monkeypatch.setattr(config, "PERSISTENT_STORAGE", False)
    assert client.get("/api/health").json()["storage"] == "temporary"
