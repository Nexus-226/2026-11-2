from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from app.agent.chat import MAX_HISTORY_CHARS, MAX_HISTORY_MESSAGES, run_chat
from app.agent.providers.base import ProviderTurn
from app.agent.providers.mock import MockProvider
from app.agent.schemas import ChatHistoryMessage, ToolCallRequest
from app.schemas.pet import PetRead

PET_ID = UUID("b8f34f24-f5cf-4b5c-8d40-073541725a11")


class FakePetService:
    """测试用的宠物 Service，替代 B 尚未提供的真实实现。"""

    def __init__(self, pets: list[PetRead] | None = None) -> None:
        self._pets = {p.id: p for p in (pets or [])}

    def get_pet(self, pet_id: UUID) -> PetRead | None:
        return self._pets.get(pet_id)

    def list_pets(self) -> list[PetRead]:
        return list(self._pets.values())


def _pet() -> PetRead:
    return PetRead(
        id=PET_ID,
        name="豆豆",
        species="dog",
        other_species=None,
        breed="金毛",
        birthday=date(2023, 5, 1),
        notes="对鸡肉过敏",
        created_at=datetime(2026, 11, 2, 8, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 11, 2, 8, 0, 0, tzinfo=timezone.utc),
    )


def test_run_chat_calls_tool_then_replies() -> None:
    provider = MockProvider(
        turns=[
            ProviderTurn(
                tool_call=ToolCallRequest(
                    name="get_pet_profile", args={"pet_id": str(PET_ID)}
                )
            ),
            ProviderTurn(reply="已查到豆豆的资料。"),
        ]
    )
    reply = run_chat(
        "豆豆多大了？", PET_ID, FakePetService([_pet()]), provider=provider
    )
    assert reply.reply == "已查到豆豆的资料。"
    assert [t.name for t in reply.tool_calls] == ["get_pet_profile"]
    assert reply.tool_calls[0].status == "success"


def test_run_chat_not_found_is_error() -> None:
    provider = MockProvider(
        turns=[
            ProviderTurn(
                tool_call=ToolCallRequest(
                    name="get_pet_profile", args={"pet_id": str(PET_ID)}
                )
            ),
            ProviderTurn(reply="未找到该宠物。"),
        ]
    )
    reply = run_chat("豆豆多大了？", PET_ID, FakePetService([]), provider=provider)
    assert reply.reply == "未找到该宠物。"
    assert reply.tool_calls[0].status == "error"


def test_run_chat_direct_reply_no_tool() -> None:
    provider = MockProvider(turns=[ProviderTurn(reply="你好！")])
    reply = run_chat("你好", None, FakePetService([]), provider=provider)
    assert reply.reply == "你好！"
    assert reply.tool_calls == []


def test_run_chat_replies_after_three_tool_calls() -> None:
    turns = [
        ProviderTurn(tool_call=ToolCallRequest(name="list_pets", args={}))
        for _ in range(3)
    ]
    turns.append(ProviderTurn(reply="已为你列出宠物。"))
    provider = MockProvider(turns=turns)
    reply = run_chat(
        "我有几只宠物？", None, FakePetService([_pet()]), provider=provider
    )
    assert reply.reply == "已为你列出宠物。"
    assert len(reply.tool_calls) == 3
    assert all(t.status == "success" for t in reply.tool_calls)


def test_run_chat_injects_current_date_into_system_prompt() -> None:
    captured: dict[str, str] = {}

    class CapturingProvider:
        def next_turn(self, **kwargs: object) -> ProviderTurn:
            captured["system_prompt"] = str(kwargs["system_prompt"])
            return ProviderTurn(reply="ok")

    run_chat("你好", None, FakePetService([]), provider=CapturingProvider())
    assert "今天是" in captured["system_prompt"]
    assert (
        datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
        in captured["system_prompt"]
    )


