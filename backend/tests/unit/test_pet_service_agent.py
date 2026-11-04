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
            assert found.data.other_species is None

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

            # P2-1：具体物种经真实 Service → 工具序列化后仍带字段与值，
            # 而非只检查类型定义。
            rabbit = create_pet(
                session,
                PetCreate(name="团团", species="other", other_species="兔"),
            )
            listed = runtime.run_tools([ToolCallRequest(name="list_pets", args={})])[0]
            assert listed.status == "success"
            assert len(listed.data) == 2
            assert isinstance(listed.data[0], PetRead)
            pets_by_id = {str(pet.id): pet for pet in listed.data}
            assert pets_by_id[rabbit.id].other_species == "兔"
            assert pets_by_id[created_pet.id].other_species is None
    finally:
        engine.dispose()
