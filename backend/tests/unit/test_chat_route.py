from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
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
from app.agent.schemas import ChatHistoryMessage, ToolCallRequest
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

    from app.api.routes.chat import get_llm_provider

    monkeypatch.setattr("app.main.init_db", lambda: None)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_provider] = lambda: MockProvider()
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
    received_histories: list[list[ChatHistoryMessage] | None] = []

    def run_with_script(
        message: str,
        requested_pet_id: UUID | None,
        service: PetService,
        record_service: object = None,
        reminder_service: object = None,
        nearby_service: object = None,
        provider: object = None,
        history: list[ChatHistoryMessage] | None = None,
    ) -> ChatReply:
        assert message == "豆豆应该怎么护理？"
        assert requested_pet_id == UUID(pet_id)
        service_instances.append(service)
        received_histories.append(history)
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
    assert received_histories == [[]]

    with Session(engine) as session:
        messages = list(
            session.scalars(select(ChatMessage).order_by(ChatMessage.sequence))
        )
        assert [message.role for message in messages] == ["user", "assistant"]
        assert [message.sequence for message in messages] == [1, 2]
        assistant_message = next(
            message for message in messages if message.role == "assistant"
        )
        user_message = next(message for message in messages if message.role == "user")
        assert assistant_message.id == result["message_id"]
        assert assistant_message.tool_calls == result["tool_calls"]
        assert user_message.content == "豆豆应该怎么护理？"
        assert user_message.pet_id == pet_id
        assert session.scalar(select(ChatSession.id)) == result["session_id"]


