# Pet Agent 接口约定 v1

> 供 A（Agent）、B（后端）、C（前端）并行开发的接口契约。P0 宠物资料的生日和备注字段已确定；宠物 CRUD、对话路由及 Qwen Provider 已实现，P0-8 会话历史已验收，地图演示版后端与页面已随 PR #40/#43 合并，P1-9 高德真实接入（POI 查询与详情）由本 PR 实现，`/locations/resolve` 地址解析待 P1-10。实现状态说明不改变以下既有接口契约；新增记录/提醒契约已由 A/C 确认（PR #33），记录后端已随 PR #34 合并，提醒后端已随 PR #38 合并（C 提醒页面已随 PR #39 合并）。其他约定仍需三人评审，接口变更先在 PR 中同步三人。P2-1 其他宠物具体物种的后端读写（含 Alembic 迁移与关联校验）由本 PR 实现；前端接入与三方联调在 B 完整后端合并后进行。

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
| 404 | 宠物、会话、地点或地址解析结果不存在 | `PET_NOT_FOUND`、`SESSION_NOT_FOUND`、`PLACE_NOT_FOUND`、`ADDRESS_NOT_FOUND` |
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
  "other_species": null,
  "breed": "金毛",
  "birthday": "2023-05-01",
  "notes": "对鸡肉过敏",
  "created_at": "2026-11-02T08:00:00Z",
  "updated_at": "2026-11-02T08:00:00Z"
}
```

`name` 为去除首尾空格后 1–50 字符；`species` 为 `dog`、`cat`、`other`。`other_species` 是 `species` 为 `other` 时的具体物种档案字段（如 `兔`）：仅接受字符串或 `null`，去除首尾空白后为空等同 `null`，标准化后最多 50 个 Unicode 码点（仅去首尾空白，不做 NFC 等归一化，不改写其余字符，不折叠内部空白）；`species` 为 `dog`/`cat` 时恒为 `null`。其余可选字段在响应中总是出现：`breed`、`notes` 为字符串或 `null`（最长分别 100、2000 字符），`birthday` 为 `YYYY-MM-DD` 日期或 `null`，不得晚于当天。创建时省略可选字段等同 `null`。时间戳为 UTC，并以 `Z` 结尾。

数据库通过一个 Alembic revision 新增可空列（`String(50)`，长度由应用层校验保证）；所有存量宠物（包括 `other`）的 `other_species` 回填 `null`，不从 `breed`、`notes` 或聊天文本推断具体物种。部署顺序为先部署后端及迁移，再启用前端新字段。

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

`species` 为 `other` 时可携带具体物种：

```json
{"name":"团团","species":"other","other_species":"兔"}
```

部分更新示例（清除备注，同时修改名称）：

```json
{"name":"小豆","notes":null}
```

PATCH 中，省略字段表示不修改；`breed`、`birthday`、`notes`、`other_species` 传 `null` 表示清空（`other_species` 的 `null` 是合法清空操作），`name` 和 `species` 不能为 `null`。`other_species` 按合并原资料后的完整对象联合校验：`dog`/`cat` 携带非空具体物种返回 `422`；从 `other` 切回 `dog`/`cat` 时必须显式提交 `other_species: null`，仅隐藏输入框或省略字段不能清除旧值，否则返回 `422` 且原资料不变——两类 `422` 的 `message` 可区分，错误码仍为 `VALIDATION_ERROR`。空对象和未知字段返回 `422`。删除不存在的记录返回 `404`；若仍被会话引用则返回 `409 PET_IN_USE`，不自动删除会话（等会话生命周期实现后生效）。

### P2-3：寻宠信息卡消费约定（C 主，A/B 协作）

寻宠信息卡是 P2-3 备选任务，本节为 B 侧「确认字段」的产出与消费契约。后端**零变更**：卡片档案部分复用上方 `Pet` 契约（单卡用 `GET /api/v1/pets/{pet_id}`，选宠列表用 `GET /api/v1/pets`），不新增端点、字段、参数或错误码，不做任何迁移或持久化，也不属于 A 的 Agent 工具范围。以下字段集与模板经 A/C 评审确认后，由 C 实现预览与复制。

- 档案字段映射：`name` → 宠物名字；物种显示沿用 `other_species` 既有语义——`dog`/`cat` 按现有页面文案，`other` 且 `other_species` 非空显示「其他（{other_species}）」，为空显示「其他」；`breed` → 品种，`birthday` → 生日，`notes` → 特征与备注。`breed`/`birthday`/`notes` 为 `null` 时对应整行省略，不放占位文案：不推算年龄、不编造生日，`notes` 中用户自述的「约 N 岁」仅原样引用，不做加工。
- 用户补充字段仅在前端组合：**走失时间按日期粒度记录（`YYYY-MM-DD`，不含具体时刻**；此粒度为本契约的明确约定，对应任务行「走失时间」，若 C 评估需要时刻粒度，先在本节修订契约再实现）、走失地点（用户文本描述）、联系方式（用户自填的自由文本）。三者仅用于本次预览与复制，**不提交后端、不持久化到服务端、不自动发布**；本契约不为它们新增任何 API 字段或请求。允许本地暂存未提交草稿（如 localStorage），但须使用与既有演示数据区分的独立存储键，并在页面标注隐私边界（涉及联系方式，见下条）。
- 预览与复制使用**同一份纯文本字符串**（由同一来源生成，不得预览渲染一份、复制时另拼一份导致两边不一致），保证所见即所复制；空字段整行省略，不放占位文案：

```text
【寻宠】{name}（{species_label}）
品种：{breed}
生日：{birthday}
走失时间：{lost_date}
走失地点：{lost_place}
特征与备注：{notes}
联系方式：{contact}
```

- 边界与不做：不接入照片（数据模型无照片字段，如需支持先在 PR 中评审新增字段与存储，不并入本期）；图片导出（如把预览渲染为图片）属低成本可选项，由 C 决定是否实现，不涉及后端；不自动发布到任何外部渠道，不接入寻宠社区与线索匹配（见 TASKS.md 排除范围）；不宣称、不接入定位能力——走失地点为用户文本，不为卡片调用地图接口，不调用 `/api/v1/locations/resolve`、`/api/v1/nearby`、`/api/v1/nearby/demo`（不为卡片复用 P1 地址解析或附近查询能力），不生成坐标或导航链接。
- 卡片复制文本除档案字段与用户输入外，不含系统生成的时间戳、坐标等元数据。联系方式为用户自填的自由文本：前端不做结构化校验（不拆分手机号/微信/邮箱等子字段）、不做号码规范化或格式校验、不承诺可拨打；展示与复制前由用户自行确认内容，属用户敏感输入，不提交后端。
- P2-3 整体完成状态（含前端预览、复制与可选图片导出的验收）由任务负责人 C 在交付后更新 TASKS.md；本节不改变任何既有接口契约。

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
| `search_nearby_pet_services` | P1 | `lat`、`lng`、`type`、`radius_m`、`center_source`（可选，默认 `user_location`） | Service 将 `center_source` 原样传给附近查询并返回下述 `NearbyResponse`；省略时使用 `user_location`；失败返回可识别错误 |

工具参数经 Pydantic 校验，仅执行注册表允许的工具；每轮最多连续调用 3 次。P0 工具为本地快速调用，暂不实现工具级超时；真实外部工具接入时再补超时机制。工具无权直接访问数据库或地图客户端，由 Service 层负责。

B 的 Agent Service 适配器将 SQLAlchemy `Session` 绑定在构造时，因此 `get_pet(pet_id)` 和 `list_pets()` 不再额外接收数据库 Session；P0-4 聊天路由应通过 `get_db` 获取 Session，构造适配器后传给 A 的 `run_chat(message, pet_id, service)`。`get_pet` 对不存在的宠物返回 `None`，由 `get_pet_profile` 工具映射为 `PET_NOT_FOUND`；Service 与工具共用 `app.schemas.pet.PetRead`。

## P1-1：日常记录与提醒契约（A/C 已确认）

本节是 P1-1 经 A/C 确认的接口契约；P1-2 实现其中的记录 API，提醒 API 由 P1-4 实现。若后续评审需调整，先在本节修订，不兼容地改动既有 P0 接口。

### 共同数据规则

- 记录和提醒独立于聊天消息保存。`pet_id` 可为 UUID 或 `null`；未关联宠物的数据仍可创建和查询。
- `created_at`、`updated_at` 为 UTC ISO 8601 时间戳，`id` 为 UUID。业务日期采用 `YYYY-MM-DD` 日历日期，不伪造具体时刻；首版“今天/逾期/未来七天”按 `Asia/Shanghai` 计算。若后续支持多用户或时区设置，再扩展用户时区，不把日期字符串转换成 UTC 时间戳。
- 所有输入校验失败返回现有 `422 VALIDATION_ERROR`；宠物不存在返回 `404 PET_NOT_FOUND`；对象不存在分别返回 `404 RECORD_NOT_FOUND` 或 `404 REMINDER_NOT_FOUND`。错误体遵循本页统一结构，不暴露数据库异常。
- 列表没有匹配项时返回 `200 []`。`pet_id` 过滤未提供时返回全部宠物及未关联的数据；传 UUID 时只返回该宠物数据；`unlinked=true` 时只返回 `pet_id=null` 的数据，且不得与 `pet_id` 同时提供。页面查询某只宠物的记录/提醒时必须显式传该宠物的 `pet_id`，不能用未过滤的全量列表替代宠物详情查询；未关联数据作为独立范围展示并标注“未关联宠物”。时间范围首尾均包含，开始日期晚于结束日期返回 `400 BAD_REQUEST`。
- A↔B Service 约定：记录/提醒查询无匹配数据时返回空列表 `[]`；查询或写入失败时抛出可识别异常，由 HTTP 层映射到本契约对应的错误码（如 `PET_NOT_FOUND`、`RECORD_NOT_FOUND`、`REMINDER_NOT_FOUND`），未预期异常映射为 `500 INTERNAL_ERROR`，不得将失败伪装成空列表。具体异常类型由 A/B 在 Service Protocol 中共享定义；Agent 工具必须保留空结果与异常的区别，以便如实说明“没有记录”或“查询失败”。B 已在 `app.services` 提供构造时绑定 `Session` 的只读适配器并返回对应 `*Read` Schema：`BoundPetService` 已接入 `/api/v1/chat`，`BoundReminderService` 与 `BoundRecordService` 已就绪，待 A 侧工具注册后在 P1-5 联调接入。

### 日常记录（`Record`）

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

#### P2-2：体重趋势图消费约定（C 主，B 协作）

体重趋势图复用上方记录契约，不新增端点、字段、参数或错误码；以下均为既有已确认行为，仅补充绘图消费视角的说明，并由 `backend/tests/unit/test_records.py` 的 `test_weight_trend_*` 用例固化：

- 拉取：`GET /api/v1/records?pet_id={pet_id}&record_type=weight`，可加 `from_date`/`to_date` 缩小窗口；窗口首尾日期均包含。宠物详情页必须显式传该宠物的 `pet_id`，不用全量列表替代。
- 排序：响应按 `occurred_on` 倒序、同日按 `created_at` 倒序（后创建在前）、`id` 升序稳定排序；绘图前前端自行反转为时间正序，后端不提供正序参数。
- 同日多条体重记录：契约不去重、不聚合，全部返回。前端如需“每日一点”，取同日列表首条（即最新创建的一条）；如全部绘出，需自行标注避免连线回折。
- `weight_kg`：JSON number，固定公斤，大于 0、最多两位小数、上限 500；不存在其他单位，不做单位换算，前端不得再乘除换算系数。
- 空数据返回 `200 []`（对应图表空态，与加载失败区分展示）；窗口内仅一条时返回单元素数组（画单点，不画连线）。
- 错误态映射：`400 BAD_REQUEST`（`unlinked` 与 `pet_id` 同时提供，或开始日期晚于结束日期）、`404 PET_NOT_FOUND`（宠物不存在）、`422 VALIDATION_ERROR`（参数类型错误）；错误体遵循本页统一结构。
- 趋势图仅展示历史记录事实，不根据体重数据给出健康诊断或建议。

### 站内提醒（`Reminder`）

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
- `status` 为 `pending`、`completed`、`cancelled` 之一；新建时客户端不得传 `status`，服务端默认创建为 `pending`。响应中的 `due_group` 是非持久化派生字段，由 B 的 Service 按 `Asia/Shanghai` 当前日统一计算，供 HTTP 响应和 A 的 Agent 工具共用：`pending` 项按 `due_on` 分为 `overdue`（逾期）、`today`（今天）、`upcoming`（即将：明日起至第七日，含）或 `later`（更晚：第七日之后）；`completed`/`cancelled` 项为 `null`。字段类型为 `ReminderDueGroup = "overdue" | "today" | "upcoming" | "later" | null`。前端和 Agent 不得各自重新计算该分组。`upcoming` 不是持久化状态。
- P1-5 演示问法使用“未来七天有哪些安排”，范围为 `Asia/Shanghai` 今天至第六日（含），以查询时实际起止日期回应，包含今天并避免与派生分组 `upcoming`（明日至第七日）混淆。用户问“这周”时按 `Asia/Shanghai` 自然周（周一至周日，含今天）理解；如对话上下文表明用户可能指滚动七天，则先澄清。Service 支持任意包含首尾日期的 `from_date`/`to_date` 查询，不将自然周与滚动七天混为一谈。
- `source_record_id` 可空；非空时记录必须存在，且提醒与来源记录的 `pet_id` 必须一致；提醒 `PATCH` 后按更新后的完整对象校验此约束，而非只校验本次提交的字段。来源记录删除时仅清空该字段，不删除提醒。
- 端点：`GET/POST /api/v1/reminders`、`GET/PATCH/DELETE /api/v1/reminders/{reminder_id}`。列表支持 `pet_id`、`unlinked`、`status`、`from_date`、`to_date`（按 `due_on` 过滤）；默认按 `due_on` 正序、`created_at` 正序及 `id` 升序稳定排序。创建返回 `201 Reminder`，读取/修改返回 `200 Reminder`，删除返回 `204`。
- 创建仅接受 `pet_id`、`title`、`due_on` 和可选 `source_record_id`；客户端传入 `status` 或任何未知字段均返回 `422 VALIDATION_ERROR`。`PATCH` 仅接受这些可修改字段及 `status`；空对象或包含未知字段返回 `422 VALIDATION_ERROR`。只允许通过 `PATCH status` 将 `pending` 改为 `completed` 或 `cancelled`；对同一状态重复更新幂等成功，不重复产生副作用；两种结束状态不可直接重新打开，需要新建提醒。
- 只要宠物仍有关联记录或提醒，删除宠物返回既有 `409 PET_IN_USE`，不级联删除或自动解除关联；用户先显式删除/解除关联的记录与提醒，再删除宠物。此沿用 P0 删除错误约定并避免静默丢失历史。

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

## P1-7：附近服务与地址解析契约（已随 PR #35 合并）

本节为 P1-7 契约，已随 PR #35 合并。P1-8 已按演示数据实现并合并（PR #40，页面见 PR #43），P1-9 高德真实接入由独立 PR 实现；两者不得合并成一个 PR。

附近查询：`GET /api/v1/nearby?lat=39.9001&lng=116.4001&type=pet_hospital&radius_m=3000&center_source=user_location`。

- 请求及响应 `location.lat`/`location.lng` 均为 WGS84 十进制度数；纬度 -90～90，经度 -180～180。高德 Web Service 请求前由后端把 WGS84 转为 GCJ-02；高德返回的 GCJ-02 坐标由后端转回 WGS84。前端地图 SDK 的坐标适配由 C 负责，不向前端暴露高德原始坐标或响应字段。
- `/nearby` 接受 `center_source` 查询参数，取值为 `user_location` 或 `resolved_address`，省略时默认为 `user_location`；非法值返回 `422 VALIDATION_ERROR`。A 的 `search_nearby_pet_services` 工具同样接受可选 `center_source`，默认 `user_location`，并将其传入与 HTTP 路由共用的 B 附近查询 Service；Service 原样保留该值用于生成响应，不得根据地点数据来源或模型推断/改写查询中心来源。地址解析返回候选后，C 将用户选择的 WGS84 坐标及 `center_source=resolved_address` 一并用于附近查询；具体候选地址由前端临时保存在客户端并自行展示，后端不回显或持久化原始地址，`search_center.label` 中“所选地址”仅为通用兜底标签。后端在 `search_center.source` 原样返回该值。演示入口不接受 `center_source`，固定返回 `search_center.source: "demo_region"` 和“演示区域（非实时位置）”标签。
- `type` 为 `pet_hospital`、`pet_grooming`、`pet_store` 之一；`radius_m` 为整数 1000–20000，省略时默认 3000。旧架构指南流程图中的 `radius` 在实现时统一使用此处的 `radius_m`。
- 距离由 B 按 WGS84 查询点和地点坐标使用球面距离计算，四舍五入为非负整数米；仅返回计算距离不超过 `radius_m` 的地点，按距离升序并以 `id` 升序稳定打破并列。高德过滤半径不替代服务端距离校验；演示种子数据使用同一算法。
- 若用户拒绝定位且未配置高德，C 提供用户主动选择的“使用演示区域”入口；B 提供 `GET /api/v1/nearby/demo?type=pet_hospital&radius_m=3000`，使用明确配置的 WGS84 演示中心和种子数据，不需要高德或地址解析。不得自动进入演示区域，也不得将用户输入的地址描述为已解析或使用该地址计算位置。该显式入口响应必须标记 `search_center.source: "demo_region"`，并显示明确的非实时标签。
- `GET /api/v1/nearby` 与 `/api/v1/nearby/demo` 均返回 `200 NearbyResponse`，地点集合位于 `places`，无结果时为 `[]`。响应包含 `search_center`（实际用于距离计算的查询中心、中心来源及供页面展示的标签）、顶层 `source`（地点数据来源：`amap` 或 `demo`）和 `fallback_reason`（`null`、`amap_unavailable` 或 `amap_not_configured`）。`search_center.source` 是不同字段，表示查询中心来源：附近查询时为透传的 `user_location` 或 `resolved_address`；只有用户主动选择 `/nearby/demo` 时才是 `demo_region`。高德正常返回空列表时是顶层 `source: "amap"`、`places: []`、`fallback_reason: null`，不得当成上游失败。`/nearby` 因高德不可用或未配置而回退时，必须继续使用原请求中的 WGS84 查询中心计算距离并保留原 `search_center.source`/`label`，不得切换到配置的演示中心；仅地点数据改用演示种子数据，顶层 `source: "demo"`，并用相应 `fallback_reason` 标明降级。演示种子可能离原查询中心较远，故回退的 `places` 允许为空；此时 `source: "demo"` 加非空 `fallback_reason` 表示“已降级且没有匹配到附近演示地点”，不能推断真实附近没有服务。前端/Agent 应同时明确告知实时服务不可用、当前结果为演示数据；空列表只表示演示数据中无距离符合条件的地点。`/nearby/demo` 则使用配置的演示中心与演示地点，顶层 `source: "demo"`、`fallback_reason: null`、`search_center.source: "demo_region"`。调用失败且没有可用回退结果时返回统一错误体和 `UPSTREAM_ERROR`/`UPSTREAM_TIMEOUT`，不伪装成空结果。
- 拒绝定位时由 C 提供手动输入地址；B 提供 `POST /api/v1/locations/resolve`，请求体为 `{ "address": "...", "city": "..." }`：`address` 首尾空白去除后长度为 1–200；`city` 可选，去首尾空白后 1–20 字符，提供时限定解析城市（前端未填写时页面说明为全国搜索，不猜城市、不借用未授权定位）。后端串行双查高德 v5 `place/text`（地标 POI，提供 `city` 时附带 `citylimit=true`）与 v3 `geocode/geo`（结构化地址），任一路失败/超时即整体返回 `502 UPSTREAM_ERROR`/`504 UPSTREAM_TIMEOUT`，不静默降级为另一路结果；两路均无匹配才返回 `404 ADDRESS_NOT_FOUND`；输入校验失败返回 `422 VALIDATION_ERROR`；高德未配置返回 `503 SERVICE_UNAVAILABLE`，不根据字符串猜坐标。返回 `200` 和 `matches` 数组：按「geocode 门址/门牌号级 → POI（高德返回序）→ 其余 geocode」排序，geocode 按 `formatted_address` 去重、POI 按 `name+city+district+address` 去重后合并，上限 5 条（POI 足够多时低精度 geocode 候选被自然截断属预期，不为两路保留名额）。每项字段固定为 `formatted_address`、`name`、`city`、`district`、`level`、`match_kind`（`poi`|`geocode`）、WGS84 `location` 与 `data_source: "amap"`，字段恒存在但值可为 null：POI 候选 `name/city/district` 来自高德、`level` 为 null；geocode 候选 `name` 为 null、`level` 为高德级别原文（门址/道路/省等，仅供前端展示解析方式与精度，不作过滤依据）；首版不做 POI 类型过滤，公交站/地铁站等噪声候选由 `match_kind`、名称与地址展示由用户区分。POI 的 `formatted_address` 由省/市/区/详细地址非空段去重拼接（直辖市重复段跳过，详细地址缺失以行政区段兜底，全空回退名称）；不透出 `poi_id` 等厂商原始字段。多条候选均返回，由用户选择后再查询附近地点；不自动选择第一条，不得暗示第一条即准确匹配。串行双查使用 HTTPX 连接、读写及连接池等待的阶段超时 5 秒；这不是单次请求或双查的总时限，不保证 10 秒内结束。先失败先返回；前端等待上限为 15 秒，超时展示可重试提示，前端中止等待不保证后端请求同步取消。例如：`{"matches":[{"formatted_address":"上海市黄浦区人民大道185号","name":"上海人民广场","city":"上海市","district":"黄浦区","level":null,"match_kind":"poi","location":{"lat":31.230761,"lng":121.470680},"data_source":"amap"},{"formatted_address":"上海市黄浦区人民大道185号","name":null,"city":"上海市","district":"黄浦区","level":"门址","match_kind":"geocode","location":{"lat":31.242028,"lng":121.472874},"data_source":"amap"}]}`。地址和精确坐标仅用于本次请求，不写入业务数据库或日志；高德服务密钥仅由后端读取。

```json
{
  "places": [{
    "id":"amap:example",
    "name":"安心宠物医院",
    "category":"pet_hospital",
    "address":"示例路 18 号",
    "phone":null,
    "location":{"lat":39.9001,"lng":116.4001},
    "distance_m":860,
    "business_status":"unknown",
    "business_hours_today":"09:00-21:00",
    "navigation_url":null,
    "data_source":"amap"
  }],
  "search_center": {
    "location":{"lat":39.9001,"lng":116.4001},
    "source":"user_location",
    "label":"当前位置"
  },
  "source":"amap",
  "fallback_reason":null
}
```

`phone`、`navigation_url`、`business_hours_today` 可为 `null`；`business_status` 为 `open`、`closed`、`unknown`，不可确定时用 `unknown`。`business_hours_today` 为数据源返回的今日营业时间原文（高德可能是 `09:00-21:00`、`24小时营业` 等文本），缺失为 `null`，仅作展示，解析由后端完成。`business_status` 语义：`demo` 地点为演示固定值、不代表真实营业；`amap` 地点由后端按北京时间从 `business_hours_today` 推算——解析成功时为 `open`/`closed`（多时段取并集，跨午夜区间如 `10:00-03:00` 按次日结束处理；今日场次未开始的凌晨时段若昨日场次可能仍在营业则保守 `unknown`），缺失或无法解析时为 `unknown`。前端仅在 `business_hours_today` 非 `null` 且 `business_status` 非 `unknown` 时把状态标注为「按营业时间推算」；`business_hours_today` 非 `null` 而 `business_status` 为 `unknown` 时可展示原文，但不得给出开关门结论。有导航链接时必须由用户主动打开。空电话显示“暂无电话”。`distance_m` 为非负整数，单位米。

数据来源和 ID 约定：真实高德数据使用 `data_source: "amap"`、`id: "amap:<高德地点 ID>"`；种子演示数据使用 `data_source: "demo"`、`id: "demo:<稳定的演示地点 ID>"`。前端和 Agent 必须明确标注演示数据，不能称为实时结果。高德不可用时如果回落演示数据，也必须标注来源；不能提供真实导航时 `navigation_url` 为 `null`。

演示区域响应沿用 `NearbyResponse` 结构，顶层 `source` 为地点数据来源 `demo`、`fallback_reason` 为 `null`；`search_center.source` 为查询中心来源 `demo_region`，`search_center.label` 明确为“演示区域（非实时位置）”。使用部署配置的演示中心，不把输入地址映射到此中心。该入口仅展示演示地点，地点的 `data_source` 与 ID 保持 `demo`。

`GET /api/v1/places/{place_id}?lat=39.9001&lng=116.4001` 返回 `200 Place`；详情中的 `distance_m` 依赖查询中心，因此必须附带 `lat`、`lng`，规则同上。按 ID 来源只查询对应数据源：`amap:<id>` 只查高德，`demo:<id>` 只查演示目录。对象不存在返回 `404 PLACE_NOT_FOUND`；高德未配置或查询失败时对 `amap:<id>` 返回可识别的 `503 SERVICE_UNAVAILABLE`、`502 UPSTREAM_ERROR` 或 `504 UPSTREAM_TIMEOUT`，绝不静默替换成演示地点；演示地点也不回退为高德结果。地图与列表使用同一 `NearbyResponse.places` 结果集；地图渲染失败需保留列表或给出可理解错误。

实现状态（P1-9）：配置 `AMAP_WEB_SERVICE_KEY` 后 `/nearby` 走高德 v5 `place/around`（按类别关键字召回、WGS84↔GCJ-02 转换、服务端距离过滤、`(distance_m, id)` 稳定排序、按高德地点 ID 去重），未配置/失败按上述语义回落演示数据；`amap:` 详情走 v5 `place/detail`（503/502/504/404 语义如上）。高德 `business.opentime_today` 原文透出为 `business_hours_today`，`business_status` 按北京时间推算（多时段/跨午夜/`24小时营业` 均覆盖，跨午夜凌晨场保守 `unknown`），缺失或无法解析时保留 `unknown`，`navigation_url` 保持 `null`。`business_hours_today` 为新增字段、结构兼容：旧前端忽略新字段仅作过渡兼容，C 同步「今日营业时间」展示与「按营业时间推算」标注后才作为新行为验收。2026-11-05 已按 Issue #82 用真实 Key 抽查 75 个宠物 POI（记录见 TASKS.md 进展与 PR 描述）；测试均使用模拟响应，不消耗真实配额。

实现状态（P1-10）：`POST /api/v1/locations/resolve` 已按上述契约实现（Issue #62 冻结稿）：串行双查高德 v5 `place/text`（适配器收敛为 `AMapLandmarkCandidate`）与 v3 `geocode/geo`（含 `level/city/district` 解析），候选按门址级 geocode → POI → 其余 geocode 排序、两路分别去重、上限 5 条；任一路失败/超时整体 502/504，无匹配 404、未配置 503，无演示回退。前端把用户所选候选作为 `/nearby` 查询中心并以 `center_source=resolved_address` 查询（同时覆盖 POI 与 geocode 选点）；导航链接由前端把 WGS84 转为 GCJ-02 后生成，仅对 `data_source: "amap"` 地点提供且由用户主动打开。新增字段保持结构兼容，但双查改变了候选内容与顺序：旧前端忽略新字段仅作过渡兼容，C 同步展示字段、城市输入与回归测试后才作为新方案验收。测试均使用模拟响应，不消耗真实配额；实施 PR 内以真实 Key 人工验证一次（人民广场/东方明珠/人民大道185号/万达广场/无城市跨城样例，覆盖有无 `city` 两种），结果脱敏回贴 Issue #62。

**P1-7 评审需明确回复：**是否确认 `NearbyResponse` 外壳及空结果/降级状态、HTTP 与 Agent 工具 `center_source` 默认值和原样传递规则、回退沿用原查询中心且允许空演示结果、顶层 `source` 与 `search_center.source` 的字段路径及语义、具体地址由前端自持展示、WGS84/GCJ-02 转换责任和服务端距离过滤、三类地点及排序规则、手动地址解析候选选择与错误行为、拒绝定位时显式选择演示区域的流程，以及详情接口按 ID 来源查询且不跨来源回退。以上未获 A/C 确认前，不据此开始 P1-8/P1-9 的实现。
