from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import DEFAULT_USER_ID, Pet, User
from app.db.session import get_db, init_db
from app.main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    database_url = URL.create("sqlite", database=str(tmp_path / "pets.db"))
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


def test_pet_crud_persists_across_requests(client: TestClient, tmp_path: Path) -> None:
    assert client.get("/api/v1/pets").json() == []

    created_response = client.post(
        "/api/v1/pets",
        json={
            "name": "  豆豆  ",
            "species": "dog",
            "breed": "金毛",
            "birthday": "2023-05-01",
            "notes": "对鸡肉过敏",
        },
    )
    assert created_response.status_code == 201
    pet = created_response.json()
    assert pet["name"] == "豆豆"
    assert pet["species"] == "dog"
    assert pet["breed"] == "金毛"
    assert pet["birthday"] == "2023-05-01"
    assert pet["notes"] == "对鸡肉过敏"
    assert set(pet) == {
        "id",
        "name",
        "species",
        "other_species",
        "breed",
        "birthday",
        "notes",
        "created_at",
        "updated_at",
    }
    assert pet["created_at"].endswith("Z")

    pet_id = pet["id"]
    assert client.get(f"/api/v1/pets/{pet_id}").json() == pet
    assert client.get("/api/v1/pets").json() == [pet]

    reopened_engine = create_engine(
        URL.create("sqlite", database=str(tmp_path / "pets.db"))
    )
    with Session(reopened_engine) as session:
        assert session.scalar(select(Pet.id)) == pet_id
        pet_user_id = session.scalar(select(Pet.user_id))
        demo_user = session.get(User, DEFAULT_USER_ID)
        assert pet_user_id == DEFAULT_USER_ID
        assert demo_user is not None
        assert demo_user.display_name == "本地演示用户"
    reopened_engine.dispose()

    updated_response = client.patch(
        f"/api/v1/pets/{pet_id}",
        json={"name": "小豆", "notes": None},
    )
    assert updated_response.status_code == 200
    assert updated_response.json()["name"] == "小豆"
    assert updated_response.json()["notes"] is None
    assert updated_response.json()["breed"] == "金毛"

    deleted_response = client.delete(f"/api/v1/pets/{pet_id}")
    assert deleted_response.status_code == 204
    assert deleted_response.content == b""
    assert client.get("/api/v1/pets").json() == []


def test_unknown_birthday_can_be_recorded_as_a_note(client: TestClient) -> None:
    response = client.post(
        "/api/v1/pets",
        json={
            "name": "豆豆",
            "species": "dog",
            "birthday": None,
            "notes": "约 3 岁",
        },
    )

    assert response.status_code == 201
    assert response.json()["birthday"] is None
    assert response.json()["notes"] == "约 3 岁"
    assert "age" not in response.json()


@pytest.mark.parametrize(
    "payload",
    [
        {"name": " ", "species": "dog"},
        {"name": "豆豆", "species": "bird"},
        {"name": "豆豆", "species": "dog", "unknown": "value"},
        {"name": "豆豆", "species": "dog", "age": 2},
        {"name": "豆豆", "species": "dog", "health_notes": "对鸡肉过敏"},
        {
            "name": "豆豆",
            "species": "dog",
            "birthday": (date.today() + timedelta(days=1)).isoformat(),
        },
    ],
)
def test_invalid_create_returns_contract_error(
    client: TestClient, payload: dict[str, object]
) -> None:
    response = client.post("/api/v1/pets", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["request_id"]


@pytest.mark.parametrize("payload", [{}, {"name": None}, {"species": None}])
def test_invalid_patch_returns_contract_error(
    client: TestClient, payload: dict[str, object]
) -> None:
    response = client.patch(
        "/api/v1/pets/00000000-0000-0000-0000-000000000001",
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_invalid_json_and_missing_pet_return_contract_errors(
    client: TestClient,
) -> None:
    invalid_json = client.post(
        "/api/v1/pets",
        content=b"{",
        headers={"content-type": "application/json"},
    )
    assert invalid_json.status_code == 400
    assert invalid_json.json()["error"]["code"] == "BAD_REQUEST"

    missing_pet = client.get("/api/v1/pets/00000000-0000-0000-0000-000000000001")
    assert missing_pet.status_code == 404
    assert missing_pet.json()["error"]["code"] == "PET_NOT_FOUND"


def test_init_db_migrates_existing_pet_table(tmp_path: Path) -> None:
    engine = create_engine(
        URL.create("sqlite", database=str(tmp_path / "legacy-pets.db"))
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE pets ("
                "id VARCHAR(36) PRIMARY KEY, "
                "name VARCHAR(50) NOT NULL, "
                "species VARCHAR(10) NOT NULL, "
                "breed VARCHAR(100), "
                "birthday DATE, "
                "notes TEXT, "
                "created_at DATETIME NOT NULL, "
                "updated_at DATETIME NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO pets "
                "(id, name, species, created_at, updated_at) "
                "VALUES (:id, :name, :species, :created_at, :updated_at)"
            ),
            {
                "id": "00000000-0000-0000-0000-000000000123",
                "name": "迁移测试",
                "species": "cat",
                "created_at": "2026-11-02 00:00:00",
                "updated_at": "2026-11-02 00:00:00",
            },
        )

    init_db(engine.url.render_as_string(hide_password=False))

    with Session(engine) as session:
        migrated_pet = session.get(Pet, "00000000-0000-0000-0000-000000000123")
        assert migrated_pet is not None
        assert migrated_pet.name == "迁移测试"
        assert migrated_pet.user_id == DEFAULT_USER_ID
        assert session.get(User, DEFAULT_USER_ID) is not None
    engine.dispose()


def test_other_species_always_present_in_read_response(client: TestClient) -> None:
    response = client.post("/api/v1/pets", json={"name": "毛毛", "species": "other"})

    assert response.status_code == 201
    assert response.json()["other_species"] is None
    assert client.get("/api/v1/pets").json()[0]["other_species"] is None


# P2-1 过渡：写入路径未开放，other_species 在 PetCreate/PetUpdate 中是未知
# 字段（extra="forbid"）→ 422。这里刻意使用 species=other + other_species=兔
# ——开放写入后该组合将合法，因此 422 只能来自"写入路径未开放"；若用
# dog + 非空 other_species，最终联合校验下同样 422，两种原因无法区分。
# P2-1 实施 PR 开放写入路径后：把下列 POST/PATCH 两例改为成功持久化用例，
# 并按契约草案补 dog/cat 携带非空、互切未显式清空等联合校验 422 用例
# （错误消息与未知字段拒绝区分）。
def test_other_species_write_path_not_open_yet(client: TestClient) -> None:
    response = client.post(
        "/api/v1/pets",
        json={"name": "豆豆", "species": "other", "other_species": "兔"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert client.get("/api/v1/pets").json() == []

    created = client.post("/api/v1/pets", json={"name": "毛毛", "species": "other"})
    assert created.status_code == 201
    pet_id = created.json()["id"]
    before = client.get(f"/api/v1/pets/{pet_id}").json()

    patched = client.patch(
        f"/api/v1/pets/{pet_id}",
        json={"species": "other", "other_species": "兔"},
    )
    assert patched.status_code == 422
    assert patched.json()["error"]["code"] == "VALIDATION_ERROR"
    assert client.get(f"/api/v1/pets/{pet_id}").json() == before
