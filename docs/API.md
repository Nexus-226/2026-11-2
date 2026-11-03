# Pet Agent 接口约定 v1

> 供 A（Agent）、B（后端）、C（前端）并行开发的接口契约。P0 宠物资料的生日和备注字段已确定；宠物 CRUD、对话路由及 Qwen Provider 已实现，P0-8 会话历史已验收，地图尚未实现。实现状态说明不改变以下既有接口契约；新增记录/提醒契约已由 A/C 确认（PR #33），记录后端由 P1-2 实现，提醒仍待 P1-4。其他约定仍需三人评审，接口变更先在 PR 中同步三人。

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
| 409 | 数据状态冲突，例如宠物仍被会话/记录/提醒引用，或来源记录仍被提醒引用 | `PET_IN_USE`、`RECORD_IN_USE` |
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

当前后端路由已接入 A 的 `run_chat`，使用 `BoundPetService` 绑定请求级数据库会话；传入不存在的 `pet_id` 时在调用 Agent 前返回 `404 PET_NOT_FOUND`。会话、用户消息和助手回复持久化到 SQLite。当前已接入 Qwen Provider：配置 LLM_API_KEY 时使用真实模型，否则使用 MockProvider。P0-8 已完成验收：数据库历史已接入模型上下文，切换或清空关联宠物时由页面重置会话；具体实现与验证范围见 TASKS.md。

## A ↔ B：Agent 内部工具约定

Agent 在后端进程内调用注册表中的工具；工具不从前端直接暴露，也不由模型执行任意代码。A 定义输入/输出 Pydantic Schema 和注册协议，B 提供 Service 方法。以下为工具**逻辑契约**，具体函数签名由 A/B 联调确定：

| 工具 | 阶段 | 输入 | 输出与异常 |
|---|---|---|---|
| `get_pet_profile` | P0 | `pet_id`：UUID | 返回上面的 `Pet`；不存在返回可识别的 `PET_NOT_FOUND` |
| `list_pets` | P0 | 空对象 `{}` | 返回 `Pet[]`，无结果为 `[]` |
| `search_nearby_pet_services` | P1 | `lat`、`lng`、`type`、`radius_m` | 返回下述 `Place[]`；失败返回可识别错误 |

工具参数经 Pydantic 校验，仅执行注册表允许的工具；每轮最多连续调用 3 次。P0 工具为本地快速调用，暂不实现工具级超时；真实外部工具接入时再补超时机制。工具无权直接访问数据库或地图客户端，由 Service 层负责。

B 的 Agent Service 适配器将 SQLAlchemy `Session` 绑定在构造时，因此 `get_pet(pet_id)` 和 `list_pets()` 不再额外接收数据库 Session；P0-4 聊天路由应通过 `get_db` 获取 Session，构造适配器后传给 A 的 `run_chat(message, pet_id, service)`。`get_pet` 对不存在的宠物返回 `None`，由 `get_pet_profile` 工具映射为 `PET_NOT_FOUND`；Service 与工具共用 `app.schemas.pet.PetRead`。

## P1-1：日常记录与提醒契约（A/C 已确认）

本节是 P1-1 经 A/C 确认的接口契约；P1-2 实现其中的记录 API，提醒 API 由 P1-4 实现。若后续评审需调整，先在本节修订，不兼容地改动既有 P0 接口。

### 共同数据规则

- 记录和提醒独立于聊天消息保存。`pet_id` 可为 UUID 或 `null`；未关联宠物的数据仍可创建和查询。
- `created_at`、`updated_at` 为 UTC ISO 8601 时间戳，`id` 为 UUID。业务日期采用 `YYYY-MM-DD` 日历日期，不伪造具体时刻；首版“今天/逾期/未来七天”按 `Asia/Shanghai` 计算。若后续支持多用户或时区设置，再扩展用户时区，不把日期字符串转换成 UTC 时间戳。
- 所有输入校验失败返回现有 `422 VALIDATION_ERROR`；宠物不存在返回 `404 PET_NOT_FOUND`；对象不存在分别返回 `404 RECORD_NOT_FOUND` 或 `404 REMINDER_NOT_FOUND`。错误体遵循本页统一结构，不暴露数据库异常。
- 列表没有匹配项时返回 `200 []`。`pet_id` 过滤未提供时返回全部宠物及未关联的数据；传 UUID 时只返回该宠物数据；`unlinked=true` 时只返回 `pet_id=null` 的数据，且不得与 `pet_id` 同时提供。页面查询某只宠物的记录/提醒时必须显式传该宠物的 `pet_id`，不能用未过滤的全量列表替代宠物详情查询；未关联数据作为独立范围展示并标注“未关联宠物”。时间范围首尾均包含，开始日期晚于结束日期返回 `400 BAD_REQUEST`。
- A↔B Service 约定：记录/提醒查询无匹配数据时返回空列表 `[]`；查询或写入失败时抛出可识别异常，由 HTTP 层映射到本契约对应的错误码（如 `PET_NOT_FOUND`、`RECORD_NOT_FOUND`、`REMINDER_NOT_FOUND`），未预期异常映射为 `500 INTERNAL_ERROR`，不得将失败伪装成空列表。具体异常类型由 A/B 在 Service Protocol 中共享定义；Agent 工具必须保留空结果与异常的区别，以便如实说明“没有记录”或“查询失败”。

