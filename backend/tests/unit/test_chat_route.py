from collections.abc import Iterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.agent.chat import ChatReply
from app.agent.chat import run_chat as actual_run_chat
from app.agent.providers.base import ProviderTurn
from app.agent.providers.mock import MockProvider
from app.agent.schemas import ToolCallRequest
from app.agent.service_protocol import PetService
from app.db.models import ChatMessage, ChatSession
from app.db.session import get_db, init_db
from app.main import app
from app.schemas.chat import ChatRequest
from app.services.pet_service import BoundPetService


@pytest.fixture
def chat_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, Engine]]:
    database_url = URL.create("sqlite", database=str(tmp_path / "chat.db"))
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
            yield test_client, engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_chat_route_runs_agent_and_persists_turn(
    chat_client: tuple[TestClient, Engine], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, engine = chat_client
    pet_response = client.post(
        "/api/v1/pets",
        json={"name": "豆豆", "species": "dog"},
    )
    assert pet_response.status_code == 201
    pet_id = pet_response.json()["id"]

    service_instances: list[object] = []

    def run_with_script(
        message: str, requested_pet_id: UUID | None, service: PetService
    ) -> ChatReply:
        assert message == "豆豆应该怎么护理？"
        assert requested_pet_id == UUID(pet_id)
        service_instances.append(service)
        return actual_run_chat(
            message,
            requested_pet_id,
            service,
            provider=MockProvider(
                [
                    ProviderTurn(
                        tool_call=ToolCallRequest(
                            name="get_pet_profile",
                            args={"pet_id": pet_id},
                        )
                    ),
                    ProviderTurn(reply="请根据豆豆的具体情况安排护理。"),
                ]
            ),
        )

    monkeypatch.setattr("app.api.routes.chat.run_chat", run_with_script)
    response = client.post(
        "/api/v1/chat",
        json={"message": "  豆豆应该怎么护理？  ", "pet_id": pet_id},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["reply"] == "请根据豆豆的具体情况安排护理。"
    assert result["tool_calls"] == [{"name": "get_pet_profile", "status": "success"}]
    assert len(service_instances) == 1
    assert isinstance(service_instances[0], BoundPetService)

    with Session(engine) as session:
        messages = list(
            session.scalars(
                select(ChatMessage).order_by(ChatMessage.created_at, ChatMessage.role)
            )
        )
        assert [message.role for message in messages] == ["user", "assistant"]
        assistant_message = next(
            message for message in messages if message.role == "assistant"
        )
        user_message = next(message for message in messages if message.role == "user")
        assert assistant_message.id == result["message_id"]
        assert assistant_message.tool_calls == result["tool_calls"]
        assert user_message.content == "豆豆应该怎么护理？"
        assert user_message.pet_id == pet_id
        assert session.scalar(select(ChatSession.id)) == result["session_id"]


def test_chat_route_returns_pet_not_found_instead_of_internal_error(
    chat_client: tuple[TestClient, Engine], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, engine = chat_client

    def unexpected_run_chat(*args: object, **kwargs: object) -> None:
        pytest.fail("run_chat must not run when the requested pet does not exist")

    monkeypatch.setattr("app.api.routes.chat.run_chat", unexpected_run_chat)
    response = client.post(
        "/api/v1/chat",
        json={"message": "请介绍一下这只宠物", "pet_id": str(uuid4())},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PET_NOT_FOUND"
    with Session(engine) as session:
        assert session.scalar(select(ChatSession.id)) is None


def test_chat_route_rejects_unknown_session(
    chat_client: tuple[TestClient, Engine],
) -> None:
    client, _ = chat_client
    response = client.post(
        "/api/v1/chat",
        json={"message": "你好", "session_id": str(uuid4())},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_chat_route_reuses_existing_session(
    chat_client: tuple[TestClient, Engine],
) -> None:
    client, _ = chat_client
    first_response = client.post("/api/v1/chat", json={"message": "你好"})
    assert first_response.status_code == 200
    first_result = first_response.json()

    second_response = client.post(
        "/api/v1/chat",
        json={"message": "再见", "session_id": first_result["session_id"]},
    )

    assert second_response.status_code == 200
    second_result = second_response.json()
    assert second_result["session_id"] == first_result["session_id"]
    assert second_result["message_id"] != first_result["message_id"]


def test_chat_request_strips_message_and_rejects_blank_content() -> None:
    response = ChatRequest(message="  hello  ")
    assert response.message == "hello"
    with pytest.raises(ValueError):
        ChatRequest(message="   ")
    assert len(ChatRequest(message="a" * 4000).message) == 4000
    with pytest.raises(ValueError):
        ChatRequest(message="a" * 4001)