def test_run_chat_injects_week_boundaries() -> None:
    captured: dict[str, str] = {}

    class CapturingProvider:
        def next_turn(self, **kwargs: object) -> ProviderTurn:
            captured["system_prompt"] = str(kwargs["system_prompt"])
            return ProviderTurn(reply="ok")

    run_chat("这周有哪些安排？", None, FakePetService([]), provider=CapturingProvider())
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    next7_end = today + timedelta(days=6)
    assert "“未来七天”指" in captured["system_prompt"]
    assert next7_end.isoformat() in captured["system_prompt"]
    assert "“本周”指" in captured["system_prompt"]
    assert monday.isoformat() in captured["system_prompt"]
    assert sunday.isoformat() in captured["system_prompt"]


def test_run_chat_prompt_marks_no_associated_pet() -> None:
    captured: dict[str, str] = {}

    class CapturingProvider:
        def next_turn(self, **kwargs: object) -> ProviderTurn:
            captured["system_prompt"] = str(kwargs["system_prompt"])
            return ProviderTurn(reply="ok")

    run_chat("它吃什么过敏？", None, FakePetService([]), provider=CapturingProvider())
    assert "当前未关联任何宠物" in captured["system_prompt"]
    assert "不要用全部宠物列表代替" in captured["system_prompt"]


def test_run_chat_prompt_distinguishes_name_and_nickname() -> None:
    captured: dict[str, str] = {}

    class CapturingProvider:
        def next_turn(self, **kwargs: object) -> ProviderTurn:
            captured["system_prompt"] = str(kwargs["system_prompt"])
            return ProviderTurn(reply="ok")

    run_chat(
        "刚才的昵称是什么？",
        PET_ID,
        FakePetService([_pet()]),
        provider=CapturingProvider(),
    )
    assert "不是用户在会话里临时起的昵称" in captured["system_prompt"]
    assert "不得额外声称档案名称" in captured["system_prompt"]


def test_run_chat_prompt_names_associated_pet() -> None:
    captured: dict[str, str] = {}

    class CapturingProvider:
        def next_turn(self, **kwargs: object) -> ProviderTurn:
            captured["system_prompt"] = str(kwargs["system_prompt"])
            return ProviderTurn(reply="ok")

    run_chat(
        "dodo 是什么动物？",
        PET_ID,
        FakePetService([_pet()]),
        provider=CapturingProvider(),
    )
    prompt = captured["system_prompt"]
    assert "豆豆" in prompt
    assert "优先按这只关联宠物理解" in prompt
    assert str(PET_ID) in prompt


def test_run_chat_prompt_labels_other_species_pet() -> None:
    captured: dict[str, str] = {}

    class CapturingProvider:
        def next_turn(self, **kwargs: object) -> ProviderTurn:
            captured["system_prompt"] = str(kwargs["system_prompt"])
            return ProviderTurn(reply="ok")

    pet = _pet().model_copy(update={"species": "other", "other_species": "兔"})
    run_chat(
        "它是什么物种？",
        PET_ID,
        FakePetService([pet]),
        provider=CapturingProvider(),
    )
    assert "具体物种：兔" in captured["system_prompt"]


def test_run_chat_prompt_falls_back_to_id_when_pet_missing() -> None:
    captured: dict[str, str] = {}

    class CapturingProvider:
        def next_turn(self, **kwargs: object) -> ProviderTurn:
            captured["system_prompt"] = str(kwargs["system_prompt"])
            return ProviderTurn(reply="ok")

    run_chat(
        "它是什么动物？",
        PET_ID,
        FakePetService([]),
        provider=CapturingProvider(),
    )
    prompt = captured["system_prompt"]
    assert "名字「" not in prompt
    assert "当前关联宠物 pet_id=" in prompt


def test_run_chat_prompt_references_other_species() -> None:
    captured: dict[str, str] = {}

    class CapturingProvider:
        def next_turn(self, **kwargs: object) -> ProviderTurn:
            captured["system_prompt"] = str(kwargs["system_prompt"])
            return ProviderTurn(reply="ok")

    run_chat(
        "我的宠物是什么物种？",
        None,
        FakePetService([]),
        provider=CapturingProvider(),
    )
    prompt = captured["system_prompt"]
    assert "other_species" in prompt
    assert "未填具体物种" in prompt
    assert "不要默认按猫狗处理" in prompt
    assert "不要编造具体物种" in prompt


