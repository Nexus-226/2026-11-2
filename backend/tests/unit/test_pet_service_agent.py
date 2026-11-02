from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import URL, create_engine
from sqlalchemy.orm import Session

from app.agent.runtime import AgentRuntime
from app.agent.schemas import ToolCallRequest
from app.agent.tools import build_default_registry
from app.db.session import init_db
from app.schemas.pet import PetCreate, PetRead
from app.services.pet_service import BoundPetService, create_pet


def test_bound_service_uses_session_and_maps_missing_pet_for_agent(
    tmp_path: Path,
) -> None:
    database_url = URL.create("sqlite", database=str(tmp_path / "agent-pets.db"))
    engine = create_engine(database_url)
    init_db(database_url.render_as_string(hide_password=False))

    try:
        with Session(engine) as session:
            created_pet = create_pet(
                session,
                PetCreate(
                    name="豆豆",
                    species="dog",
                    birthday=None,
                    notes="约 3 岁",
                ),
            )
            service = BoundPetService(session)
            runtime = AgentRuntime(build_default_registry(service))

            found = runtime.run_tools(
                [
                    ToolCallRequest(
                        name="get_pet_profile",
                        args={"pet_id": created_pet.id},
                    )
                ]
            )[0]
            assert found.status == "success"
            assert isinstance(found.data, PetRead)
            assert found.data.id == UUID(created_pet.id)
            assert found.data.birthday is None
            assert found.data.notes == "约 3 岁"

            missing_pet_id = uuid4()
            assert service.get_pet(missing_pet_id) is None
            missing = runtime.run_tools(
                [
                    ToolCallRequest(
                        name="get_pet_profile",
                        args={"pet_id": str(missing_pet_id)},
                    )
                ]
            )[0]
            assert missing.status == "error"
            assert missing.error_code == "PET_NOT_FOUND"

            listed = runtime.run_tools([ToolCallRequest(name="list_pets", args={})])[0]
            assert listed.status == "success"
            assert len(listed.data) == 1
            assert isinstance(listed.data[0], PetRead)
    finally:
        engine.dispose()
