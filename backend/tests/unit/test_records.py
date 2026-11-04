from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Record
from app.db.session import get_db, init_db
from app.main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    database_url = URL.create("sqlite", database=str(tmp_path / "records.db"))
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
    response = client.post(
        "/api/v1/pets",
        json={"name": name, "species": "cat"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_record_crud_persists_and_validates_pet_deletion(
    client: TestClient, tmp_path: Path
) -> None:
    pet_id = create_pet(client)
    response = client.post(
        "/api/v1/records",
        json={
            "pet_id": pet_id,
            "record_type": "weight",
            "occurred_on": "2026-11-02",
            "name": "  体重  ",
            "weight_kg": 4.25,
            "notes": "复诊后",
        },
    )
    assert response.status_code == 201
    record = response.json()
    assert record["pet_id"] == pet_id
    assert record["record_type"] == "weight"
    assert record["occurred_on"] == "2026-11-02"
    assert record["name"] == "体重"
    assert record["weight_kg"] == 4.25
    assert record["notes"] == "复诊后"
    assert record["created_at"].endswith("Z")
    assert set(record) == {
        "id",
        "pet_id",
        "record_type",
        "occurred_on",
        "name",
        "weight_kg",
        "notes",
        "created_at",
        "updated_at",
    }

    record_id = record["id"]
    assert client.get(f"/api/v1/records/{record_id}").json() == record
    reopened_engine = create_engine(
        URL.create("sqlite", database=str(tmp_path / "records.db"))
    )
    with Session(reopened_engine) as session:
        stored_record = session.get(Record, record_id)
        assert stored_record is not None
        assert str(stored_record.weight_kg) == "4.25"
    reopened_engine.dispose()

    invalid_type_change = client.patch(
        f"/api/v1/records/{record_id}",
        json={"record_type": "bath"},
    )
    assert invalid_type_change.status_code == 422

    update = client.patch(
        f"/api/v1/records/{record_id}",
        json={"record_type": "bath", "weight_kg": None, "notes": None},
    )
    assert update.status_code == 200
    assert update.json()["record_type"] == "bath"
    assert update.json()["weight_kg"] is None
    assert update.json()["notes"] is None

    pet_delete = client.delete(f"/api/v1/pets/{pet_id}")
    assert pet_delete.status_code == 409
    assert pet_delete.json()["error"]["code"] == "PET_IN_USE"

    deleted = client.delete(f"/api/v1/records/{record_id}")
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.get(f"/api/v1/records/{record_id}").json()["error"]["code"] == (
        "RECORD_NOT_FOUND"
    )
    assert client.delete(f"/api/v1/pets/{pet_id}").status_code == 204


def test_record_filters_and_empty_results(client: TestClient) -> None:
    pet_one = create_pet(client, "豆豆")
    pet_two = create_pet(client, "团团")
    for payload in [
        {
            "pet_id": pet_one,
            "record_type": "deworming",
            "occurred_on": "2026-10-30",
        },
        {
            "pet_id": pet_one,
            "record_type": "vaccine",
            "occurred_on": "2026-11-02",
        },
        {
            "pet_id": pet_two,
            "record_type": "bath",
            "occurred_on": "2026-11-01",
        },
        {"record_type": "bath", "occurred_on": "2026-11-03"},
    ]:
        assert client.post("/api/v1/records", json=payload).status_code == 201

    all_records = client.get("/api/v1/records")
    assert all_records.status_code == 200
    assert len(all_records.json()) == 4
    assert (
        client.get("/api/v1/records", params={"pet_id": pet_one}).json()[0][
            "record_type"
        ]
        == "vaccine"
    )
    assert (
        client.get("/api/v1/records", params={"unlinked": True}).json()[0]["pet_id"]
        is None
    )
    filtered = client.get(
        "/api/v1/records",
        params={
            "pet_id": pet_one,
            "record_type": "deworming",
            "from_date": "2026-10-30",
            "to_date": "2026-10-30",
        },
    )
    assert [item["record_type"] for item in filtered.json()] == ["deworming"]
    assert (
        client.get(
            "/api/v1/records",
            params={"pet_id": pet_one, "record_type": "bath"},
        ).json()
        == []
    )

    assert (
        client.get(
            "/api/v1/records",
            params={"pet_id": pet_one, "unlinked": True},
        ).json()["error"]["code"]
        == "BAD_REQUEST"
    )
    assert (
        client.get(
            "/api/v1/records",
            params={"from_date": "2026-11-03", "to_date": "2026-11-02"},
        ).json()["error"]["code"]
        == "BAD_REQUEST"
    )
    assert (
        client.get(
            "/api/v1/records",
            params={"pet_id": "00000000-0000-0000-0000-000000000123"},
        ).json()["error"]["code"]
        == "PET_NOT_FOUND"
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"record_type": "other", "occurred_on": "2026-11-02"},
        {"record_type": "weight", "occurred_on": "2026-11-02"},
        {
            "record_type": "bath",
            "occurred_on": "2026-11-02",
            "weight_kg": 4,
        },
        {
            "record_type": "weight",
            "occurred_on": "2026-11-02",
            "weight_kg": 0,
        },
        {
            "record_type": "weight",
            "occurred_on": "2026-11-02",
            "weight_kg": 500.01,
        },
        {
            "record_type": "weight",
            "occurred_on": "2026-11-02",
            "weight_kg": 1.234,
        },
        {"record_type": "bath", "occurred_on": "2026-11-02", "unknown": "value"},
        {
            "record_type": "bath",
            "occurred_on": "2026-11-02",
            "notes": "x" * 2001,
        },
    ],
)
def test_invalid_record_create_returns_validation_error(
    client: TestClient, payload: dict[str, object]
) -> None:
    response = client.post("/api/v1/records", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_record_validation_and_failure_paths(client: TestClient) -> None:
    future_date = (
        datetime.now(ZoneInfo("Asia/Shanghai")).date() + timedelta(days=1)
    ).isoformat()
    future = client.post(
        "/api/v1/records",
        json={"record_type": "bath", "occurred_on": future_date},
    )
    assert future.status_code == 422

    missing_pet = client.post(
        "/api/v1/records",
        json={
            "pet_id": "00000000-0000-0000-0000-000000000123",
            "record_type": "bath",
            "occurred_on": "2026-11-02",
        },
    )
    assert missing_pet.status_code == 404
    assert missing_pet.json()["error"]["code"] == "PET_NOT_FOUND"

    empty = client.get("/api/v1/records")
    assert empty.status_code == 200
    assert empty.json() == []

    missing_record = "00000000-0000-0000-0000-000000000123"
    assert (
        client.get(f"/api/v1/records/{missing_record}").json()["error"]["code"]
        == "RECORD_NOT_FOUND"
    )
    assert (
        client.patch(f"/api/v1/records/{missing_record}", json={}).json()["error"][
            "code"
        ]
        == "VALIDATION_ERROR"
    )
    assert (
        client.patch(
            f"/api/v1/records/{missing_record}", json={"unknown": "value"}
        ).json()["error"]["code"]
        == "VALIDATION_ERROR"
    )
    assert (
        client.delete(f"/api/v1/records/{missing_record}").json()["error"]["code"]
        == "RECORD_NOT_FOUND"
    )


def test_record_pet_patch_can_clear_or_change_association(client: TestClient) -> None:
    pet_one = create_pet(client, "豆豆")
    pet_two = create_pet(client, "团团")
    created = client.post(
        "/api/v1/records",
        json={
            "pet_id": pet_one,
            "record_type": "bath",
            "occurred_on": "2026-11-02",
        },
    )
    record_id = created.json()["id"]

    changed = client.patch(
        f"/api/v1/records/{record_id}",
        json={"pet_id": pet_two},
    )
    assert changed.status_code == 200
    assert changed.json()["pet_id"] == pet_two

    unlinked = client.patch(
        f"/api/v1/records/{record_id}",
        json={"pet_id": None},
    )
    assert unlinked.status_code == 200
    assert unlinked.json()["pet_id"] is None

    invalid_association = client.patch(
        f"/api/v1/records/{record_id}",
        json={"pet_id": "00000000-0000-0000-0000-000000000123"},
    )
    assert invalid_association.status_code == 404
    assert invalid_association.json()["error"]["code"] == "PET_NOT_FOUND"


def create_source_reminder(
    client: TestClient,
    pet_id: str,
    record_id: str,
    due_on: str = "2026-11-02",
    title: str = "来源记录提醒",
) -> str:
    response = client.post(
        "/api/v1/reminders",
        json={
            "pet_id": pet_id,
            "title": title,
            "due_on": due_on,
            "source_record_id": record_id,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_record_pet_change_blocked_while_referenced_by_reminder(
    client: TestClient,
) -> None:
    pet_one = create_pet(client, "豆豆")
    pet_two = create_pet(client, "团团")
    created = client.post(
        "/api/v1/records",
        json={
            "pet_id": pet_one,
            "record_type": "bath",
            "occurred_on": "2026-11-02",
            "name": "洗澡",
        },
    )
    assert created.status_code == 201
    record_id = created.json()["id"]
    create_source_reminder(client, pet_one, record_id)

    blocked = client.patch(
        f"/api/v1/records/{record_id}",
        json={"pet_id": pet_two, "name": "改名"},
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "RECORD_IN_USE"

    unchanged = client.get(f"/api/v1/records/{record_id}")
    assert unchanged.status_code == 200
    assert unchanged.json()["pet_id"] == pet_one
    assert unchanged.json()["name"] == "洗澡"

    blocked_unlink = client.patch(
        f"/api/v1/records/{record_id}",
        json={"pet_id": None},
    )
    assert blocked_unlink.status_code == 409
    assert blocked_unlink.json()["error"]["code"] == "RECORD_IN_USE"


def test_record_updates_allowed_when_pet_id_not_changed(client: TestClient) -> None:
    pet_one = create_pet(client, "豆豆")
    created = client.post(
        "/api/v1/records",
        json={
            "pet_id": pet_one,
            "record_type": "weight",
            "occurred_on": "2026-11-02",
            "weight_kg": 4.25,
        },
    )
    assert created.status_code == 201
    record_id = created.json()["id"]
    create_source_reminder(client, pet_one, record_id)

    rename = client.patch(
        f"/api/v1/records/{record_id}",
        json={"name": "体重复查", "weight_kg": 4.5},
    )
    assert rename.status_code == 200
    assert rename.json()["name"] == "体重复查"
    assert rename.json()["weight_kg"] == 4.5
    assert rename.json()["pet_id"] == pet_one

    same_pet = client.patch(
        f"/api/v1/records/{record_id}",
        json={"pet_id": pet_one, "notes": "同宠物更新"},
    )
    assert same_pet.status_code == 200
    assert same_pet.json()["pet_id"] == pet_one
    assert same_pet.json()["notes"] == "同宠物更新"


def test_record_pet_change_allowed_after_reference_cleared(client: TestClient) -> None:
    pet_one = create_pet(client, "豆豆")
    pet_two = create_pet(client, "团团")
    created = client.post(
        "/api/v1/records",
        json={"pet_id": pet_one, "record_type": "bath", "occurred_on": "2026-11-02"},
    )
    assert created.status_code == 201
    record_id = created.json()["id"]
    reminder_id = create_source_reminder(client, pet_one, record_id)

    blocked = client.patch(
        f"/api/v1/records/{record_id}",
        json={"pet_id": pet_two},
    )
    assert blocked.status_code == 409

    cleared = client.patch(
        f"/api/v1/reminders/{reminder_id}",
        json={"source_record_id": None},
    )
    assert cleared.status_code == 200
    assert cleared.json()["source_record_id"] is None

    moved = client.patch(
        f"/api/v1/records/{record_id}",
        json={"pet_id": pet_two},
    )
    assert moved.status_code == 200
    assert moved.json()["pet_id"] == pet_two

    reminder_after = client.get(f"/api/v1/reminders/{reminder_id}")
    assert reminder_after.status_code == 200
    assert reminder_after.json()["pet_id"] == pet_one
    assert reminder_after.json()["source_record_id"] is None


def test_weight_trend_orders_desc_and_exposes_kg_number(client: TestClient) -> None:
    """P2-2 体重趋势图消费契约：类型过滤、occurred_on 倒序与同日稳定排序。

    列表按 occurred_on 倒序、同日按 created_at 倒序（后创建在前）返回；
    weight_kg 序列化为 JSON number（公斤固定），非 weight 记录不得混入。
    """
    pet_id = create_pet(client, "豆豆")
    created = [
        client.post(
            "/api/v1/records",
            json={
                "pet_id": pet_id,
                "record_type": "weight",
                "occurred_on": "2026-10-30",
                "weight_kg": 4.1,
            },
        ),
        client.post(
            "/api/v1/records",
            json={
                "pet_id": pet_id,
                "record_type": "bath",
                "occurred_on": "2026-11-01",
            },
        ),
        client.post(
            "/api/v1/records",
            json={
                "pet_id": pet_id,
                "record_type": "weight",
                "occurred_on": "2026-11-02",
                "weight_kg": 4.25,
            },
        ),
        client.post(
            "/api/v1/records",
            json={
                "pet_id": pet_id,
                "record_type": "weight",
                "occurred_on": "2026-11-02",
                "weight_kg": 4.5,
            },
        ),
    ]
    assert all(item.status_code == 201 for item in created)

    trend = client.get(
        "/api/v1/records", params={"pet_id": pet_id, "record_type": "weight"}
    )
    assert trend.status_code == 200
    weights = trend.json()
    assert [(item["occurred_on"], item["weight_kg"]) for item in weights] == [
        ("2026-11-02", 4.5),
        ("2026-11-02", 4.25),
        ("2026-10-30", 4.1),
    ]
    assert all(isinstance(item["weight_kg"], float) for item in weights)
    assert all(item["record_type"] == "weight" for item in weights)


def test_weight_trend_window_bounds_empty_and_single_point(
    client: TestClient,
) -> None:
    """P2-2 体重趋势图消费契约：窗口首尾均包含、空窗口与单点。

    窗口内无数据返回 200 []（图表空态）；窗口内仅一条时返回单元素数组
    （画单点、不画连线）；窗口首尾日期均包含在结果内。
    """
    pet_id = create_pet(client, "团团")
    for occurred_on, weight_kg in [("2026-11-01", 4.0), ("2026-11-03", 4.6)]:
        response = client.post(
            "/api/v1/records",
            json={
                "pet_id": pet_id,
                "record_type": "weight",
                "occurred_on": occurred_on,
                "weight_kg": weight_kg,
            },
        )
        assert response.status_code == 201

    def list_weight_window(from_date: str, to_date: str) -> list[dict[str, object]]:
        response = client.get(
            "/api/v1/records",
            params={
                "pet_id": pet_id,
                "record_type": "weight",
                "from_date": from_date,
                "to_date": to_date,
            },
        )
        assert response.status_code == 200
        return response.json()

    empty_window = list_weight_window("2026-11-02", "2026-11-02")
    assert empty_window == []

    single_point = list_weight_window("2026-11-03", "2026-11-03")
    assert [item["weight_kg"] for item in single_point] == [4.6]

    full_window = list_weight_window("2026-11-01", "2026-11-03")
    assert [item["occurred_on"] for item in full_window] == [
        "2026-11-03",
        "2026-11-01",
    ]
