"""Acceptance tests for specs/0001-foundation.md (auth)."""


def test_at_0001_01_login_returns_jwt_pair(api, user):
    res = api.post("/api/auth/token/", {"username": "alice", "password": "s3cret-pass!"})
    assert res.status_code == 200
    assert {"access", "refresh"} <= res.json().keys()


def test_at_0001_01_wrong_password_is_rejected(api, user):
    res = api.post("/api/auth/token/", {"username": "alice", "password": "nope"})
    assert res.status_code == 401


def test_at_0001_02_me_requires_a_token(api, db):
    assert api.get("/api/auth/me/").status_code == 401


def test_at_0001_02_me_returns_the_current_user(api, user):
    access = api.post("/api/auth/token/", {"username": "alice", "password": "s3cret-pass!"}).json()[
        "access"
    ]
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    assert api.get("/api/auth/me/").json()["username"] == "alice"


def test_at_0001_03_refresh_issues_a_new_access_token(api, user):
    refresh = api.post(
        "/api/auth/token/", {"username": "alice", "password": "s3cret-pass!"}
    ).json()["refresh"]
    res = api.post("/api/auth/token/refresh/", {"refresh": refresh})
    assert res.status_code == 200
    assert "access" in res.json()
