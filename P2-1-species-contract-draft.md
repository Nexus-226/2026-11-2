# P2-1 字段契约草案：其他宠物具体物种（待 A/B 评审，未冻结）

> C 侧整理，仅供三人评审；未确认前不据此改 API / Schema / 前端 / Agent。

## 背景与目标

当前 `species` 仅 `dog` / `cat` / `other`，`other` 无法结构化标识「兔、仓鼠、鹦鹉」等具体物种。本项在**保留 dog/cat/other 兼容**的前提下，让 `other` 可填写具体物种；范围严格限制为**档案字段 + Agent 读取**，不扩展专属健康逻辑。

## 字段定义（候选）

- 字段名候选：`other_species`（推荐，语义直白）／ `species_detail`（更通用）。
- 类型：`string | null`。
- 含义：`species == "other"` 时的具体物种文本；`dog` / `cat` 时为 `null`。
- 约束：去除首尾空格后 1–50 字符；`null` 表示未填。

## 校验（服务端，关联校验）

- `species != "other"` 时，`other_species` 必须为 `null`；传非空 → `422 VALIDATION_ERROR`。
- `species == "other"` 时，`other_species` 可空（`null`）或 1–50 字符。
- 去除首尾空格后为空 → 等价存 `null`。
- `PATCH`：省略表示不修改；`null` 清空；空对象 / 未知字段沿用既有 `422`。

## 兼容性

- 不新增 `species` 枚举值，保留 `dog` / `cat` / `other`；现有物种判断逻辑不变。
- 存量 `dog` / `cat` 数据 `other_species` 回填 `null`。
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

- `get_pet_profile` / `list_pets` 返回 `other_species`。
- 提示词：`species == "other"` 且 `other_species` 非空时按具体物种称呼（如「兔」）；`other_species` 为空时如实说「其他宠物（未填具体物种）」；不得默认按猫狗处理，也不得编造具体物种。

## 测试

- B：关联校验（dog + 非空 `other_species` → 422；other 空 / 非空）、迁移回填、CRUD 持久化。
- C：表单显示 / 隐藏 / 清空、保存编辑刷新、演示与 API 双模式。
- A：工具返回字段、模型准确引用且不默认猫狗。

## 待 A/B 确认

1. 字段名用 `other_species` 还是 `species_detail`？
2. 长度上限 50 是否合适？
3. 关联校验是否收紧（dog/cat 传非空直接 422，还是静默忽略该字段）？
4. `other` 且未填具体物种：允许空，还是强制补填？

## 审查补充：建议采用的精确语义（待 A/B 确认）

本节将上述候选收敛为评审建议，不代表已经冻结或实现：字段采用 `other_species`，最长 50 字符；`other` 允许未填写；dog/cat 携带非空值返回 `422 VALIDATION_ERROR`，不静默忽略。

### 标准化与输入类型

- 创建时省略 `other_species` 等同 `null`；PATCH 省略表示不修改，显式 `null` 表示清空。
- 仅接受字符串或 `null`；数字、布尔值、数组和对象均返回 `422 VALIDATION_ERROR`。
- 字符串先去除首尾空白，空串转为 `null`，再检查标准化后长度（最多 50 个 Unicode 码点），最后校验与 species 的关联。空白不占标准化后的长度；前端长度校验应与后端一致。
- `species:null` 仍返回既有 `422`，不因新增可空字段放宽 species。

### PATCH 按完整对象联合校验

Service 读取已有宠物，将仅本次出现的字段合并到现有对象，对完整候选对象执行标准化及关联校验；全部通过后才持久化。失败不得部分修改资料。仅凭 PetUpdate 请求体无法判断省略 species 时的实际物种。

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

### 存量与发布兼容

- 数据库新增可空列；所有存量宠物（包括 other）值均为 null，不从 breed、notes 或聊天文本推断具体物种。保留原记录及已有字段。
- 演示数据沿用现有 localStorage：读取旧记录缺失的新字段时补为 null，后续保存包含该字段，不清空用户已有演示档案。
- 保留 dog/cat/other 枚举不等于旧服务端已支持新字段：现有 Schema 禁止未知字段。实施时先部署后端及迁移，再启用前端新字段；API 模式不将未知字段或字段缺失错误伪装成成功或演示结果。
- 工具继续经 Service 返回共用 PetRead；需验证运行时序列化后的 get_pet_profile 和 list_pets 结果均带新字段，而非只检查类型定义。字段文本仅作为档案数据，不作为模型指令。

### 补充验收

- 后端覆盖上表、空值/全空白、50/51 码点边界、错误输入类型、失败不落库，以及含 dog/cat/other 旧数据的升级迁移、CRUD 和重启读取。
- 前端覆盖旧演示数据读取、猫狗与其他互切、显式清空请求、API 保存编辑刷新、失败保留输入；补充非 BMP 字符的长度一致性。
- Agent 用模拟 Service/Provider 验证真实工具输出；具体物种、未知物种、修改后重新查询和宠物切换均不混用。真实模型引用另行抽查，不把一次通过当作永久保证。

## 分工与实施条件

最新 TASKS.md 的 P2-1 为“其他宠物具体物种支持”，B/C 主、A 适配工具；依赖 P0-5、P0-7、字段契约确认及 P1 收尾验收。本 PR 仅提交契约评审，不将功能标记完成，不宣称 P1 已验收。

C 可以独立完成表单、列表/详情、演示存储、前端类型和 Client；只改前端不能交付完整 P2-1，因为还需要后端 Schema、迁移、Service 联合校验及 Agent 引用验证。由 C 一人承担跨端编码在技术上可行、工作量中等，但需先明确跨端责任，由 B 评审后端与迁移、A 评审工具输出和提示词；建议保留 B/C 主、A 协作的现有分工。

契约确认后，实施 PR 同步 API.md、Schema、数据库迁移、前端类型及测试；分别执行后端 pytest/Ruff 与前端测试、构建、所改文件 Prettier 检查，并完成真实接口联调后再更新实现状态。

