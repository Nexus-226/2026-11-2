# Pet Agent

三人协作的宠物助手项目。已有宠物资料页面、聊天页面、宠物 CRUD、会话持久化和 Qwen Provider；配置 LLM_API_KEY 时使用真实模型，未配置时使用 MockProvider。P0 已验收完成；P1-1 契约已获 A/C 确认，P1-2 记录后端已合并（PR #34），记录页面已合并（PR #37）；P1-4 提醒后端已合并（PR #38），C 提醒页面已随 PR #39 合并；A 侧 Agent 记录/提醒工具在 PR #42 评审；P1-8 演示数据版附近服务后端已在本 PR 实现（页面集成见 PR #43）；真实高德与 POI/地址双查已接入；P1-10/P1-12 已由 A/B/C 在 [Issue #67](https://github.com/Nexus-226/2026-11-2/issues/67) 确认完成。P1-6 与整个 P1 的收尾另行核对。

## 目录与分工

```text
frontend/                     C：React + TypeScript 前端
  src/app/                    入口与应用
  src/pages/                  已有对话、宠物资料、日常记录、待办提醒页面；附近服务页面集成见 PR #43
  src/components/             chat / map / common 组件
  src/api/ hooks/ types/ styles/
  tests/
backend/                      Python + FastAPI 后端
  app/agent/                  A：Agent Runtime、提示词与工具
  app/api/ core/ schemas/     B：路由、配置和数据结构
  app/services/ db/           B：业务服务和数据访问
  app/integrations/           B：第三方适配
  migrations/ tests/
docs/                         架构、接口及技术决策
scripts/                      开发辅助脚本
```

A 负责 Agent、工具协议和 LLM 接入；B 负责后端 API、数据库与业务服务；C 负责前端和交互。LLM Provider 的边界由 A、B 共同确定。前端通过 FastAPI 访问后端；Agent 通过受控工具和服务访问数据及外部能力。地图查询是 P1；演示数据版附近服务后端已实现并明确标注来源（页面集成见 PR #43），真实高德、手动候选选点与 Agent 附近工具已接入，P1-12 最终验收见 [Issue #67](https://github.com/Nexus-226/2026-11-2/issues/67)。

原始《Pet Agent 架构与开发指南》第 9 节将 A、C 的职责写反；本仓库以当前明确的 **A：Agent、B：后端、C：前端** 分工为准。

开发前请先评审：[技术栈与分层约定](docs/TECH_STACK.md)、[接口契约草案](docs/API.md) 和 [仓库现状与缺项](docs/REPOSITORY_STATUS.md)。Git 协作见 [PR 指南](docs/PR_GUIDE.md)。

项目优先级：P0 完成宠物资料与 Agent 对话闭环及会话上下文修复；P1 按“日常记录 → 站内提醒 → Agent 查询 → 附近宠物服务”推进；P2 为就诊摘要等增强项。负责人、依赖、状态和审核安排见 [项目任务表](docs/TASKS.md)。

## 技术栈

| 部分 | 约定 | 当前状态 |
|---|---|---|
| 前端 | React + TypeScript + Vite | 宠物资料和聊天页面支持演示；真实接口联调待完成 |
| 后端 | Python + FastAPI + Pydantic | 健康检查、宠物资料 CRUD、统一错误响应、对话路由和会话消息持久化已实现 |
| Agent | Python Agent 模块、受控工具和 LLM Provider | Runtime、宠物工具、对话编排、Qwen/Mock Provider 已接入；跨请求会话历史传入模型待修复（P0-8） |
| 数据 | SQLite + SQLAlchemy 2 + Alembic | 本地演示用户与宠物资料通过 SQLite/SQLAlchemy 持久化；Alembic 迁移已配置 |
| 地图（P1） | 高德开放平台 Web 服务 v5（P1-9 已实现后端真实接入）；P1-8 演示版无需 Key；C 页面已随 PR #43 合并 | 真实 POI 查询、去重、排序与失败回落演示已实现；Key 与配额由部署配置 |