def test_run_chat_prompt_limits_nearby_demo_fallback() -> None:
    captured: dict[str, str] = {}

    class CapturingProvider:
        def next_turn(self, **kwargs: object) -> ProviderTurn:
            captured["system_prompt"] = str(kwargs["system_prompt"])
            return ProviderTurn(reply="ok")

    run_chat(
        "附近有哪些宠物医院？",
        None,
        FakePetService([]),
        provider=CapturingProvider(),
    )
    prompt = captured["system_prompt"]
    assert "不得据此判断真实附近有没有服务" in prompt
    assert "不要建议用户重新定位" in prompt
    assert "启用导航" in prompt


def test_run_chat_prompt_forbids_relative_day_counting() -> None:
    captured: dict[str, str] = {}

    class CapturingProvider:
        def next_turn(self, **kwargs: object) -> ProviderTurn:
            captured["system_prompt"] = str(kwargs["system_prompt"])
            return ProviderTurn(reply="ok")

    run_chat(
        "未来七天有哪些安排？",
        None,
        FakePetService([]),
        provider=CapturingProvider(),
    )
    assert "occurred_on" in captured["system_prompt"]
    assert "due_on" in captured["system_prompt"]
    assert "第几天" in captured["system_prompt"]


def test_run_chat_prompt_enforces_readonly() -> None:
    captured: dict[str, str] = {}

    class CapturingProvider:
        def next_turn(self, **kwargs: object) -> ProviderTurn:
            captured["system_prompt"] = str(kwargs["system_prompt"])
            return ProviderTurn(reply="ok")

    run_chat(
        "帮我设置一个提醒。",
        None,
        FakePetService([]),
        provider=CapturingProvider(),
    )
    assert "不能创建或修改提醒" in captured["system_prompt"]
    assert "不要主动提议" in captured["system_prompt"]
    assert "需要我帮您设置提醒吗" in captured["system_prompt"]


class HistoryCapturingProvider:
    def __init__(self) -> None:
        self.history: list[ChatHistoryMessage] | None = None

    def next_turn(self, **kwargs: object) -> ProviderTurn:
        value = kwargs.get("history")
        self.history = value if isinstance(value, list) else None
        return ProviderTurn(reply="ok")


def test_run_chat_passes_history_to_provider() -> None:
    provider = HistoryCapturingProvider()
    history = [
        ChatHistoryMessage(role="user", content="我给猫起了个昵称叫小煤球"),
        ChatHistoryMessage(role="assistant", content="好的，记住了。"),
    ]

    run_chat(
        "刚才那个昵称是什么？",
        None,
        FakePetService([]),
        provider=provider,
        history=history,
    )

    assert provider.history == history


def test_run_chat_truncates_history_to_recent_messages() -> None:
    provider = HistoryCapturingProvider()
    history: list[ChatHistoryMessage] = []
    for index in range(30):
        history.append(ChatHistoryMessage(role="user", content=f"u{index}"))
        history.append(ChatHistoryMessage(role="assistant", content=f"a{index}"))

    run_chat("继续", None, FakePetService([]), provider=provider, history=history)

    assert provider.history is not None
    assert len(provider.history) == MAX_HISTORY_MESSAGES
    assert provider.history[0].role == "user"
    assert provider.history[-1].content == "a29"


def test_run_chat_drops_leading_assistant_from_history() -> None:
    provider = HistoryCapturingProvider()
    history = [ChatHistoryMessage(role="assistant", content="orphan")]
    for index in range(19):
        role = "user" if index % 2 == 0 else "assistant"
        history.append(ChatHistoryMessage(role=role, content=f"m{index}"))

    run_chat("继续", None, FakePetService([]), provider=provider, history=history)

    assert provider.history is not None
    assert provider.history[0].role == "user"


