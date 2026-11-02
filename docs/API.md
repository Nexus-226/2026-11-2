# Pet Agent 接口约定 v1

> 供 A（Agent）、B（后端）、C（前端）并行开发的接口约定。宠物资料 CRUD 已由后端实现；对话和地图接口仍是待实现契约。接口变更先在 PR 中同步三人。

## 共同规则

- 前端只请求 FastAPI：开发环境用相对路径，业务前缀为 `/api/v1`。请求和响应使用 UTF-8 JSON，字段统一 `snake_case`。
- 除健康检查外，成功时直接返回下述对象或数组，不再包 `success/data` 外壳。时间为带时区的 ISO 8601（UTC，例：`2026-11-02T08:00:00Z`）；ID 为 UUID 字符串。
- P0 是本地单用户演示，不要求登录；后端使用单一本地演示用户关联宠物资料，不代表接口已具备线上安全性。所有列表无结果返回 `200` 和 `[]`。
- `GET /health` 已实现：`200 {"status":"ok"}`。
- 业务接口错误使用以下统一结构。错误码为稳定的全大写字符串；`request_id` 为服务端生成的追踪 ID，`retryable` 表示是否可重试。

```json
{"error":{"code":"PET_NOT_FOUND","message":"未找到宠物","request_id":"req_123","retryable":false}}
```

| 状态码 | 场景 | 示例 code |
|---|---|---|
| 400 | JSON 无法解析或参数组合不合法 | `BAD_REQUEST` |
| 404 | 宠物、会话或地点不存在 | `PET_NOT_FOUND`、`SESSION_NOT_FOUND`、`PLACE_NOT_FOUND` |
| 409 | 数据状态冲突，例如宠物仍被会话引用 | `PET_IN_USE` |
| 422 | 字段缺失、类型或取值校验失败 | `VALIDATION_ERROR` |
| 429 | 服务限流 | `RATE_LIMITED` |
| 502 / 503 | 上游响应异常 / 暂不可用 | `UPSTREAM_ERROR`、`SERVICE_UNAVAILABLE` |
| 504 | 外部模型或地图请求超时 | `UPSTREAM_TIMEOUT` |
| 500 | 未预期的服务端错误 | `INTERNAL_ERROR` |

错误信息不包含密钥或上游原始敏感内容。宠物资料接口和参数校验已采用此结构；其他业务接口实现时也必须遵循。因请求被取消而中断时，客户端结束等待，不保证服务端返回 JSON。

## P0：宠物资料

`Pet` 响应结构（宠物 CRUD 已实现，SQLite 数据在后端进程重启后保留）：

```json
{
  "id": "b8f34f24-f5cf-4b5c-8d40-073541725a11",
  "name": "豆豆",
  "species": "dog",
  "breed": "金毛",
  "birthday": "2023-05-01",
  "notes": "对鸡肉过敏",
  "created_at": "2026-11-02T08:00:00Z",
  "updated_at": "2026-11-02T08:00:00Z"
}
```

`name` 为去除首尾空格后 1–50 字符；`species` 为 `dog`、`cat`、`other`。其余可选字段在响应中总是出现：`breed`、`notes` 为字符串或 `null`（最长分别 100、2000 字符），`birthday` 为 `YYYY-MM-DD` 日期或 `null`，不得晚于当天。创建时省略可选字段等同 `null`。时间戳为 UTC，并以 `Z` 结尾。

### P0 最终决定：生日和备注字段

- 统一使用 `birthday` 和 `notes`；P0 的宠物资料请求和响应不新增 `age`、`health_notes` 字段。早期任务说明中的“年龄、健康备注”是需求描述，不是另外两项 API 字段。
- `birthday` 保存已知的生日；为空时表示未知。有生日时可按需要计算年龄，不把计算结果当成额外存储字段。
- `notes` 用于健康和其他注意事项，允许为空。只知道大概年龄时，`birthday` 填 `null`，可在 `notes` 中写“约 3 岁”；不要由大概年龄推测具体生日。备注是自由文本，不保证能自动计算年龄。
- B 的数据模型和 API、C 的表单和客户端、A 获取的宠物资料均使用同一约定。未来要增加字段时，先在 PR 中同步 A、B、C 并更新文档和调用方。

例如，不知道生日但知道大概年龄时，创建请求可写：

```json
{"name":"豆豆","species":"dog","birthday":null,"notes":"约 3 岁"}
```

| 方法和路径 | 输入 | 成功响应 |
|---|---|---|
| `GET /api/v1/pets` | 无 | `200`：`Pet[]` |
| `POST /api/v1/pets` | `name`、`species` 必填，其余可选 | `201`：创建后的 `Pet` |
| `GET /api/v1/pets/{pet_id}` | 宠物 UUID | `200`：`Pet` |
| `PATCH /api/v1/pets/{pet_id}` | 只传需要修改的字段 | `200`：更新后的 `Pet` |
| `DELETE /api/v1/pets/{pet_id}` | 宠物 UUID | `204`：无响应体 |

创建请求示例：

```json
{
  "name": "豆豆",
  "species": "dog",
  "breed": "金毛",
  "birthday": "2023-05-01",
  "notes": "对鸡肉过敏"
}
```