def test_chat_route_registers_record_tool_with_real_service(
    chat_client: tuple[TestClient, Engine],
) -> None:
    client, _ = chat_client
    pet_id = client.post(
        "/api/v1/pets", json={"name": "豆豆", "species": "dog"}
    ).json()["id"]
    created = client.post(
        "/api/v1/records",
        json={
            "pet_id": pet_id,
            "record_type": "deworming",
            "occurred_on": "2026-10-20",
        },
    )
    assert created.status_code == 201

    from app.api.routes.chat import get_llm_provider

    app.dependency_overrides[get_llm_provider] = lambda: MockProvider(
        [
            ProviderTurn(
                tool_call=ToolCallRequest(
                    name="list_pet_records",
                    args={"record_type": "deworming"},
                )
            ),
            ProviderTurn(reply="上次驱虫是 2026-10-20。"),
        ]
    )

    response = client.post(
        "/api/v1/chat",
        json={"message": "上次什么时候驱虫？", "pet_id": pet_id},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["tool_calls"] == [{"name": "list_pet_records", "status": "success"}]
    assert result["reply"] == "上次驱虫是 2026-10-20。"


def test_chat_route_registers_reminder_tool_with_real_service(
    chat_client: tuple[TestClient, Engine],
) -> None:
    client, _ = chat_client
    pet_id = client.post(
        "/api/v1/pets", json={"name": "豆豆", "species": "dog"}
    ).json()["id"]
    created = client.post(
        "/api/v1/reminders",
        json={"pet_id": pet_id, "title": "下次驱虫", "due_on": "2026-11-09"},
    )
    assert created.status_code == 201

    from app.api.routes.chat import get_llm_provider

    app.dependency_overrides[get_llm_provider] = lambda: MockProvider(
        [
            ProviderTurn(
                tool_call=ToolCallRequest(
                    name="list_pet_reminders",
                    args={"status": "pending"},
                )
            ),
            ProviderTurn(reply="这周有一次驱虫待办。"),
        ]
    )

    response = client.post(
        "/api/v1/chat",
        json={"message": "这周有哪些安排？", "pet_id": pet_id},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["tool_calls"] == [{"name": "list_pet_reminders", "status": "success"}]
    assert result["reply"] == "这周有一次驱虫待办。"


def test_chat_route_registers_nearby_tool_with_real_service(
    chat_client: tuple[TestClient, Engine],
) -> None:
    client, _ = chat_client
    from app.api.routes.chat import get_llm_provider

    app.dependency_overrides[get_llm_provider] = lambda: MockProvider(
        [
            ProviderTurn(
                tool_call=ToolCallRequest(
                    name="search_nearby_pet_services",
                    args={"lat": 39.9001, "lng": 116.4001, "type": "pet_hospital"},
                )
            ),
            ProviderTurn(reply="附近暂时没有匹配的宠物医院。"),
        ]
    )

    response = client.post(
        "/api/v1/chat",
        json={"message": "附近有哪些宠物医院？"},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["tool_calls"] == [
        {"name": "search_nearby_pet_services", "status": "success"}
    ]
    assert result["reply"] == "附近暂时没有匹配的宠物医院。"


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
    chat_client: tuple[TestClient, Engine], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = chat_client
    histories: list[list[ChatHistoryMessage]] = []

    def run_with_history(
        message: str,
        requested_pet_id: UUID | None,
        service: PetService,
        record_service: object = None,
        reminder_service: object = None,
        nearby_service: object = None,
        provider: object = None,
        history: list[ChatHistoryMessage] | None = None,
    ) -> ChatReply:
        histories.append(history or [])
        return ChatReply(reply=f"回复：{message}")

    monkeypatch.setattr("app.api.routes.chat.run_chat", run_with_history)
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
    assert histories == [
        [],
        [
            ChatHistoryMessage(role="user", content="你好"),
            ChatHistoryMessage(role="assistant", content="回复：你好"),
        ],
    ]


def test_chat_route_filters_history_by_session_and_current_pet(
    chat_client: tuple[TestClient, Engine], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = chat_client
    histories: list[list[tuple[str, str]]] = []

    def run_with_history(
        message: str,
        requested_pet_id: UUID | None,
        service: PetService,
        record_service: object = None,
        reminder_service: object = None,
        nearby_service: object = None,
        provider: object = None,
        history: list[ChatHistoryMessage] | None = None,
    ) -> ChatReply:
        assert all(isinstance(item, ChatHistoryMessage) for item in history or [])
        histories.append([(item.role, item.content) for item in history or []])
        return ChatReply(reply=f"回复：{message}")

    monkeypatch.setattr("app.api.routes.chat.run_chat", run_with_history)
    pet_a = client.post("/api/v1/pets", json={"name": "A", "species": "cat"}).json()[
        "id"
    ]
    pet_b = client.post("/api/v1/pets", json={"name": "B", "species": "dog"}).json()[
        "id"
    ]

    first = client.post(
        "/api/v1/chat", json={"message": "A 的信息", "pet_id": pet_a}
    ).json()
    client.post("/api/v1/chat", json={"message": "另一会话", "pet_id": pet_b})
    client.post(
        "/api/v1/chat",
        json={"message": "通用信息", "session_id": first["session_id"]},
    )
    client.post(
        "/api/v1/chat",
        json={
            "message": "关于 B 的问题",
            "session_id": first["session_id"],
            "pet_id": pet_b,
        },
    )

    assert histories == [
        [],
        [],
        [],
        [("user", "通用信息"), ("assistant", "回复：通用信息")],
    ]


def test_chat_route_returns_conflict_without_saving_stale_turn(
    chat_client: tuple[TestClient, Engine],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, engine = chat_client

    def run_with_reply(
        message: str,
        requested_pet_id: UUID | None,
        service: PetService,
        record_service: object = None,
        reminder_service: object = None,
        nearby_service: object = None,
        provider: object = None,
        history: list[ChatHistoryMessage] | None = None,
    ) -> ChatReply:
        return ChatReply(reply=f"回复：{message}")

    monkeypatch.setattr("app.api.routes.chat.run_chat", run_with_reply)
    first_response = client.post("/api/v1/chat", json={"message": "第一轮"})
    assert first_response.status_code == 200

    from app.services.chat_service import ChatTurnConflict

    def reject_stale_turn(*args: object, **kwargs: object) -> ChatMessage:
        raise ChatTurnConflict

    monkeypatch.setattr("app.services.chat_service.save_chat_turn", reject_stale_turn)
    response = client.post(
        "/api/v1/chat",
        json={
            "message": "并发旧轮次",
            "session_id": first_response.json()["session_id"],
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "HTTP_ERROR"
    with Session(engine) as session:
        messages = list(session.scalars(select(ChatMessage)))
    assert len(messages) == 2


def test_chat_route_serializes_same_session_requests(
    chat_client: tuple[TestClient, Engine], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = chat_client
    first_started = Event()
    release_first = Event()
    second_started = Event()
    histories: dict[str, list[tuple[str, str]]] = {}

    def run_with_history(
        message: str,
        requested_pet_id: UUID | None,
        service: PetService,
        record_service: object = None,
        reminder_service: object = None,
        nearby_service: object = None,
        provider: object = None,
        history: list[ChatHistoryMessage] | None = None,
    ) -> ChatReply:
        histories[message] = [(item.role, item.content) for item in history or []]
        if message == "阻塞中的请求":
            first_started.set()
            if not release_first.wait(timeout=5):
                raise TimeoutError("test did not release first request")
        elif message == "排队请求":
            second_started.set()
        return ChatReply(reply=f"回复：{message}")

    monkeypatch.setattr("app.api.routes.chat.run_chat", run_with_history)
    initial = client.post("/api/v1/chat", json={"message": "初始消息"}).json()
    session_id = initial["session_id"]

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            client.post,
            "/api/v1/chat",
            json={"message": "阻塞中的请求", "session_id": session_id},
        )
        assert first_started.wait(timeout=5)
        second = executor.submit(
            client.post,
            "/api/v1/chat",
            json={"message": "排队请求", "session_id": session_id},
        )
        assert not second_started.wait(timeout=0.1)
        release_first.set()
        assert first.result(timeout=5).status_code == 200
        assert second.result(timeout=5).status_code == 200

    assert histories["阻塞中的请求"] == [
        ("user", "初始消息"),
        ("assistant", "回复：初始消息"),
    ]
    assert histories["排队请求"] == [
        ("user", "初始消息"),
        ("assistant", "回复：初始消息"),
        ("user", "阻塞中的请求"),
        ("assistant", "回复：阻塞中的请求"),
    ]


def test_chat_request_strips_message_and_rejects_blank_content() -> None:
    response = ChatRequest(message="  hello  ")
    assert response.message == "hello"
    with pytest.raises(ValueError):
        ChatRequest(message="   ")
    assert len(ChatRequest(message="a" * 4000).message) == 4000
    with pytest.raises(ValueError):
        ChatRequest(message="a" * 4001)


@pytest.mark.parametrize(
    ("code", "status_code"),
    [
        ("UPSTREAM_ERROR", 502),
        ("SERVICE_UNAVAILABLE", 503),
        ("UPSTREAM_TIMEOUT", 504),
    ],
)
def test_chat_route_maps_provider_error_to_upstream_status(
    chat_client: tuple[TestClient, Engine],
    monkeypatch: pytest.MonkeyPatch,
    code: str,
    status_code: int,
) -> None:
    from app.agent.errors import ProviderError

    client, engine = chat_client

    def fail_chat(message: str, *args: object, **kwargs: object) -> ChatReply:
        if message == "失败":
            raise ProviderError(code, "模型服务不可用")
        return ChatReply(reply="成功")

    monkeypatch.setattr("app.api.routes.chat.run_chat", fail_chat)
    first_response = client.post("/api/v1/chat", json={"message": "你好"})
    assert first_response.status_code == 200
    response = client.post(
        "/api/v1/chat",
        json={"message": "失败", "session_id": first_response.json()["session_id"]},
    )

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == code
    with Session(engine) as session:
        messages = list(session.scalars(select(ChatMessage)))
    assert len(messages) == 2
