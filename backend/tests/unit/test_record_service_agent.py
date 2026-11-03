from datetime import date
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import Session

from app.db.session import init_db
from app.schemas.pet import PetCreate
from app.schemas.record import RecordCreate, RecordRead
from app.services.pet_service import create_pet
from app.services.record_service import BoundRecordService, create_record


def test_bound_record_service_maps_and_filters_records_for_agent(
    tmp_path: Path,
) -> None:
    database_url = URL.create("sqlite", database=str(tmp_path / "agent-records.db"))
    engine = create_engine(database_url)
    init_db(database_url.render_as_string(hide_password=False))

    try:
        with Session(engine) as session:
            created_pet = create_pet(
                session,
                PetCreate(name="豆豆", species="dog", birthday=None, notes=None),
            )
            pet_id = UUID(created_pet.id)
            create_record(
                session,
                RecordCreate(
                    pet_id=pet_id,
                    record_type="weight",
                    occurred_on=date(2026, 10, 20),
                    weight_kg=4.5,
                ),
            )
            create_record(
                session,
                RecordCreate(
                    pet_id=pet_id,
                    record_type="deworming",
                    occurred_on=date(2026, 10, 28),
                ),
            )
            create_record(
                session,
                RecordCreate(
                    pet_id=None,
                    record_type="bath",
                    occurred_on=date(2026, 10, 25),
                    name="洗澡",
                ),
            )
            service = BoundRecordService(session)

            listed = service.list_records()
            assert len(listed) == 3
            assert all(isinstance(record, RecordRead) for record in listed)
            weight = next(record for record in listed if record.record_type == "weight")
            assert weight.pet_id == pet_id
            assert weight.weight_kg == 4.5

            for_pet = service.list_records(pet_id=pet_id)
            assert {record.record_type for record in for_pet} == {
                "weight",
                "deworming",
            }
            assert all(record.pet_id == pet_id for record in for_pet)

            unlinked = service.list_records(unlinked=True)
            assert {record.record_type for record in unlinked} == {"bath"}
            assert all(record.pet_id is None for record in unlinked)

            by_type = service.list_records(record_type="weight")
            assert [record.record_type for record in by_type] == ["weight"]

            in_range = service.list_records(
                from_date=date(2026, 10, 21), to_date=date(2026, 10, 28)
            )
            assert {record.record_type for record in in_range} == {
                "deworming",
                "bath",
            }

            assert service.list_records(record_type="vaccine") == []
    finally:
        engine.dispose()


def test_bound_record_service_propagates_pet_not_found_for_agent(
    tmp_path: Path,
) -> None:
    database_url = URL.create(
        "sqlite", database=str(tmp_path / "agent-records-missing-pet.db")
    )
    engine = create_engine(database_url)
    init_db(database_url.render_as_string(hide_password=False))

    try:
        with Session(engine) as session:
            service = BoundRecordService(session)
            with pytest.raises(HTTPException) as exc_info:
                service.list_records(pet_id=uuid4())
            assert exc_info.value.status_code == 404
            detail = exc_info.value.detail
            assert isinstance(detail, dict)
            assert detail["code"] == "PET_NOT_FOUND"
    finally:
        engine.dispose()