部分更新示例（清除备注，同时修改名称）：

```json
{"name":"小豆","notes":null}
```

PATCH 中，省略字段表示不修改；`breed`、`birthday`、`notes` 传 `null` 表示清空，`name` 和 `species` 不能为 `null`。空对象和未知字段返回 `422`。删除不存在的记录返回 `404`；若仍被会话引用则返回 `409 PET_IN_USE`，不自动删除会话（等会话生命周期实现后生效）。

## P0：对话

第一版采用单次 JSON 请求与完整 JSON 回复。SSE 流式事件暂不纳入 P0 契约，确定事件格式后再版本化添加。C 可中止浏览器请求并清除加载状态；A/B 应设置服务端超时，是否立即停止上游计费由实际 Provider 决定。

`POST /api/v1/chat`：

```json
{"message":"豆豆平时怎么护理？","pet_id":"b8f34f24-f5cf-4b5c-8d40-073541725a11","session_id":null}
```

- `message` 必填，去除首尾空格后 1–4000 字符；`pet_id` 可为 UUID 或 `null`；`session_id` 可为 UUID 或 `null`。省略可选字段等同 `null`。
- `session_id:null` 创建会话；传入不存在的会话返回 `404 SESSION_NOT_FOUND`。传入不存在的宠物返回 `404 PET_NOT_FOUND`；关联宠物由本次 `pet_id` 显式指定，`null` 表示本次不使用宠物资料。
- `200` 返回如下结构；`tool_calls` 只列出工具名称及状态，不泄露参数、原始结果或密钥；无调用时为 `[]`：

```json
{
  "session_id":"d57700a2-a0a3-4bea-822c-9a8544def58e",
  "message_id":"b0276f42-1264-4ac3-ac75-5d58269e8758",
  "reply":"可以根据豆豆的年龄安排日常护理……",
  "tool_calls":[{"name":"get_pet_profile","status":"success"}]
}
```

`status` 为 `success` 或 `error`。若无法生成可信回答，返回相应错误状态码，不伪造回复。医疗信息需提醒仅供参考，紧急情况联系兽医。会话及消息持久化由 B 负责；Agent 的工具选择和输出组织由 A 负责；前端显示加载、错误和取消状态由 C 负责。

## A ↔ B：Agent 内部工具约定

Agent 在后端进程内调用注册表中的工具；工具不从前端直接暴露，也不由模型执行任意代码。A 定义输入/输出 Pydantic Schema 和注册协议，B 提供 Service 方法。以下为工具**逻辑契约**，具体函数签名由 A/B 联调确定：

| 工具 | 阶段 | 输入 | 输出与异常 |
|---|---|---|---|
| `get_pet_profile` | P0 | `pet_id`：UUID | 返回上面的 `Pet`；不存在返回可识别的 `PET_NOT_FOUND` |
| `list_pets` | P0 | 空对象 `{}` | 返回 `Pet[]`，无结果为 `[]` |
| `search_nearby_pet_services` | P1 | `lat`、`lng`、`type`、`radius_m` | 返回下述 `Place[]`；失败返回可识别错误 |

工具参数经 Pydantic 校验，仅执行注册表允许的工具；每轮最多连续调用 3 次，单次超时由 A/B 配置并在实现时明确。工具无权直接访问数据库或地图客户端，由 Service 层负责。

## P1：附近服务

`GET /api/v1/nearby?lat=39.9001&lng=116.4001&type=pet_hospital&radius_m=3000`。

- `lat`、`lng` 为 WGS84 十进制度数；纬度 -90～90，经度 -180～180。后端适配高德时负责坐标系转换；返回坐标也统一 WGS84，前端地图 SDK 使用时由地图展示适配层按需转换。
- `type` 为 `pet_hospital`、`pet_grooming`、`pet_store` 之一；`radius_m` 为整数 1000–20000，省略时默认 3000。
- `200` 返回按 `distance_m` 升序的 `Place[]`；无结果为 `[]`。拒绝定位时由前端允许手动输入地址，地址解析接口需在 P1 实现前另行约定，不能假定已实现。

```json
[{
  "id":"amap:example",
  "name":"安心宠物医院",
  "category":"pet_hospital",
  "address":"示例路 18 号",
  "phone":null,
  "location":{"lat":39.9001,"lng":116.4001},
  "distance_m":860,
  "business_status":"unknown",
  "navigation_url":null,
  "data_source":"amap"
}]
```

`phone`、`navigation_url` 可为 `null`；`business_status` 为 `open`、`closed`、`unknown`，不可确定时用 `unknown`。有导航链接时必须由用户主动打开。空电话显示“暂无电话”。`id` 使用 `amap:` 加供应商地点 ID；`distance_m` 为非负整数，单位米。

`GET /api/v1/places/{place_id}` 返回 `200` 和单个 `Place`；其中 `distance_m` 依赖用户位置，因此详情请求必须附带 `lat`、`lng`，规则同上。地点无效返回 `404 PLACE_NOT_FOUND`。地图与列表使用同一结果集，地图失败需保留列表或给出可理解错误。
