"""P1 附近搜索只读工具（A 定义）。

工具只声明输入 Schema 并通过 Service 查询；Service 将 ``center_source`` 原样
传给附近查询并返回 ``NearbyResponse``。附近搜索按坐标查询、不绑定宠物；工具不
直接访问地图客户端或数据库，也不编造地点、距离或来源，演示/真实数据及回退状态
由 Service 结果显式标注，Agent 只引用返回的地点。
"""

from __future__ import annotations

from app.agent.registry import Tool
from app.agent.schemas import SearchNearbyPetServicesInput
from app.agent.service_protocol import NearbyService
from app.schemas.nearby import NearbyResponse


def make_nearby_tools(service: NearbyService) -> list[Tool]:
    """基于 Service 构造附近搜索工具。"""

    def search_nearby_pet_services(
        inp: SearchNearbyPetServicesInput,
    ) -> NearbyResponse:
        return service.search_nearby(
            lat=inp.lat,
            lng=inp.lng,
            category=inp.type,
            radius_m=inp.radius_m,
            center_source=inp.center_source,
        )

    return [
        Tool(
            name="search_nearby_pet_services",
            description=(
                "按 WGS84 坐标（lat/lng）、类型和半径查询附近的宠物服务。"
                "type 取 pet_hospital 宠物医院 / pet_grooming 宠物美容 / "
                "pet_store 宠物用品店；radius_m 单位为米，默认 3000。"
                "center_source 表示查询中心来源：user_location 当前位置（默认）或 "
                "resolved_address 所选地址。"
                "返回 NearbyResponse：places 地点列表（含 distance_m 距离、电话、"
                "营业状态、导航链接）、search_center 查询中心、source 数据来源"
                "（amap 真实 / demo 演示）、fallback_reason 回退原因。"
                "只引用返回的地点，缺失字段标为未知；演示数据或回退状态要如实告知，"
                "不能说成实时结果；导航链接只能由用户主动打开。查询失败会返回错误，"
                "不要把失败说成没有结果。"
                "source=demo 且 fallback_reason 非空、places 为空时，只能说明演示数据中"
                "没有该范围内的地点，不能推断真实附近没有服务，应说明实时服务未接入/不可用。"
            ),
            input_schema=SearchNearbyPetServicesInput,
            func=search_nearby_pet_services,
        ),
    ]
