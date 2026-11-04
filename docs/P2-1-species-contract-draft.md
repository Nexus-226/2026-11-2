# P2-1 字段契约草案：其他宠物具体物种（A/B 方向已确认，修订待最终审核）

> C 侧整理，A/B 已在 PR #63 确认字段方向；本次按评论修订，待最终审核后冻结。尚未实现 API / Schema / 前端 / Agent。

## 背景与目标

当前 `species` 仅 `dog` / `cat` / `other`，`other` 无法结构化标识「兔、仓鼠、鹦鹉」等具体物种。本项在**保留 dog/cat/other 兼容**的前提下，让 `other` 可填写具体物种；范围严格限制为**档案字段 + Agent 读取**，不扩展专属健康逻辑。

## 字段定义（A/B 已确认方向）

- 字段名：`other_species`，不采用 `species_detail`。
- 类型：`string | null`。
- 含义：`species == "other"` 时的具体物种文本；`dog` / `cat` 时为 `null`。
- 约束：去首尾空白后非空、标准化后 ≤50 Unicode 码点（空串转 `null`）；`null` 表示未填。

## 校验（服务端，关联校验）

- `species != "other"` 时，`other_species` 必须为 `null`；传非空 → `422 VALIDATION_ERROR`。
- `species == "other"` 时，`other_species` 可空（`null`），或去首尾空白后非空、标准化后 ≤50 Unicode 码点的字符串（空串转 `null`）。
- 去除首尾空格后为空 → 等价存 `null`。
- `PATCH`：省略表示不修改；`null` 清空；空对象 / 未知字段沿用既有 `422`。

## 兼容性

- 不新增 `species` 枚举值，保留 `dog` / `cat` / `other`；现有物种判断逻辑不变。
- 所有存量宠物（包括 `other`）数据 `other_species` 回填 `null`。
- 迁移：新增可空列，不收紧既有约束。

## API 变更

- `PetCreate` / `PetRead` / `PetUpdate` 增加 `other_species: string | null`。
- 响应中 `other_species` 总出现（`dog`/`cat` 时为 `null`），与 `breed`/`notes` 一致。
- 错误：违反关联校验 → `422 VALIDATION_ERROR`（复用既有统一错误结构）。

## 前端（C）

- 表单：`species` 选「其他」时显示 `other_species` 输入；切回 dog/cat 时清空并隐藏。
- 列表 / 详情：`other` 且 `other_species` 非空时展示「其他（兔）」；为空时「其他」。
- 演示与 API 双模式同步该字段；失败保留输入，不自动回退演示数据。

## Agent（A）

- `get_pet_profile` / `list_pets` 继续直接返回共用 `PetRead`，新增字段通过 `_to_jsonable` 的 `model_dump(mode="json")` 自动透出，工具函数无需改动。
- C 在实施 PR 调整 `prompts.py`，可选补充 `pets.py` 工具 description，并在 `test_agent_tools.py` 增加序列化断言；A 评审并参与真实模型验收抽查，确认准确引用、不默认猫狗。
- 提示词：`species == "other"` 且 `other_species` 非空时按具体物种称呼（如「兔」）；`other_species` 为空时如实说「其他宠物（未填具体物种）」；不得默认按猫狗处理，也不得编造具体物种。

## 测试

- B：关联校验（dog + 非空 `other_species` → 422；other 空 / 非空）、迁移回填、CRUD 持久化。
- C：表单显示 / 隐藏 / 清空、保存编辑刷新、演示与 API 双模式。
- A：工具返回字段、模型准确引用且不默认猫狗。

## A/B 评论确认记录与修订状态

