"""The backend serves the built website, so one address (or one tunnel) is the whole app."""


def test_website_and_app_routes_served(client):
    assert "MindTrace test page" in client.get("/").text
    assert "MindTrace test page" in client.get("/insights").text  # React routes fall back to index.html
    assert client.get("/assets/app.js").text == "console.log(1)"


def test_api_404_stays_json_and_no_path_escape(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404 and r.json()["error"] == "not_found"
    assert "not for the web" not in client.get("/assets/..%2F..%2Fsecret.txt").text
    assert client.get("/api/health").json()["ok"] is True
