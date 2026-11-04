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
from app.schemas.pet import (
    ERROR_OTHER_SPECIES_NOT_ALLOWED,
    ERROR_OTHER_SPECIES_NOT_CLEARED,
)


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
        legacy_rows = [
            {
                "id": "00000000-0000-0000-0000-000000000123",
                "name": "迁移测试",
                "species": "cat",
            },
            {
                "id": "00000000-0000-0000-0000-000000000124",
                "name": "豆豆",
                "species": "dog",
            },
            {
                "id": "00000000-0000-0000-0000-000000000125",
                "name": "团团",
                "species": "other",
            },
        ]
        for row in legacy_rows:
            connection.execute(
                text(
                    "INSERT INTO pets "
                    "(id, name, species, created_at, updated_at) "
                    "VALUES (:id, :name, :species, :created_at, :updated_at)"
                ),
                {
                    **row,
                    "created_at": "2026-11-02 00:00:00",
                    "updated_at": "2026-11-02 00:00:00",
                },
            )

    init_db(engine.url.render_as_string(hide_password=False))

    with Session(engine) as session:
        # P2-1：存量 dog/cat/other 一律回填 other_species = null，
        # 原记录及已有字段保留，不从 breed/notes 推断具体物种。
        for row in legacy_rows:
            migrated_pet = session.get(Pet, row["id"])
            assert migrated_pet is not None
            assert migrated_pet.name == row["name"]
            assert migrated_pet.species == row["species"]
            assert migrated_pet.other_species is None
            assert migrated_pet.user_id == DEFAULT_USER_ID
        assert session.get(User, DEFAULT_USER_ID) is not None
    engine.dispose()


def test_other_species_always_present_in_read_response(client: TestClient) -> None:
    response = client.post("/api/v1/pets", json={"name": "毛毛", "species": "other"})

    assert response.status_code == 201
    assert response.json()["other_species"] is None
    assert client.get("/api/v1/pets").json()[0]["other_species"] is None


