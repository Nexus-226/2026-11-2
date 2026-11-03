from collections.abc import Iterator
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Reminder
from app.db.session import get_db, init_db
from app.main import app
from app.schemas.reminder import reminder_due_group


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    database_url = URL.create("sqlite", database=str(tmp_path / "reminders.db"))
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


def create_reminder(
    client: TestClient,
    *,
    pet_id: str | None = None,
    title: str = "下次驱虫",
    due_on: date | None = None,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/reminders",
        json={
            "pet_id": pet_id,
            "title": title,
            "due_on": (due_on or date.today()).isoformat(),
        },
    )
    assert response.status_code == 201
    return response.json()


def test_reminder_crud_persists_and_protects_pet_deletion(
    client: TestClient, tmp_path: Path
) -> None:
    pet_id = create_pet(client)
    due_on = datetime.now(ZoneInfo("Asia/Shanghai")).date() + timedelta(days=1)
    reminder = create_reminder(client, pet_id=pet_id, due_on=due_on)

    assert reminder["pet_id"] == pet_id
    assert reminder["title"] == "下次驱虫"
    assert reminder["due_on"] == due_on.isoformat()
    assert reminder["status"] == "pending"
    assert reminder["due_group"] == "upcoming"
    assert reminder["source_record_id"] is None
    assert reminder["created_at"].endswith("Z")
    assert set(reminder) == {
        "id",
        "pet_id",
        "title",
        "due_on",
        "status",
        "due_group",
        "source_record_id",
        "created_at",
        "updated_at",
    }

    reminder_id = str(reminder["id"])
    assert client.get(f"/api/v1/reminders/{reminder_id}").json() == reminder
    reopened_engine = create_engine(
        URL.create("sqlite", database=str(tmp_path / "reminders.db"))
    )
    with Session(reopened_engine) as session:
        stored_reminder = session.get(Reminder, reminder_id)
        assert stored_reminder is not None
        assert stored_reminder.status == "pending"
    reopened_engine.dispose()

    update = client.patch(
        f"/api/v1/reminders/{reminder_id}",
        json={"title": "  下次体检  ", "due_on": due_on.isoformat()},
    )
    assert update.status_code == 200
    assert update.json()["title"] == "下次体检"

    pet_delete = client.delete(f"/api/v1/pets/{pet_id}")
    assert pet_delete.status_code == 409
    assert pet_delete.json()["error"]["code"] == "PET_IN_USE"

    assert client.delete(f"/api/v1/reminders/{reminder_id}").status_code == 204
    assert client.delete(f"/api/v1/pets/{pet_id}").status_code == 204
    missing = client.get(f"/api/v1/reminders/{reminder_id}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "REMINDER_NOT_FOUND"


def test_reminder_title_is_trimmed_before_length_validation(
    client: TestClient,
) -> None:
    reminder = create_reminder(client, title=f"  {'x' * 120}  ")
    assert len(str(reminder["title"])) == 120
    assert str(reminder["title"]) == "x" * 120


def test_reminder_filters_and_empty_results(client: TestClient) -> None:
    pet_one = create_pet(client, "豆豆")
    pet_two = create_pet(client, "团团")
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    first = create_reminder(
        client, pet_id=pet_one, title="复诊", due_on=today - timedelta(days=1)
    )
    create_reminder(client, pet_id=pet_one, title="洗澡", due_on=today)
    create_reminder(client, pet_id=pet_two, title="疫苗", due_on=today)
    unlinked = create_reminder(client, title="未关联事项", due_on=today)
    client.patch(f"/api/v1/reminders/{first['id']}", json={"status": "completed"})

    assert len(client.get("/api/v1/reminders").json()) == 4
    filtered = client.get(
        "/api/v1/reminders",
        params={
            "pet_id": pet_one,
            "status": "pending",
            "from_date": today.isoformat(),
            "to_date": today.isoformat(),
        },
    )
    assert [item["title"] for item in filtered.json()] == ["洗澡"]
    assert (
        client.get("/api/v1/reminders", params={"unlinked": True}).json()[0]["id"]
        == unlinked["id"]
    )
    assert (
        client.get(
            "/api/v1/reminders",
            params={"pet_id": pet_one, "status": "completed"},
        ).json()[0]["id"]
        == first["id"]
    )
    assert (
        client.get(
            "/api/v1/reminders",
            params={"pet_id": pet_one, "status": "cancelled"},
        ).json()
        == []
    )
    assert (
        client.get(
            "/api/v1/reminders", params={"pet_id": pet_two, "unlinked": True}
        ).json()["error"]["code"]
        == "BAD_REQUEST"
    )
    assert (
        client.get(
            "/api/v1/reminders",
            params={
                "from_date": (today + timedelta(days=1)).isoformat(),
                "to_date": today.isoformat(),
            },
        ).json()["error"]["code"]
        == "BAD_REQUEST"
    )
    assert (
        client.get(
            "/api/v1/reminders",
            params={"pet_id": "00000000-0000-0000-0000-000000000123"},
        ).json()["error"]["code"]
        == "PET_NOT_FOUND"
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"title": " ", "due_on": "2026-11-03"},
        {"title": "x" * 121, "due_on": "2026-11-03"},
        {"title": "合法", "due_on": "2026-11-03", "status": "completed"},
        {"title": "合法", "due_on": "2026-11-03", "unknown": "value"},
    ],
)
def test_invalid_reminder_create_returns_validation_error(
    client: TestClient, payload: dict[str, object]
) -> None:
    response = client.post("/api/v1/reminders", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_reminder_validation_and_status_transitions(client: TestClient) -> None:
    empty = client.get("/api/v1/reminders")
    assert empty.status_code == 200
    assert empty.json() == []

    missing_id = "00000000-0000-0000-0000-000000000123"
    assert client.get(f"/api/v1/reminders/{missing_id}").json()["error"]["code"] == (
        "REMINDER_NOT_FOUND"
    )
    assert (
        client.patch(f"/api/v1/reminders/{missing_id}", json={"title": "x"}).json()[
            "error"
        ]["code"]
        == "REMINDER_NOT_FOUND"
    )
    assert client.delete(f"/api/v1/reminders/{missing_id}").json()["error"]["code"] == (
        "REMINDER_NOT_FOUND"
    )

    reminder = create_reminder(client)
    reminder_id = str(reminder["id"])
    for payload in [{}, {"unknown": "value"}, {"title": None}, {"status": None}]:
        response = client.patch(f"/api/v1/reminders/{reminder_id}", json=payload)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    completed = client.patch(
        f"/api/v1/reminders/{reminder_id}", json={"status": "completed"}
    )
    assert completed.status_code == 200
    assert completed.json()["due_group"] is None
    completed_again = client.patch(
        f"/api/v1/reminders/{reminder_id}", json={"status": "completed"}
    )
    assert completed_again.status_code == 200
    assert completed_again.json()["updated_at"] == completed.json()["updated_at"]
    reopen = client.patch(
        f"/api/v1/reminders/{reminder_id}", json={"status": "pending"}
    )
    assert reopen.status_code == 422
    assert reopen.json()["error"]["code"] == "VALIDATION_ERROR"

    cancelled = create_reminder(client, title="取消测试")
    cancelled_once = client.patch(
        f"/api/v1/reminders/{cancelled['id']}", json={"status": "cancelled"}
    )
    assert cancelled_once.status_code == 200
    assert cancelled_once.json()["due_group"] is None
    cancelled_twice = client.patch(
        f"/api/v1/reminders/{cancelled['id']}", json={"status": "cancelled"}
    )
    assert cancelled_twice.status_code == 200
    assert cancelled_twice.json()["updated_at"] == cancelled_once.json()["updated_at"]
    cannot_complete = client.patch(
        f"/api/v1/reminders/{cancelled['id']}", json={"status": "completed"}
    )
    assert cannot_complete.status_code == 422


def test_source_record_reference_validation_and_cleanup(client: TestClient) -> None:
    pet_one = create_pet(client, "豆豆")
    pet_two = create_pet(client, "团团")
    occurred_on = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    record_response = client.post(
        "/api/v1/records",
        json={"pet_id": pet_one, "record_type": "bath", "occurred_on": occurred_on},
    )
    assert record_response.status_code == 201
    record_id = record_response.json()["id"]

    missing_record = client.post(
        "/api/v1/reminders",
        json={
            "pet_id": pet_one,
            "title": "不存在的来源",
            "due_on": occurred_on,
            "source_record_id": "00000000-0000-0000-0000-000000000123",
        },
    )
    assert missing_record.status_code == 404
    assert missing_record.json()["error"]["code"] == "RECORD_NOT_FOUND"

    mismatch = client.post(
        "/api/v1/reminders",
        json={
            "pet_id": pet_two,
            "title": "来源不匹配",
            "due_on": occurred_on,
            "source_record_id": record_id,
        },
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["error"]["code"] == "VALIDATION_ERROR"

    reminder = client.post(
        "/api/v1/reminders",
        json={
            "pet_id": pet_one,
            "title": "来源已关联",
            "due_on": occurred_on,
            "source_record_id": record_id,
        },
    )
    assert reminder.status_code == 201
    reminder_id = reminder.json()["id"]

    moved_pet = client.patch(
        f"/api/v1/reminders/{reminder_id}", json={"pet_id": pet_two}
    )
    assert moved_pet.status_code == 422
    clear_source_and_move = client.patch(
        f"/api/v1/reminders/{reminder_id}",
        json={"pet_id": pet_two, "source_record_id": None},
    )
    assert clear_source_and_move.status_code == 200
    assert clear_source_and_move.json()["source_record_id"] is None

    record_again = client.post(
        "/api/v1/records",
        json={"pet_id": pet_two, "record_type": "bath", "occurred_on": occurred_on},
    )
    reminder_again = client.post(
        "/api/v1/reminders",
        json={
            "pet_id": pet_two,
            "title": "来源删除后解除",
            "due_on": occurred_on,
            "source_record_id": record_again.json()["id"],
        },
    )
    assert reminder_again.status_code == 201
    assert (
        client.delete(f"/api/v1/records/{record_again.json()['id']}").status_code == 204
    )
    after_record_delete = client.get(f"/api/v1/reminders/{reminder_again.json()['id']}")
    assert after_record_delete.status_code == 200
    assert after_record_delete.json()["source_record_id"] is None


def test_reminder_due_group_boundaries() -> None:
    today = date(2026, 11, 3)
    assert reminder_due_group(today - timedelta(days=1), "pending", today) == "overdue"
    assert reminder_due_group(today, "pending", today) == "today"
    assert reminder_due_group(today + timedelta(days=1), "pending", today) == "upcoming"
    assert reminder_due_group(today + timedelta(days=7), "pending", today) == "upcoming"
    assert reminder_due_group(today + timedelta(days=8), "pending", today) == "later"
    assert reminder_due_group(today, "completed", today) is None
    assert reminder_due_group(today, "cancelled", today) is None
