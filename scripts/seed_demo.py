#!/usr/bin/env python3
"""演示数据种子脚本。

在 ECS 上运行（后端在不在运行都可以）：
    cd /opt/pet-agent
    PET_AGENT_DATABASE_URL=sqlite:////var/lib/pet-agent/pet_agent.db \
      .venv/bin/python scripts/seed_demo.py

幂等：重复运行会先删除同名的演示宠物及其记录，再重新插入。

两组数据：
  - 「豆豆」（猫）：用于向 Agent 提问（过敏 / 驱虫 / 洗澡 / 体重）。
  - 「旺财」（狗）：用于看体重趋势图（近两个月 9 条称重记录）。
"""
from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import delete, select

from app.db.models import DEFAULT_USER_ID, Pet, Record, User
from app.db.session import SessionLocal, init_db

DEMO_PETS = [
    {
        "name": "豆豆",
        "species": "cat",
        "breed": "英国短毛猫",
        "birthday": date(2023, 3, 15),
        "notes": "对牛肉过敏，鸡肉可以吃。已绝育，特别怕洗澡，容易应激。最近在控制体重，每天 40g 猫粮。",
        "records": [
            ("vaccine", date(2026, 9, 10), "猫三联疫苗", None, "第一针"),
            ("vaccine", date(2026, 10, 1), "猫三联疫苗", None, "第二针（加强）"),
            ("deworming", date(2026, 10, 20), "体内驱虫", None, None),
            ("bath", date(2026, 11, 2), "洗澡", None, "有点应激，下次提前安抚"),
            ("weight", date(2026, 9, 8), None, Decimal("4.20"), None),
            ("weight", date(2026, 10, 8), None, Decimal("4.26"), None),
            ("weight", date(2026, 11, 2), None, Decimal("4.30"), None),
        ],
    },
    {
        "name": "旺财",
        "species": "dog",
        "breed": "金毛寻回犬",
        "birthday": date(2022, 6, 1),
        "notes": "鸡肉过敏，牛肉可以吃。正在控制体重，目标是 29 kg。",
        "records": [
            ("weight", date(2026, 9, 5), None, Decimal("31.80"), None),
            ("weight", date(2026, 9, 12), None, Decimal("31.50"), None),
            ("weight", date(2026, 9, 20), None, Decimal("31.20"), None),
            ("weight", date(2026, 9, 28), None, Decimal("30.90"), None),
            ("weight", date(2026, 10, 5), None, Decimal("30.50"), None),
            ("weight", date(2026, 10, 12), None, Decimal("30.20"), None),
            ("weight", date(2026, 10, 19), None, Decimal("29.80"), None),
            ("weight", date(2026, 10, 26), None, Decimal("29.50"), None),
            ("weight", date(2026, 11, 3), None, Decimal("29.20"), None),
        ],
    },
]


def _clear_pet(session, user_id: str, name: str) -> None:
    existing = session.scalars(
        select(Pet).where(Pet.user_id == user_id, Pet.name == name)
    ).all()
    for pet in existing:
        session.execute(delete(Record).where(Record.pet_id == pet.id))
        session.delete(pet)
    session.flush()


def main() -> None:
    init_db()
    with SessionLocal() as session:
        user = session.get(User, DEFAULT_USER_ID)
        if user is None:
            user = User(id=DEFAULT_USER_ID, display_name="本地演示用户")
            session.add(user)
            session.flush()

        for spec in DEMO_PETS:
            _clear_pet(session, user.id, spec["name"])

            pet = Pet(
                id=str(uuid4()),
                user_id=user.id,
                name=spec["name"],
                species=spec["species"],
                other_species=None,
                breed=spec["breed"],
                birthday=spec["birthday"],
                notes=spec["notes"],
            )
            session.add(pet)
            session.flush()

            for record_type, occurred_on, name, weight_kg, notes in spec["records"]:
                session.add(
                    Record(
                        id=str(uuid4()),
                        user_id=user.id,
                        pet_id=pet.id,
                        record_type=record_type,
                        occurred_on=occurred_on,
                        name=name,
                        weight_kg=weight_kg,
                        notes=notes,
                    )
                )

        session.commit()
        print("演示数据已就绪：")
        print("  - 豆豆（猫）：用于向 Agent 提问（过敏 / 驱虫 / 洗澡 / 体重）")
        print("  - 旺财（狗）：用于看体重趋势图（近两个月 9 条称重记录）")


if __name__ == "__main__":
    main()