def _create_pet(client: TestClient, name: str, species: str, **extra: object) -> str:
    response = client.post(
        "/api/v1/pets", json={"name": name, "species": species, **extra}
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_other_species_write_and_clear_round_trip(
    client: TestClient, tmp_path: Path
) -> None:
    created = client.post(
        "/api/v1/pets",
        json={"name": "团团", "species": "other", "other_species": " 兔 "},
    )
    assert created.status_code == 201
    pet = created.json()
    assert pet["other_species"] == "兔"

    pet_id = pet["id"]
    assert client.get(f"/api/v1/pets/{pet_id}").json()["other_species"] == "兔"
    assert client.get("/api/v1/pets").json()[0]["other_species"] == "兔"

    # PATCH 省略 other_species 表示不修改。
    renamed = client.patch(f"/api/v1/pets/{pet_id}", json={"name": "团团"})
    assert renamed.status_code == 200
    assert renamed.json()["species"] == "other"
    assert renamed.json()["other_species"] == "兔"

    reopened_engine = create_engine(
        URL.create("sqlite", database=str(tmp_path / "pets.db"))
    )
    with Session(reopened_engine) as session:
        stored = session.get(Pet, pet_id)
        assert stored is not None
        assert stored.other_species == "兔"
    reopened_engine.dispose()

    retitled = client.patch(f"/api/v1/pets/{pet_id}", json={"other_species": "仓鼠"})
    assert retitled.status_code == 200
    assert retitled.json()["other_species"] == "仓鼠"

    cleared = client.patch(f"/api/v1/pets/{pet_id}", json={"other_species": None})
    assert cleared.status_code == 200
    assert cleared.json()["other_species"] is None


def test_patch_species_pair_contract_seven_cases(client: TestClient) -> None:
    other_rabbit = _create_pet(client, "团团", "other", other_species="兔")
    dog_pet = _create_pet(client, "豆豆", "dog")
    cat_pet = _create_pet(client, "咪咪", "cat")

    # 1. 原资料 other/兔，PATCH {"name":"团团"} → 保留 other/兔。
    kept = client.patch(f"/api/v1/pets/{other_rabbit}", json={"name": "团团"})
    assert kept.status_code == 200
    assert kept.json()["species"] == "other"
    assert kept.json()["other_species"] == "兔"

    # 2. PATCH {"other_species":" 荷兰 猪 "} → 去首尾空白、保留内部空白。
    retitled = client.patch(
        f"/api/v1/pets/{other_rabbit}", json={"other_species": " 荷兰 猪 "}
    )
    assert retitled.status_code == 200
    assert retitled.json()["other_species"] == "荷兰 猪"

    # 3. 原资料 dog/null，PATCH {"other_species":"兔"} → 422，原资料不变。
    before_dog = client.get(f"/api/v1/pets/{dog_pet}").json()
    rejected = client.patch(f"/api/v1/pets/{dog_pet}", json={"other_species": "兔"})
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "VALIDATION_ERROR"
    assert rejected.json()["error"]["message"] == ERROR_OTHER_SPECIES_NOT_ALLOWED
    assert client.get(f"/api/v1/pets/{dog_pet}").json() == before_dog

    # 4. 原资料 other/兔，PATCH {"species":"cat"} → 422，省略字段不自动清空。
    before_other = client.get(f"/api/v1/pets/{other_rabbit}").json()
    switched = client.patch(f"/api/v1/pets/{other_rabbit}", json={"species": "cat"})
    assert switched.status_code == 422
    assert switched.json()["error"]["message"] == ERROR_OTHER_SPECIES_NOT_CLEARED
    assert client.get(f"/api/v1/pets/{other_rabbit}").json() == before_other

    # 5. PATCH {"species":"cat","other_species":null} → 保存 cat/null。
    switched_clear = client.patch(
        f"/api/v1/pets/{other_rabbit}", json={"species": "cat", "other_species": None}
    )
    assert switched_clear.status_code == 200
    assert switched_clear.json()["species"] == "cat"
    assert switched_clear.json()["other_species"] is None

    # 6. 原资料 cat/null，PATCH {"species":"other","other_species":"兔"}
    #    → 保存 other/兔。
    to_other = client.patch(
        f"/api/v1/pets/{cat_pet}", json={"species": "other", "other_species": "兔"}
    )
    assert to_other.status_code == 200
    assert to_other.json()["species"] == "other"
    assert to_other.json()["other_species"] == "兔"

    # 7. PATCH {"other_species":"   "} → 全空白等同 null，保存 other/null。
    blanked = client.patch(f"/api/v1/pets/{cat_pet}", json={"other_species": "   "})
    assert blanked.status_code == 200
    assert blanked.json()["species"] == "other"
    assert blanked.json()["other_species"] is None


@pytest.mark.parametrize("species", ["dog", "cat"])
def test_create_rejects_dog_and_cat_with_other_species_value(
    client: TestClient, species: str
) -> None:
    response = client.post(
        "/api/v1/pets",
        json={"name": "豆豆", "species": species, "other_species": "兔"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["message"] == ERROR_OTHER_SPECIES_NOT_ALLOWED
    assert client.get("/api/v1/pets").json() == []


def test_create_other_species_defaults_and_blank_handling(client: TestClient) -> None:
    omitted = client.post("/api/v1/pets", json={"name": "豆豆", "species": "dog"})
    assert omitted.status_code == 201
    assert omitted.json()["other_species"] is None

    blank = client.post(
        "/api/v1/pets",
        json={"name": "毛毛", "species": "other", "other_species": "   "},
    )
    assert blank.status_code == 201
    assert blank.json()["other_species"] is None

    explicit_null = client.post(
        "/api/v1/pets",
        json={"name": "团团", "species": "other", "other_species": None},
    )
    assert explicit_null.status_code == 201
    assert explicit_null.json()["other_species"] is None


@pytest.mark.parametrize(
    "value",
    [123, True, ["兔"], {"species": "兔"}],
)
def test_other_species_only_accepts_string_or_null(
    client: TestClient, value: object
) -> None:
    response = client.post(
        "/api/v1/pets",
        json={"name": "团团", "species": "other", "other_species": value},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert client.get("/api/v1/pets").json() == []


def test_other_species_length_counts_unicode_code_points(client: TestClient) -> None:
    fifty = "𠮷" * 50
    created = client.post(
        "/api/v1/pets",
        json={"name": "团团", "species": "other", "other_species": fifty},
    )
    assert created.status_code == 201
    assert created.json()["other_species"] == fifty
    pet_id = created.json()["id"]

    # 长度按标准化后（去首尾空白）的码点计数：前后各加一个空格仍为 50。
    padded = client.patch(
        f"/api/v1/pets/{pet_id}", json={"other_species": f" {fifty} "}
    )
    assert padded.status_code == 200
    assert padded.json()["other_species"] == fifty

    fifty_one = "𠮷" * 51
    too_long = client.patch(f"/api/v1/pets/{pet_id}", json={"other_species": fifty_one})
    assert too_long.status_code == 422
    assert too_long.json()["error"]["code"] == "VALIDATION_ERROR"
    assert too_long.json()["error"]["message"] == (
        "other_species must be at most 50 characters"
    )
    # 失败不落库：原值保持不变。
    assert client.get(f"/api/v1/pets/{pet_id}").json()["other_species"] == fifty

    create_too_long = client.post(
        "/api/v1/pets",
        json={"name": "团团", "species": "other", "other_species": fifty_one},
    )
    assert create_too_long.status_code == 422
    assert len(client.get("/api/v1/pets").json()) == 1