def test_run_chat_drops_trailing_half_round_from_history() -> None:
    provider = HistoryCapturingProvider()
    history = [
        ChatHistoryMessage(role="user", content="u1"),
        ChatHistoryMessage(role="assistant", content="a1"),
        ChatHistoryMessage(role="user", content="没有回复的半轮"),
    ]

    run_chat("继续", None, FakePetService([]), provider=provider, history=history)

    assert provider.history is not None
    assert [item.content for item in provider.history] == ["u1", "a1"]


def test_run_chat_passes_history_only_on_first_turn() -> None:
    class TwoTurnProvider:
        def __init__(self) -> None:
            self.history_per_call: list[object] = []

        def next_turn(self, **kwargs: object) -> ProviderTurn:
            self.history_per_call.append(kwargs.get("history"))
            if len(self.history_per_call) == 1:
                return ProviderTurn(
                    tool_call=ToolCallRequest(name="list_pets", args={})
                )
            return ProviderTurn(reply="完成")

    provider = TwoTurnProvider()
    history = [
        ChatHistoryMessage(role="user", content="上一轮"),
        ChatHistoryMessage(role="assistant", content="上一轮的回答"),
    ]

    run_chat("继续", None, FakePetService([]), provider=provider, history=history)

    assert provider.history_per_call[0] == history
    assert provider.history_per_call[1] is None


def test_run_chat_filters_history_from_other_pets() -> None:
    provider = HistoryCapturingProvider()
    other_pet = uuid4()
    history = [
        ChatHistoryMessage(role="user", content="豆豆的问题", pet_id=PET_ID),
        ChatHistoryMessage(role="assistant", content="豆豆的回答", pet_id=PET_ID),
        ChatHistoryMessage(role="user", content="另一只宠物的问题", pet_id=other_pet),
        ChatHistoryMessage(
            role="assistant", content="另一只宠物的回答", pet_id=other_pet
        ),
    ]

    run_chat(
        "继续", PET_ID, FakePetService([_pet()]), provider=provider, history=history
    )

    assert provider.history is not None
    assert [item.content for item in provider.history] == ["豆豆的问题", "豆豆的回答"]


def test_run_chat_drops_pet_history_when_no_current_pet() -> None:
    provider = HistoryCapturingProvider()
    history = [
        ChatHistoryMessage(role="user", content="豆豆的问题", pet_id=PET_ID),
        ChatHistoryMessage(role="assistant", content="豆豆的回答", pet_id=PET_ID),
        ChatHistoryMessage(role="user", content="不关联宠物的问题"),
        ChatHistoryMessage(role="assistant", content="不关联宠物的回答"),
    ]

    run_chat("继续", None, FakePetService([_pet()]), provider=provider, history=history)

    assert provider.history is not None
    assert [item.content for item in provider.history] == [
        "不关联宠物的问题",
        "不关联宠物的回答",
    ]


def test_run_chat_drops_over_budget_single_round() -> None:
    provider = HistoryCapturingProvider()
    history = [
        ChatHistoryMessage(role="user", content="u" * (MAX_HISTORY_CHARS + 1)),
        ChatHistoryMessage(role="assistant", content="a"),
    ]

    run_chat("继续", None, FakePetService([]), provider=provider, history=history)

    assert provider.history == []


def test_run_chat_ignores_blank_history_messages() -> None:
    provider = HistoryCapturingProvider()
    history = [
        ChatHistoryMessage(role="user", content="   "),
        ChatHistoryMessage(role="assistant", content=""),
    ]

    run_chat("继续", None, FakePetService([]), provider=provider, history=history)

    assert provider.history == []


def test_run_chat_limits_history_by_characters() -> None:
    provider = HistoryCapturingProvider()
    history = [
        ChatHistoryMessage(role="user", content="u" * 3000),
        ChatHistoryMessage(role="assistant", content="a" * 3000),
        ChatHistoryMessage(role="user", content="v" * 3000),
        ChatHistoryMessage(role="assistant", content="b" * 3000),
    ]

    run_chat("继续", None, FakePetService([]), provider=provider, history=history)

    assert provider.history is not None
    assert sum(len(item.content) for item in provider.history) <= MAX_HISTORY_CHARS
    assert len(provider.history) == 2
    assert provider.history[0].role == "user"