### 日常记录（拟议 `Record`）

记录类型固定为 `vaccine`、`deworming`、`bath`、`weight`。日期字段 `occurred_on` 表示实际发生日期，不能用记录创建日期代替。

```json
{
  "id": "b8f34f24-f5cf-4b5c-8d40-073541725a11",
  "pet_id": "d57700a2-a0a3-4bea-822c-9a8544def58e",
  "record_type": "weight",
  "occurred_on": "2026-11-02",
  "name": null,
  "weight_kg": 4.25,
  "notes": null,
  "created_at": "2026-11-02T08:00:00Z",
  "updated_at": "2026-11-02T08:00:00Z"
}
```

- `record_type` 必填；`occurred_on` 必填且不得晚于当前 `Asia/Shanghai` 日期。
- `name` 为可空、去除首尾空格后最长 100 字符的项目/产品名称，可用于疫苗或驱虫记录；`notes` 为可空、最长 2000 字符。
- `weight_kg` 仅 `weight` 类型必填，使用公斤，数值必须大于 0、最多两位小数、上限 500；其他类型必须为 `null`。不提供可变单位，避免同一字段出现单位换算歧义。
- 端点：`GET/POST /api/v1/records`、`GET/PATCH/DELETE /api/v1/records/{record_id}`。列表支持 `pet_id`、`unlinked`、`record_type`、`from_date`、`to_date`；默认按 `occurred_on` 倒序，再按 `created_at` 倒序及 `id` 升序稳定排序。创建返回 `201 Record`，读取/修改返回 `200 Record`，删除返回 `204`。
- 创建仅接受 `pet_id`、`record_type`、`occurred_on`、`name`、`weight_kg`、`notes`；`PATCH` 只修改出现的字段，省略不变，可空字段传 `null` 表示清空。创建或 `PATCH` 包含未知字段，以及空对象 `PATCH`，均返回 `422 VALIDATION_ERROR`。`record_type` 与 `weight_kg` 按更新后的完整对象规则联合校验。记录被删除时不删除引用它的提醒，提醒的 `source_record_id` 清空。
- 若记录被提醒作为 `source_record_id` 引用，`PATCH` 改变记录的 `pet_id` 不自动修改任何提醒；当新归属会使来源记录与提醒的宠物归属不一致时，返回 `409 RECORD_IN_USE`，用户先解除相关提醒的来源引用后再修改归属。`pet_id` 未改变时允许其他字段正常更新。

### 站内提醒（拟议 `Reminder`）

```json
{
  "id": "b8f34f24-f5cf-4b5c-8d40-073541725a12",
  "pet_id": "d57700a2-a0a3-4bea-822c-9a8544def58e",
  "title": "下次驱虫",
  "due_on": "2026-11-09",
  "status": "pending",
  "due_group": "upcoming",
  "source_record_id": null,
  "created_at": "2026-11-02T08:00:00Z",
  "updated_at": "2026-11-02T08:00:00Z"
}
```

- `title` 必填，去除首尾空格后 1–120 字符；`due_on` 必填，为 `Asia/Shanghai` 日历日期，可为过去日期以支持补录逾期事项。
- `status` 为 `pending`、`completed`、`cancelled` 之一；新建时客户端不得传 `status`，服务端默认创建为 `pending`。响应中的 `due_group` 是非持久化派生字段，由 B 的 Service 按 `Asia/Shanghai` 当前日统一计算，供 HTTP 响应和 A 的 Agent 工具共用：`pending` 项按 `due_on` 分为 `overdue`（早于今天）、`today`（今天）、`upcoming`（明日起至第七日，含）或 `later`（第七日之后）；`completed`/`cancelled` 项为 `null`。字段类型为 `ReminderDueGroup = "overdue" | "today" | "upcoming" | "later" | null`。前端和 Agent 不得各自重新计算该分组。`upcoming` 不是持久化状态。
- P1-5 演示问法使用“未来七天有哪些安排”，范围为 `Asia/Shanghai` 今天至第六日（含），以查询时实际起止日期回应，包含今天并避免与派生分组 `upcoming`（明日至第七日）混淆。用户问“这周”时按 `Asia/Shanghai` 自然周（周一至周日，含今天）理解；如对话上下文表明用户可能指滚动七天，则先澄清。Service 支持任意包含首尾日期的 `from_date`/`to_date` 查询，不将自然周与滚动七天混为一谈。
- `source_record_id` 可空；非空时记录必须存在，且提醒与来源记录的 `pet_id` 必须一致；提醒 `PATCH` 后按更新后的完整对象校验此约束，而非只校验本次提交的字段。来源记录删除时仅清空该字段，不删除提醒。
- 建议端点：`GET/POST /api/v1/reminders`、`GET/PATCH/DELETE /api/v1/reminders/{reminder_id}`。列表支持 `pet_id`、`unlinked`、`status`、`from_date`、`to_date`（按 `due_on` 过滤）；默认按 `due_on` 正序、`created_at` 正序及 `id` 升序稳定排序。创建返回 `201 Reminder`，读取/修改返回 `200 Reminder`，删除返回 `204`。
- 创建仅接受 `pet_id`、`title`、`due_on` 和可选 `source_record_id`；客户端传入 `status` 或任何未知字段均返回 `422 VALIDATION_ERROR`。`PATCH` 仅接受这些可修改字段及 `status`；空对象或包含未知字段返回 `422 VALIDATION_ERROR`。只允许通过 `PATCH status` 将 `pending` 改为 `completed` 或 `cancelled`；对同一状态重复更新幂等成功，不重复产生副作用；两种结束状态不可直接重新打开，需要新建提醒。
- 提案：只要宠物仍有关联记录或提醒，删除宠物返回既有 `409 PET_IN_USE`，不级联删除或自动解除关联；用户先显式删除/解除关联的记录与提醒，再删除宠物。此沿用 P0 删除错误约定并避免静默丢失历史，需 A/C 确认具体解除关联交互。

