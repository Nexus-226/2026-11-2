# P2-1 字段契约草案：其他宠物具体物种（A/B 方向已确认，修订待最终审核）

> C 侧整理，A/B 已在 PR #63 确认字段方向；本次按评论修订，待最终审核后冻结。本 PR 不包含运行代码，各侧分支实现进展不等于主分支已交付。

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
- A 在自己的实施 PR 调整 `prompts.py`，可选补充 `pets.py` 工具 description，并在 `test_agent_tools.py` 增加序列化断言；A 负责本侧实现与修复，并参与真实模型验收抽查，确认准确引用、不默认猫狗。
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

按用户最新要求恢复原职责：**B/C 主，A 适配工具；A 做 Agent，B 做后端，C 做前端，A/B/C 共同联调验收。** 各自负责本侧实现、测试、提交和问题修复，C 不跨端；评审和联调不表示接管其他成员的实现。

依赖 P0-5、P0-7、字段契约确认及 P1 收尾验收不变。本 PR 仅修改契约和任务文档，不交付运行代码；各侧分支进展与主分支合并、验证状态分开记录。

### 各自一次完成的交付范围

下列为各侧完整工作包，同一成员可在本次范围内连续完成实现、测试和文档，不按单个字段或单个场景反复拆交；跨侧依赖明确后由原负责人接续。PR 仍保持范围单一、可独立验证。

| 成员 | 实现范围与完整交付 | 本侧自测及证据 |
|---|---|---|
| A：Agent | 维护 `backend/app/agent/`：`prompts.py` 按具体物种称呼、缺失时说明未填、不默认猫狗、不编造；`pets.py` 工具 description 按需补充；`test_agent_tools.py` 补两个资料工具的序列化断言。复用 `PetRead` 与现有 `_to_jsonable`，工具函数无需重复改写。负责本侧问题修复 | 通过模拟 Service/Provider 验证 `get_pet_profile`、`list_pets` 输出包含新字段，覆盖具体值和 null；准备具体物种、未填、修改后重查和宠物切换的模型抽查用例。运行相关后端测试及所改文件 Ruff；真实模型结果另留证据 |
| B：后端 | 维护 Pet 数据模型、`PetCreate/PetRead/PetUpdate`、Service/Repository 与 Alembic 迁移：新增可空列；实现类型/空白/码点长度校验、PATCH 合并原对象后的联合校验、错误消息区分及失败不落库；保证 HTTP 和 `BoundPetService` 返回完整 `PetRead`。同步 `docs/API.md` 的字段、请求/响应示例及 PATCH 语义，负责本侧问题修复 | 一次覆盖本契约 PATCH 七例、创建/读取/列表/更新、空值与非法输入、50/51 码点、旧 dog/cat/other 数据迁移、失败不部分写入及重启读取；运行后端 pytest 和所改文件 Ruff，提供可供 A/C 使用的真实接口与迁移证据 |
| C：前端 | 维护 `frontend/` 的宠物类型、API Client/响应校验、表单、列表/详情、演示存储及前端测试：其他物种输入与显示、切回猫狗显式清空、旧演示数据缺字段补 null、保存/编辑/刷新、加载与失败保留输入；按码点计数，不自动回退演示。同步受影响的前端使用说明，负责本侧问题修复 | 一次覆盖显隐与互切、请求载荷、空值、非 BMP 50/51 码点、旧演示存储、保存编辑刷新及错误路径；运行前端测试、构建和本次文件 Prettier。先用契约一致的模拟 HTTP 完成本侧测试，真实接口结果另留证据 |

A 已在 [评审评论](https://github.com/Nexus-226/2026-11-2/pull/63#issuecomment-6625913827)报告 Agent 适配位于 `feat/a-p2-1-species-agent`（`4e7ee08`）；由 A 继续整理和提交，不由 C 重做、覆盖或代提交。该分支报告不等于已合并或已通过整体验收。

### 开发可并行，合并须满足依赖

契约先确认；在既有 P1 启动条件满足后，三人可在原职责内开发自测。B 可先交付只读前置项解除 A 的 Schema 依赖，再完成本侧剩余后端工作；拆分交付不改变责任归属。

- **B 的只读前置项**：[PR #68](https://github.com/Nexus-226/2026-11-2/pull/68) 仅给 `PetRead` 增加字段，过渡期响应恒为 null，创建/更新仍拒绝该字段。该 PR 不代表具体物种可写入、持久化或 P2-1 后端已完成。
- **A 的适配**：只读前置项合并后，A 同步 main，确认两个工具的序列化测试实际执行且通过，再提交适配供审核合并。缺字段导致的 skip 不算通过；前置项就绪后应确认 skip 不再触发。null 输出验证不能替代具体物种值的验证；具体值可先用带新字段的 PetRead 测试替身验证，数据库到工具的真实值仍等 B 完整后端后验收。
- **B 的完整后端**：由 B 继续完成数据模型、Alembic 迁移、`PetCreate/PetUpdate`、Service 完整对象校验、真实读写和后端测试；清理 API.md 过渡说明，并将过渡期“写入拒绝”测试按最终契约替换或调整。上述工作不交给 C；A 适配与 B 剩余后端可各自在本侧推进。
- **C 的前端**：可先用契约一致的模拟响应完成类型、Client、表单、显示、演示兼容和测试；启用并合入新字段的真实写入功能前，必须已有 B 的完整后端。C 不承担 Schema、Service、迁移或后端测试。
- **最终集成**：只读前置项 → A 适配与 B 完整后端各自就绪 → C 接通真实读写并完成三方联调。A/B 的具体合并先后由实际依赖确定，不因 A 已适配就把 B 的剩余工作转给 C；#68 单独合并不足以启用前端新字段写入。

[B 的后续评论](https://github.com/Nexus-226/2026-11-2/pull/63#issuecomment-6626286997)及 #68 描述中“C 补 PetCreate/PetUpdate、Service、迁移”的分配与用户最新要求冲突，本契约统一为 B 承接；#68 的协作描述需由提交人同步。A 的[复审通过评论](https://github.com/Nexus-226/2026-11-2/pull/63#issuecomment-6626217348)是评论确认，不在此冒充 GitHub 正式 review 状态。

这是实现依赖，不额外预排多轮审核日程；具体审核和联调安排仍在各侧就绪后确认。契约 PR 可先合并，功能状态由实际实现与验证决定。

### 协作边界与后续确认

- B 负责共享 `PetRead` 字段和接口实现；A 使用 B 的 Schema 补齐工具序列化验证，C 使用契约一致的响应完成前端。若最终序列化测试需要新 Schema，等待 B 的候选实现就绪后由 A 补齐，不让 C 代改后端。
- 各侧完成本工作包时提供分支/提交、改动范围、自测结果及剩余依赖；已有实现先复用，缺项由原负责人补齐。共享文件先协调，避免重复提交、覆盖和无关改动。
- 本次只明确实现责任，不再预排多轮审核和联调时点。各侧就绪后再确认审核人、集成版本及联调安排；每个 PR 仍须遵守仓库评审规则，作者不以自测代替他人评审。
- 联调范围保留：B/C 确认真实接口、迁移、持久化和页面操作；A/B 确认 Service 到工具的真实字段传递；A/C 确认页面选择、宠物切换及真实模型引用。发现问题由所属侧负责人修复。
- 联调证据需注明版本、环境/数据来源、输入/操作、预期与实际以及工具结果；不提交密钥、数据库或真实对话。尚未执行的真实接口/模型验证明确列为待验，不以模拟测试替代。相关 PR 合并且必要验证完成后，再由任务负责人同步任务表和实现状态。