当前真实模型通过 DashScope 的 OpenAI 兼容接口接入，默认 qwen-plus；可通过现有环境变量配置，Provider 抽象保留。前端锁定的依赖版本见 `frontend/package-lock.json`，详细选型和边界见 [技术栈文档](docs/TECH_STACK.md)。

## 接口速览

业务接口使用 `/api/v1` 前缀：

| 接口 | 用途 | 阶段 |
|---|---|---|
| `GET /health` | 服务健康检查 | 已实现 |
| `GET /api/v1/pets`、`POST /api/v1/pets` | 查询列表、新建宠物 | P0，已实现 |
| `GET /api/v1/pets/{pet_id}`、`PATCH /api/v1/pets/{pet_id}`、`DELETE /api/v1/pets/{pet_id}` | 查看、修改、删除宠物 | P0，已实现 |
| `POST /api/v1/chat` | Agent 对话，JSON 回复；有 LLM_API_KEY 使用 Qwen，否则使用 MockProvider | P0，路由与会话存储已实现；模型历史上下文待修复 |
| `GET/POST /api/v1/records`、`GET/PATCH/DELETE /api/v1/records/{record_id}` | 日常记录查询及 CRUD | P1-2，后端已随 PR #34 合并；前端页面见 PR #37 |
| `GET/POST /api/v1/reminders`、`GET/PATCH/DELETE /api/v1/reminders/{reminder_id}` | 站内提醒和待办查询及 CRUD | P1-4，后端已随 PR #38 合并；C 页面见 PR #39 |
| `GET /api/v1/nearby`、`GET /api/v1/nearby/demo`、`GET /api/v1/places/{place_id}` | 附近服务查询、演示区域查询和地点详情 | P1-8 演示数据版后端见 [PR #40](https://github.com/Nexus-226/2026-11-2/pull/40)；页面见 PR #43，高德及端到端验收见 Issue #67 |

宠物字段、记录/提醒错误格式、A/B 工具边界和地图参数以 [接口契约](docs/API.md) 为准。SQLite 数据默认写入运行目录下的 `pet_agent.db`，可用 `PET_AGENT_DATABASE_URL` 修改连接地址。记录/提醒契约已由 A/C 确认；其他 P1 接口约定仍需三人评审。实现时如有变更，同步更新文档和测试。

宠物资料的字段已决定：P0 使用可为空的 `birthday` 和 `notes`，不新增 `age`、`health_notes`。生日不详时可在 `notes` 写大概年龄，不推测生日；其他接口约定仍需评审。

## 启动

需要 Python 3.10+ 和 Node.js 20.19+（或 22.12+）。在项目根目录分别运行：

```powershell
# 后端
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e "./backend[dev]"
python -m uvicorn app.main:app --app-dir backend --reload
```

访问 `http://127.0.0.1:8000/health`，应返回 `{"status":"ok"}`。

```powershell
# 前端：另开终端
cd frontend
npm install
npm run dev
```

前端地址以 Vite 的终端输出为准。开发时 `/api` 和 `/health` 会代理至 `http://127.0.0.1:8000`，可通过前端环境变量 `VITE_API_PROXY_TARGET` 修改代理目标。

宠物资料页默认使用本地演示数据，仅保存在当前浏览器，不会同步后端。在 `frontend/.env.local` 中设置 `VITE_PET_DATA_SOURCE=api` 并重新启动前端，即切换到 `/api/v1/pets`；前后端仍需完成联调。接口失败时页面显示错误，不会自动回退到演示数据。切换模式不会迁移已有演示资料。

聊天页默认显示固定的演示回复，不连接真实模型，聊天记录只保留在当前页面。在 `frontend/.env.local` 设置 `VITE_CHAT_DATA_SOURCE=api` 并重启前端，即可切换到已实现的 `POST /api/v1/chat`；后端配置 LLM_API_KEY 时使用真实 Qwen Provider，否则使用 MockProvider；请求失败时前端不会自动生成模拟回复。若对话需要关联宠物，还应设置 `VITE_PET_DATA_SOURCE=api`，并启动后端：本地演示宠物的 ID 不能用于后端对话接口。

取消操作只停止前端等待，服务端可能仍在处理；超时或中断后重试可能产生重复请求。前后端仍需联调会话 ID、宠物 ID、错误格式和取消行为。

LLM 配置模块已读取环境变量，并在 python-dotenv 可用时加载本地 `.env`；`.env.example` 只是示例，不会被直接加载。现有配置为 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`，后两项默认分别为 `https://dashscope.aliyuncs.com/compatible-mode/v1` 和 `qwen-plus`。数据库连接可通过 `PET_AGENT_DATABASE_URL` 设置。真实密钥和本地数据库不要提交到 Git。

会话记录已持久化，但当前模型请求没有携带数据库历史；复用 session_id 尚不代表模型记得上一轮。修复见 P0-8。本地 API 模式与真实模型能力已具备；全流程及取消/超时验收仍按任务表逐项记录，本说明不替代 P0-5/P0-6 的审核状态。

## 检查

```powershell
# 项目根目录，已安装后端 dev 依赖
python -m pytest backend/tests

# frontend 目录，已安装依赖
npm run build
npm test
```

Python 使用 Ruff 做检查与格式化，前端使用 Prettier；版本分别固定在 `backend/pyproject.toml` 和 `frontend/package-lock.json`。对本次改动的文件单独运行命令，例如：

```powershell
# 项目根目录：把路径换成实际改动的 Python 文件
python -m ruff check backend/app/main.py
python -m ruff format --check backend/app/main.py
python -m ruff format backend/app/main.py

# frontend 目录：把路径换成实际改动的前端文件
npm run format:check -- src/app/App.tsx
npm run format -- src/app/App.tsx
```

本 PR 不批量格式化现有文件。`frontend/.prettierignore` 排除了生成文件、锁文件和 Markdown。ESLint 尚未配置，待 C 开发业务页面时确定规则。

`.gitattributes` 让 Git 新检出或重新写入的文本文件使用 LF，即使本机设置了 `core.autocrlf=true`；已有工作区文件不会立即自动转换。请先保存本地改动，再按需用编辑器或对应格式化工具转换涉及的文件。

应用启动时会自动执行 Alembic `upgrade head`。开发环境也可在 `backend/` 目录手动运行 `python -m alembic upgrade head`。当前优先完成 P0 联调验收和上下文修复，再推进 P1 记录、提醒与 Agent 查询；附近服务演示版后端已实现（见下文 P1-8），页面与真实高德后续已接入，P1-12 验收见 Issue #67。新增功能尚无已实现接口，其契约由 P1-1 另行确认，不在本说明中预设。

## P1-3：日常记录页面（C 侧开发）

导航“日常记录”支持疫苗、驱虫、洗澡、体重记录的添加、编辑、确认删除及日期倒序时间线，可按宠物、类型和日期范围筛选。默认是浏览器本地演示数据，与后端数据分开。

设置 `VITE_RECORD_DATA_SOURCE=api` 后重启前端可使用 `/api/v1/records`；关联真实宠物同时设置 `VITE_PET_DATA_SOURCE=api`。接口失败明确显示错误，不自动回退演示数据。此开关不迁移本地记录。已与 B 的 P1-2 记录后端完成真实联调；提醒创建见 P1-4，Agent 记录查询见 P1-5。

## P1-4：待办提醒页面（C 侧开发）

导航“待办提醒”支持创建、编辑、完成、取消和删除提醒，按到期日期分组展示（逾期/今天/即将/更晚，以及已完成/已取消）。分组直接使用后端返回的 `due_group`，前端不重新计算。默认是浏览器本地演示数据，与后端数据分开。

设置 `VITE_REMINDER_DATA_SOURCE=api` 后重启前端可使用 `/api/v1/reminders`；关联真实宠物同时设置 `VITE_PET_DATA_SOURCE=api`。接口失败明确显示错误，不自动回退演示数据。此开关不迁移本地提醒。已与 B 的 P1-4 后端（PR #38）完成真实联调。

## P1-8：附近服务演示版后端（B 侧实现）

后端已随 PR #40 合并；前端页面由 C 侧单独集成（页面集成 PR 见 #43，已合并），参考实现保留在分支提交 `465e513`（未运行前端测试与构建，不能据此验收）。后端新增：

- `GET /api/v1/nearby?lat=..&lng=..&type=..&radius_m=..`：未配置高德时按 P1-7 契约回退演示种子数据，返回 `source: "demo"`、`fallback_reason: "amap_not_configured"`，并沿用请求中心计算距离；配置 Key 后走真实 POI 查询，见下文 P1-9。
- `GET /api/v1/nearby/demo?type=..&radius_m=..`：用户主动选择的演示区域，使用 `PET_AGENT_DEMO_CENTER_LAT/LNG` 配置的演示中心（未配置时用内置默认值），`search_center.source` 固定为 `demo_region`。
- `GET /api/v1/places/{place_id}?lat=..&lng=..`：`demo:` 前缀查演示目录；`amap:` 前缀只查高德：未配置返回 `503 SERVICE_UNAVAILABLE`、失败/超时返回 502/504、不存在 404，绝不静默替换为演示数据（见下文 P1-9）。

演示地点坐标按相对演示中心的偏移生成，并收敛到 WGS84 合法范围（纬度 [-90, 90]、经度 [-180, 180]），边界配置（如纬度 90、经度 180）不会产生非法坐标。Service 层暂依赖调用方校验坐标、类别与半径（HTTP 路由已校验），P1-11 工具直调 Service 前需与 A 明确校验责任。手动地址解析见下文 P1-10。
## P1-8：附近服务页面（C 侧）

导航“附近服务”通过 FastAPI 的 `/api/v1/nearby` 和 `/api/v1/nearby/demo` 查询三类地点，支持半径筛选、地点列表与位置示意图双向选中。位置示意图不是道路地图，不提供导航。

需启动包含 PR #40 的后端；前端沿用 Vite 的 `VITE_API_PROXY_TARGET` 代理，无需新增数据模式开关。页面不会自动定位或自动进入演示区域，用户拒绝定位后仍可点击“使用演示区域”。接口错误明确展示，不在前端伪造演示结果。地点与查询中心来源、回退原因及空结果按后端响应展示；定位仅保存在当前页面内存。

本段记录 P1-8 首版范围；后续已接入手动地址解析、高德和 Agent 附近查询（见下文及 Issue #67），仍未接入真实地图 SDK。P1-8 真实联调已由用户确认通过（2026-11-03），PR #40 已合并，C 页面 PR #43 已合并。

## P1-9：高德真实接入（B 侧实现）

配置 `AMAP_WEB_SERVICE_KEY`（高德 Web 服务 Key）后，`/api/v1/nearby` 通过高德 POI 2.0（v5 `place/around`）查询真实地点：按类别使用关键字召回（宠物医院/动物医院、宠物美容/SPA/洗护、宠物用品/宠物店），请求前把 WGS84 转为 GCJ-02，返回坐标转回 WGS84；坐标转换收敛在后端 `app/services/amap.py`，不透出高德原始响应或未转换坐标。距离仍由服务端按 WGS84 球面距离计算并过滤半径，结果按 `(distance_m, id)` 稳定排序并按高德地点 ID 去重；`category` 由高德类型文本映射，`business_status` 固定 `unknown`（高德无可靠营业状态），`phone` 取自高德 `business.tel`，`navigation_url` 保持 `null`。高德正常返回空列表时 `source: "amap"`、`places: []`，不算失败。

高德未配置或调用失败时按 P1-7 契约回落演示种子数据并标注来源：未配置为 `fallback_reason: "amap_not_configured"`，超时/失败为 `fallback_reason: "amap_unavailable"`；回落沿用原查询中心与 `search_center`，不切换演示中心。`GET /api/v1/places/amap:<id>` 走 v5 `place/detail`：未配置 503、上游失败 502、超时 504、不存在 404，绝不静默替换为演示数据。密钥仅由后端读取，不写入日志或错误响应。相关测试（25 项）全部使用 httpx MockTransport 模拟高德响应，不依赖真实 Key 或配额；坐标转换以 eviltransform 公开测试向量校验。

## P1-10：定位用途说明与手动地址回退（B/C 协作）

拒绝定位或不便使用定位时，“附近服务”页面提供手动地址回退：输入地址（可选填城市）→ `POST /api/v1/locations/resolve` 解析为候选 → 用户自行选择候选 → 以 `center_source=resolved_address` 查询附近。后端按 Issue #62 冻结契约串行双查高德 v5 `place/text`（地标 POI）与 v3 `geocode/geo`，坐标转换与字段收敛复用 `app/services/amap.py`：候选含 `formatted_address`、`name/city/district/level`、`match_kind`（poi/geocode）、WGS84 `location` 与 `data_source`，按门址级 geocode → POI → 其余 geocode 排序、两路分别去重后上限 5 条，`city` 可选限定城市（未填写为全国搜索）；多条候选全部返回且不自动选择第一条；任一路失败/超时整体 502/504，两路均空 404 `ADDRESS_NOT_FOUND`、输入非法 422 `VALIDATION_ERROR`、未配置高德 503，均不做演示回退或字符串猜坐标。地址与坐标仅用于本次请求，不写入业务数据库或日志；页面明确说明定位用途，地址输入不自动触发任何查询。导航链接由 C 侧把 WGS84 转为 GCJ-02 后生成（`src/lib/coords.ts`，以 eviltransform 同源向量测试），仅在高德真实地点（`data_source: "amap"`）的卡片上提供，用户点击后在新窗口打开；演示地点为虚构数据，不提供导航入口。



## P1-10 / P1-12 验收完成（2026-11-04）

C 的 [最终验收记录及 A/B 确认](https://github.com/Nexus-226/2026-11-2/issues/67) 已齐备，P1-10/P1-12 已完成。覆盖真实高德三类查询、来源/空结果、城市与 POI 候选选择、中心切换、列表/位置示意图及外部导航终点；后端 233 项、前端 65 项测试与构建通过（记录中的执行结果，本次仅更新文档）。定位成功采用公开坐标模拟回调，未验证设备定位精度或系统权限弹窗；真实模型为抽查，工具硬失败为受控注入，不声称真实高德故障演练。P1-6、其他收尾事项和整个 P1 完成状态另行核对。

## P2-1：其他宠物具体物种（C 侧候选实现）

宠物资料选择“其他”时可选填具体物种，保存后列表和详情显示“其他（兔）”；为空仍显示“其他”。切回猫狗会清空并显式提交 null。去首尾空白后最多 50 个 Unicode 码点，不做 NFC 或内部空白折叠，超限提示且保留输入。

沿用 `VITE_PET_DATA_SOURCE`：默认本地演示可保存、编辑并刷新恢复，旧浏览器档案缺失该字段时补为 null；API 模式要求响应总含 `other_species`，接口错误或缺字段时明确失败，不回退演示数据。现有存储不会被自动清空。

本候选包含最终写入字段，需 B 的完整后端（Schema、迁移、校验与持久化）就绪后才能启用和合入真实写入功能；PR #68 的只读前置项尚不足以支持保存。C 侧已完成自测及部分真实接口/模型验证，用户于 2026-11-04 确认十步手工联调均通过（未留截图）；证据来源与边界见 [C 侧验收记录](docs/P2-1_C_ACCEPTANCE.md)。PR #69 转正式待审，尚未合并，不代表 P2-1 整体交付。

P2-1 具体物种的首尾空白处理与后端 Python str.strip 一致：U+FEFF 不作为空白删除，U+0085 与 U+001C–U+001F 按空白处理；读取和再次保存不改写其余字符。

## P2-2：体重趋势图（待审核）

日常记录页选择具体宠物后可查看体重趋势，支持近 30 天、近 90 天及全部记录。图表独立于时间线类型/日期筛选，按实际发生日期绘制，公斤为统一单位；同日多次称重保留全部明细。保存、修改、删除后随记录一起刷新。空范围可点击“添加体重记录”，加载失败可单独重试。图表只展示称重变化，不提供诊断。数据来源沿用 `VITE_RECORD_DATA_SOURCE`；真实记录需同时设置 `VITE_PET_DATA_SOURCE=api`。已按 PR #73 的消费约定对接，前端模拟测试与构建通过；真实接口及浏览器视觉验收待完成，尚未合并交付。
