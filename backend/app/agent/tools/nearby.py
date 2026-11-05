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
                "只引用返回的地点，缺失字段标为未知；数据来源 source 与回退原因 "
                "fallback_reason 要如实告知，演示数据不能说成实时结果。"
                "source=demo 时无论 places 是否为空，都不得据此判断真实附近有没有服务；"
                "fallback_reason 表示后端高德未配置（amap_not_configured）或不可用"
                "（amap_unavailable），应说明是服务端问题、当前为演示数据，不要建议用户"
                "重新定位或输入地址来恢复真实结果。"
                "每条地点含 business_hours_today（今日营业时间原文，可能为 null）与 "
                "business_status：amap 地点的 business_status 由后端按北京时间从今日营业时间"
                "推算，不是实时开关门探测，回答时必须说明“按今日营业时间推算”；"
                "demo 地点为演示固定值，不代表真实营业。business_hours_today 为 null 或 "
                "business_status 为 unknown 时不要给出开关门结论，有原文可原样展示并说明"
                "无法判断，没有原文就说未提供营业时间，不要猜测。"
                "navigation_url=null 时不要说能启用"
                "导航或生成链接，只提示用户去页面真实地点卡片自带的导航入口手动打开。"
                "查询失败会返回错误，不要把失败说成没有结果。"
            ),
            input_schema=SearchNearbyPetServicesInput,
            func=search_nearby_pet_services,
        ),
    ]