[B 评论](https://github.com/Nexus-226/2026-11-2/pull/63#issuecomment-6625654005)与 [A 评论](https://github.com/Nexus-226/2026-11-2/pull/63#issuecomment-6625665826)均认可：字段名 `other_species`、上限 50 Unicode 码点、dog/cat 携带非空值显式返回 422、other 允许 null。本次纳入评论澄清，待最终审核；不代表功能已实现。

## 精确语义

### 标准化与输入类型

- 创建时省略 `other_species` 等同 `null`；PATCH 省略表示不修改，显式 `null` 表示清空。
- 仅接受字符串或 `null`；数字、布尔值、数组和对象均返回 `422 VALIDATION_ERROR`。
- 字符串先去除首尾空白，空串转为 `null`，再检查标准化后长度（最多 50 个 Unicode 码点），最后校验与 species 的关联。仅移除首尾空白；不做 NFC 或其他 Unicode 归一化，不改写其余字符，不折叠内部空白。该 strip→null 规则仅用于新字段，不顺带改变 breed/notes 的既有行为。
- 前端按 Unicode 码点计数（如 `[...value].length`），不能使用按 UTF-16 单元计数的 `value.length` 作为长度判断。
- PATCH 的 `name:null` / `species:null` 返回既有 `422`，而 `other_species:null` 是合法清空操作，不能套用 name/species 的非空守卫。

### PATCH 按完整对象联合校验

Service 读取已有宠物，将仅本次出现的字段合并到现有对象，对完整候选对象执行标准化及关联校验；同一请求体中已明确的冲突可由 Schema 提前拦截，但不能代替 Service 的完整对象校验。全部通过后才持久化。失败不得部分修改资料。仅凭 PetUpdate 请求体无法判断省略 species 时的实际物种。

| 原资料 | PATCH 请求 | 预期 |
|---|---|---|
| other / 兔 | `{"name":"团团"}` | 保留 other / 兔 |
| other / 兔 | `{"other_species":" 仓鼠 "}` | 保存 other / 仓鼠 |
| dog / null | `{"other_species":"兔"}` | 422，原资料不变 |
| other / 兔 | `{"species":"cat"}` | 422，省略字段不自动清空 |
| other / 兔 | `{"species":"cat","other_species":null}` | 保存 cat / null |
| cat / null | `{"species":"other","other_species":"兔"}` | 保存 other / 兔 |
| other / 兔 | `{"other_species":"   "}` | 保存 other / null |

前端切回 dog/cat 时必须显式提交 `other_species:null`；仅隐藏输入框或省略字段不能清除服务端旧值。空对象、未知字段沿用既有 422，宠物不存在沿用 `404 PET_NOT_FOUND`。

关联错误沿用 `422 VALIDATION_ERROR` 和既有错误结构；message 应区分“dog/cat 携带非空具体物种”与“从 other 切回猫狗时未显式清空原具体物种”，便于定位表单问题，具体文案在实施 PR 确定，不新增错误码或响应字段。

### 存量与发布兼容

- 数据库通过一个 Alembic revision 新增可空 `String(50)` 列；SQLite 不强制 VARCHAR 长度，长度限制必须由应用层校验保证，不能依赖列长兜底。所有存量宠物（包括 other）值均为 null，不从 breed、notes 或聊天文本推断具体物种。保留原记录及已有字段。
- 演示数据沿用现有 localStorage：读取旧记录缺失的新字段时补为 null，后续保存包含该字段，不清空用户已有演示档案。
- 保留 dog/cat/other 枚举不等于旧服务端已支持新字段：现有 Schema 禁止未知字段。实施时先部署后端及迁移，再启用前端新字段；API 模式不将未知字段或字段缺失错误伪装成成功或演示结果。
- 工具继续经 Service 返回共用 PetRead；需验证运行时序列化后的 get_pet_profile 和 list_pets 结果均带新字段，而非只检查类型定义。字段文本仅作为档案数据，不作为模型指令。

### 补充验收

- 后端覆盖上表、空值/全空白、50/51 码点边界、错误输入类型、失败不落库，以及含 dog/cat/other 旧数据的升级迁移、CRUD 和重启读取。
- 前端覆盖旧演示数据读取、猫狗与其他互切、显式清空请求、API 保存编辑刷新、失败保留输入；明确验证非 BMP 字符（如 `𠮷`）重复 50 次允许、51 次拒绝，前后端结果一致；不可被 HTML maxlength 的 UTF-16 计数提前限制。
- Agent 用模拟 Service/Provider 验证真实工具输出；具体物种、未知物种、修改后重新查询和宠物切换均不混用。真实模型引用另行抽查，不把一次通过当作永久保证。

## 分工与实施条件

按用户指派，P2-1 由 **C 主责跨端实现，B 评审后端与迁移，A 评审 Agent 适配，A/B/C 联调验收**。依赖 P0-5、P0-7、字段契约确认及 P1 收尾验收不变。本契约 PR 不启动功能实现，不将功能标记完成。

- C：承担前端、Schema、Service 联合校验、数据库迁移、提示词适配、相关测试和 API 文档；负责提交、问题修复及验收证据。
- B：评审 Schema、标准化、PATCH 校验、统一错误、迁移和后端测试；与 C 确认旧库升级、真实 CRUD、失败不落库及重启读取。
- A：评审提示词、工具输出和序列化测试；与 C 确认两个资料工具携带新字段、真实模型准确引用、不默认猫狗及宠物切换隔离。工具函数原则上无需修改。
- A/B 给出各自范围的明确评审结论；共同联调通过、合并并验证后才计完成。原“B 承接后端、A 编写适配”的分工由本次用户指派替代。

### 审核与联调时机

| 阶段 / 触发时机 | C 的交付 | A/B 参与与通过条件 |
|---|---|---|
| 1. 本契约 PR 合并前 | 补齐契约及分工，保留功能未开始 | A/B 最终确认修订语义；获得所需评审后合并契约，不等于功能验收 |
| 2. 契约冻结、P1 收尾验收满足后 | 从最新 main 建实施分支；实现后端、前端、提示词、文档及测试；可开草稿 PR 提前评审 | 后端候选实现及测试就绪即请 B 审 Schema、标准化、PATCH 完整对象校验、错误和迁移；Agent 候选实现及测试就绪即请 A 审提示词与两个工具的序列化证据。无需等全部页面完成才审 |
| 3. 实施 PR 自测通过、合并前 | 提供固定提交版本、后端 pytest/Ruff、前端测试/构建/本次文件 Prettier 结果及待验场景 | B 确认后端与迁移实现；A 确认 Agent 适配；C 修复问题。代码评审不替代真实联调 |
| 4. 评审问题修复后、实施 PR 合并前 | 用同一提交版本启动真实前后端，演示建档、编辑、物种互切、清空、刷新、失败保留输入及旧演示存储 | B 与 C 验证含 dog/cat/other 旧库的迁移、真实 CRUD、422 不落库和重启读取；A 与 C 验证两个工具实际输出、新/未知物种、修改后重查和宠物切换，再做真实模型引用抽查 |
| 5. 联调发现问题时 | 修复并更新提交、证据和对应测试 | 涉及后端请 B 复审、涉及 Agent 请 A 复审；重跑受影响场景。若改变契约先获 A/B 确认并同步文档；最终验收须对应最新待合并提交 |
| 6. 实施 PR 合并及合并后 | A/B 各自范围明确通过、联调证据齐备后合并；在合并后的 main 快速验证启动及核心链路 | 三方确认无回归后才标记 P2-1 已完成；仅模拟通过、缺少真实模型抽查或真实接口联调时保留待验收并注明缺项 |

联调证据记录提交版本、环境/数据来源、操作或输入、预期与实际、工具调用及结果；使用脱敏测试数据，不提交真实密钥、数据库或真实对话。
