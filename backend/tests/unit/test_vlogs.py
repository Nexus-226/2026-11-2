import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import VlogMedia, VlogPost
from app.db.session import get_db, init_db
from app.main import app
from app.services import vlog_service

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 24
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"0" * 24
MP4_BYTES = b"\x00\x00\x00\x18ftypmp42" + b"0" * 16


def shanghai_today() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("PET_AGENT_VLOG_MEDIA_DIR", str(tmp_path / "media"))
    database_url = URL.create("sqlite", database=str(tmp_path / "vlogs.db"))
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
    )
    init_db(database_url.render_as_string(hide_password=False))
    test_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        with test_session() as session:
            yield session

    monkeypatch.setattr("app.main.init_db", lambda: None)
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def create_pet(client: TestClient, name: str = "豆豆") -> str:
    response = client.post("/api/v1/pets", json={"name": name, "species": "cat"})
    assert response.status_code == 201
    return response.json()["id"]


def upload(
    client: TestClient,
    pet_id: str,
    files: list[tuple[str, tuple[str, bytes, str]]],
    **extra: str,
):
    return client.post(
        "/api/v1/vlogs",
        data={
            "pet_id": pet_id,
            "occurred_on": extra.pop("occurred_on", shanghai_today()),
            **extra,
        },
        files=files,
    )


@contextmanager
def engine_session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(URL.create("sqlite", database=str(tmp_path / "vlogs.db")))
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    try:
        with factory() as session:
            yield session
    finally:
        engine.dispose()


def media_files(directory: Path) -> list[str]:
    if not directory.exists():
        return []
    return sorted(p.name for p in directory.iterdir() if p.is_file())


def test_create_with_images_persists_media_and_serves_bytes(
    client: TestClient, tmp_path: Path
) -> None:
    pet_id = create_pet(client)
    response = upload(
        client,
        pet_id,
        [
            ("files", ("散步.png", PNG_BYTES, "image/png")),
            ("files", ("特写.jpg", JPEG_BYTES, "image/jpeg")),
        ],
        caption="  今天去公园  ",
    )
    assert response.status_code == 201
    vlog = response.json()
    assert vlog["pet_id"] == pet_id
    assert vlog["caption"] == "今天去公园"
    assert vlog["occurred_on"] == shanghai_today()
    assert [m["media_type"] for m in vlog["media"]] == ["image", "image"]
    assert [m["filename"] for m in vlog["media"]] == ["散步.png", "特写.jpg"]
    assert vlog["media"][0]["size_bytes"] == len(PNG_BYTES)
    assert vlog["media"][0]["content_type"] == "image/png"
    url = vlog["media"][0]["url"]
    assert re.fullmatch(r"/api/v1/vlogs/media/[0-9a-f]{32}\.png", url)
    assert vlog["created_at"].endswith("Z")

    served = client.get(url)
    assert served.status_code == 200
    assert served.content == PNG_BYTES
    assert served.headers["content-type"] == "image/png"

    directory = tmp_path / "media"
    assert len(media_files(directory)) == 2

    fetched = client.get(f"/api/v1/vlogs/{vlog['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == vlog

    with engine_session(tmp_path) as session:
        stored = session.query(VlogPost).one()
        assert stored.caption == "今天去公园"
        assert session.query(VlogMedia).count() == 2


def test_text_only_vlog_and_empty_caption(client: TestClient) -> None:
    pet_id = create_pet(client)
    response = upload(client, pet_id, [], caption="   ")
    assert response.status_code == 201
    vlog = response.json()
    assert vlog["media"] == []
    assert vlog["caption"] is None


def test_upload_validation_errors(client: TestClient) -> None:
    pet_id = create_pet(client)
    too_many = upload(
        client,
        pet_id,
        [("files", (f"{i}.png", PNG_BYTES, "image/png")) for i in range(4)],
    )
    assert too_many.status_code == 400
    assert too_many.json()["error"]["code"] == "VLOG_MEDIA_TOO_MANY"

    mixed = upload(
        client,
        pet_id,
        [
            ("files", ("a.png", PNG_BYTES, "image/png")),
            ("files", ("b.mp4", MP4_BYTES, "video/mp4")),
        ],
    )
    assert mixed.status_code == 400
    assert mixed.json()["error"]["code"] == "VLOG_MEDIA_MIXED"

    fake_png = upload(
        client, pet_id, [("files", ("fake.png", b"plain text", "image/png"))]
    )
    assert fake_png.status_code == 400
    assert fake_png.json()["error"]["code"] == "VLOG_MEDIA_UNSUPPORTED"

    empty = upload(client, pet_id, [("files", ("empty.png", b"", "image/png"))])
    assert empty.status_code == 400
    assert empty.json()["error"]["code"] == "VLOG_MEDIA_EMPTY"

    unknown_pet = upload(client, "00000000-0000-0000-0000-00000000000f", [])
    assert unknown_pet.status_code == 404
    assert unknown_pet.json()["error"]["code"] == "PET_NOT_FOUND"

    future = (datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(days=2)).date()
    bad_date = upload(client, pet_id, [], occurred_on=future.isoformat())
    assert bad_date.status_code == 422
    assert "occurred_on" in bad_date.json()["error"]["message"]


def test_oversize_media_rejected_before_write(
    client: TestClient, tmp_path: Path
) -> None:
    pet_id = create_pet(client)
    big_png = b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024)
    big_mp4 = b"\x00\x00\x00\x18ftypmp42" + b"0" * (20 * 1024 * 1024)

    big_image = upload(client, pet_id, [("files", ("big.png", big_png, "image/png"))])
    assert big_image.status_code == 400
    assert big_image.json()["error"]["code"] == "VLOG_MEDIA_TOO_LARGE"

    big_video = upload(client, pet_id, [("files", ("big.mp4", big_mp4, "video/mp4"))])
    assert big_video.status_code == 400
    assert big_video.json()["error"]["code"] == "VLOG_MEDIA_TOO_LARGE"

    assert media_files(tmp_path / "media") == []
    assert client.get("/api/v1/vlogs").json() == []