**评审结论：**A/C 已确认 `Asia/Shanghai` 日期语义、`weight_kg` 精度和上限、字段、过滤与排序、提醒状态转换、`RECORD_IN_USE` 归属变更保护、创建时服务端默认 `pending`，以及宠物仍有关联记录/提醒时返回 `PET_IN_USE` 的行为。具体审批记录见 PR #33。

## P1：模型可靠性与数据边界（待契约评审）

本节是 P1-1 / P1-7 的设计与验收要求，不代表接口、字段或功能已实现，也不提前新增路径、响应字段或错误码。具体结构由 A/B/C 共同评审；现有 P0 契约保持不变。

- 数据库记录及 Service 查询结果是事实来源。记录日期、数值、提醒状态、到期及逾期判断由程序按约定时区计算，模型只负责理解与解释，不自行补齐事实或计算状态。
- B 在 Service/工具边界校验宠物、类型、时间范围等参数并限制查询范围。针对“它/当前宠物”的查询，未关联时要求选择；只有明确请求跨宠物汇总且契约支持时才查询多只宠物，结果保留宠物归属，不以全部档案替代当前关联。
- 空结果、查询失败、未关联和已成功取得数据必须可区分，不能把失败说成“没有记录”。状态如何表达由契约评审决定；不依赖模型从自然语言猜测。
- A 只能引用本轮工具返回或已明确提供的事实。记录缺失时如实说明；工具失败时说明暂时无法查询。计划、待办完成与实际护理记录分开解释，不能从历史聊天推断某项操作已入库或已发生。
- C 的记录时间线、待办状态和地点卡片直接展示结构化接口数据。模型文本不能修改卡片事实或充当保存成功依据；写入成功以业务接口确认结果为准。
- P1 Agent 保持只读，不承诺“已保存/已设置提醒/关闭程序后会通知”。P2 自然语言写入须经可编辑草稿、用户确认及服务端校验后提交，成功、失败和去重按实际接口处理。
- 附近服务的地点、距离和来源以工具结果为准；缺失的营业时间、携宠规则等标为未知，不编造。演示/真实数据及回退状态需可识别，空结果时也适用。

## P1：附近服务

`GET /api/v1/nearby?lat=39.9001&lng=116.4001&type=pet_hospital&radius_m=3000`。

- `lat`、`lng` 为 WGS84 十进制度数；纬度 -90～90，经度 -180～180。后端适配高德时负责坐标系转换；返回坐标也统一 WGS84，前端地图 SDK 使用时由地图展示适配层按需转换。
- `type` 为 `pet_hospital`、`pet_grooming`、`pet_store` 之一；`radius_m` 为整数 1000–20000，省略时默认 3000。旧架构指南流程图中的 `radius` 在实现时统一使用此处的 `radius_m`。
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

`phone`、`navigation_url` 可为 `null`；`business_status` 为 `open`、`closed`、`unknown`，不可确定时用 `unknown`。有导航链接时必须由用户主动打开。空电话显示“暂无电话”。`distance_m` 为非负整数，单位米。

数据来源和 ID 约定：真实高德数据使用 `data_source: "amap"`、`id: "amap:<高德地点 ID>"`；种子演示数据使用 `data_source: "demo"`、`id: "demo:<稳定的演示地点 ID>"`。前端和 Agent 必须明确标注演示数据，不能称为实时结果。高德不可用时如果回落演示数据，也必须标注来源；不能提供真实导航时 `navigation_url` 为 `null`。

高德失败后回落时，前端还需要知道服务不可用并提供重试；仅依赖列表中的每条 `data_source` 无法表达空列表时的回落状态。P1 实现前由 A、B、C 确认如何传递回落原因和状态（包括空结果）；该部分目前尚未实现或冻结。

`GET /api/v1/places/{place_id}` 返回 `200` 和单个 `Place`；其中 `distance_m` 依赖用户位置，因此详情请求必须附带 `lat`、`lng`，规则同上。地点无效返回 `404 PLACE_NOT_FOUND`。地图与列表使用同一结果集，地图失败需保留列表或给出可理解错误。