def test_write_failure_cleans_partial_files(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pet_id = create_pet(client)
    original = vlog_service._copy_stream
    calls = {"n": 0}

    def flaky(file, target, limit):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("disk full")
        return original(file, target, limit)

    monkeypatch.setattr(vlog_service, "_copy_stream", flaky)
    response = upload(
        client,
        pet_id,
        [
            ("files", ("a.png", PNG_BYTES, "image/png")),
            ("files", ("b.png", PNG_BYTES, "image/png")),
        ],
    )
    assert response.status_code == 500
    body = response.json()["error"]
    assert body["code"] == "VLOG_MEDIA_STORAGE_FAILED"
    assert body["retryable"] is True
    assert media_files(tmp_path / "media") == []
    assert client.get("/api/v1/vlogs").json() == []


def test_list_filters_ordering_and_pet_guard(client: TestClient) -> None:
    pet_one = create_pet(client, "豆豆")
    pet_two = create_pet(client, "团团")
    for pet, day in [
        (pet_one, "2026-11-01"),
        (pet_one, "2026-11-03"),
        (pet_two, "2026-11-02"),
    ]:
        response = upload(client, pet, [], occurred_on=day)
        assert response.status_code == 201

    all_vlogs = client.get("/api/v1/vlogs").json()
    assert [v["occurred_on"] for v in all_vlogs] == [
        "2026-11-03",
        "2026-11-02",
        "2026-11-01",
    ]

    pet_one_vlogs = client.get("/api/v1/vlogs", params={"pet_id": pet_one}).json()
    assert [v["occurred_on"] for v in pet_one_vlogs] == ["2026-11-03", "2026-11-01"]
    ranged = client.get(
        "/api/v1/vlogs",
        params={"pet_id": pet_one, "from_date": "2026-11-02", "to_date": "2026-11-03"},
    ).json()
    assert [v["occurred_on"] for v in ranged] == ["2026-11-03"]

    invalid_range = client.get(
        "/api/v1/vlogs",
        params={"from_date": "2026-11-03", "to_date": "2026-11-01"},
    )
    assert invalid_range.status_code == 400

    unknown = client.get(
        "/api/v1/vlogs",
        params={"pet_id": "00000000-0000-0000-0000-00000000000f"},
    )
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "PET_NOT_FOUND"


def test_patch_caption_and_occurred_on(client: TestClient) -> None:
    pet_id = create_pet(client)
    vlog = upload(client, pet_id, [], caption="旧文案").json()
    vlog_id = vlog["id"]

    updated = client.patch(
        f"/api/v1/vlogs/{vlog_id}",
        json={"caption": "新文案", "occurred_on": "2026-11-02"},
    )
    assert updated.status_code == 200
    assert updated.json()["caption"] == "新文案"
    assert updated.json()["occurred_on"] == "2026-11-02"

    cleared = client.patch(f"/api/v1/vlogs/{vlog_id}", json={"caption": None})
    assert cleared.status_code == 200
    assert cleared.json()["caption"] is None

    assert client.patch(f"/api/v1/vlogs/{vlog_id}", json={}).status_code == 422
    null_date = client.patch(f"/api/v1/vlogs/{vlog_id}", json={"occurred_on": None})
    assert null_date.status_code == 422

    future = (datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(days=1)).date()
    bad_date = client.patch(
        f"/api/v1/vlogs/{vlog_id}", json={"occurred_on": future.isoformat()}
    )
    assert bad_date.status_code == 422
    assert "occurred_on" in bad_date.json()["error"]["message"]

    assert (
        client.patch(f"/api/v1/vlogs/{vlog_id}", json={"pet_id": pet_id}).status_code
        == 422
    )

    missing = client.patch(
        "/api/v1/vlogs/00000000-0000-0000-0000-00000000000f", json={"caption": "x"}
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "VLOG_NOT_FOUND"


def test_delete_vlog_reclaims_media(client: TestClient, tmp_path: Path) -> None:
    pet_id = create_pet(client)
    vlog = upload(client, pet_id, [("files", ("a.png", PNG_BYTES, "image/png"))]).json()
    url = vlog["media"][0]["url"]

    deleted = client.delete(f"/api/v1/vlogs/{vlog['id']}")
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert media_files(tmp_path / "media") == []
    gone = client.get(url)
    assert gone.status_code == 404
    assert gone.json()["error"]["code"] == "VLOG_MEDIA_NOT_FOUND"
    assert client.get(f"/api/v1/vlogs/{vlog['id']}").status_code == 404
    assert client.delete(f"/api/v1/vlogs/{vlog['id']}").status_code == 404


def test_media_route_guards(client: TestClient, tmp_path: Path) -> None:
    pet_id = create_pet(client)
    vlog = upload(client, pet_id, [("files", ("a.png", PNG_BYTES, "image/png"))]).json()
    url = vlog["media"][0]["url"]
    key = url.rsplit("/", 1)[-1]

    # 路径穿越在路由/守卫层即被拒绝，不会触达媒体目录。
    traversal = client.get("/api/v1/vlogs/media/..%2Fvlogs.db")
    assert traversal.status_code == 404

    unknown = client.get("/api/v1/vlogs/media/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png")
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "VLOG_MEDIA_NOT_FOUND"

    (tmp_path / "media" / key).unlink()
    missing = client.get(url)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "VLOG_MEDIA_MISSING"


def test_media_service_guard_rejects_bad_keys(tmp_path: Path) -> None:
    init_db(f"sqlite:///{tmp_path / 'guard.db'}")
    factory = sessionmaker(
        create_engine(f"sqlite:///{tmp_path / 'guard.db'}"),
        autoflush=False,
        expire_on_commit=False,
    )
    with factory() as session:
        for bad_key in ["../vlogs.db", "a/b.png", "short.png", "x" * 33 + ".png"]:
            with pytest.raises(HTTPException) as exc:
                vlog_service.read_media_file(session, bad_key)
            assert exc.value.status_code == 404
            assert exc.value.detail["code"] == "VLOG_MEDIA_NOT_FOUND"


def test_pet_delete_cascades_vlogs_and_reclaims_media(
    client: TestClient, tmp_path: Path
) -> None:
    pet_id = create_pet(client)
    vlog = upload(client, pet_id, [("files", ("a.png", PNG_BYTES, "image/png"))]).json()

    deleted = client.delete(f"/api/v1/pets/{pet_id}")
    assert deleted.status_code == 204
    assert media_files(tmp_path / "media") == []
    assert client.get(f"/api/v1/vlogs/{vlog['id']}").status_code == 404
    assert client.get("/api/v1/vlogs").json() == []


def test_pet_with_records_still_blocked_and_vlogs_kept(
    client: TestClient, tmp_path: Path
) -> None:
    pet_id = create_pet(client)
    record = client.post(
        "/api/v1/records",
        json={
            "pet_id": pet_id,
            "record_type": "weight",
            "occurred_on": shanghai_today(),
            "weight_kg": 4.2,
        },
    )
    assert record.status_code == 201
    vlog = upload(client, pet_id, [("files", ("a.png", PNG_BYTES, "image/png"))]).json()

    blocked = client.delete(f"/api/v1/pets/{pet_id}")
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "PET_IN_USE"
    assert media_files(tmp_path / "media") != []
    assert client.get(f"/api/v1/vlogs/{vlog['id']}").status_code == 200


def test_pet_delete_media_failure_is_retryable(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pet_id = create_pet(client)
    vlog = upload(client, pet_id, [("files", ("a.png", PNG_BYTES, "image/png"))]).json()

    original_unlink = Path.unlink
    calls = {"n": 0}

    def broken_once(self: Path, missing_ok: bool = False) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("permission denied")
        original_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", broken_once)
    failed = client.delete(f"/api/v1/pets/{pet_id}")
    assert failed.status_code == 500
    body = failed.json()["error"]
    assert body["code"] == "VLOG_MEDIA_CLEANUP_FAILED"
    assert body["retryable"] is True

    # 行未删除、媒体仍在：重试成功并完成回收。
    assert client.get(f"/api/v1/vlogs/{vlog['id']}").status_code == 200
    retried = client.delete(f"/api/v1/pets/{pet_id}")
    assert retried.status_code == 204
    assert media_files(tmp_path / "media") == []
