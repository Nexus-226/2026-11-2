# Pet Agent

Pet Agent 是一个宠物生活助手。你可以为多只宠物建立档案、记录日常护理、安排待办、向助手提问，并查找附近的宠物服务。

**在线使用** · 项目已部署在 ECS，打开浏览器即可使用。[访问 Pet Agent](https://petagent.icu/)

## 怎么用

1. 打开「我的」，新增一份宠物档案。养了多只宠物时，用页面标题下的切换栏选择当前宠物。
2. 在「记录」里记下疫苗、驱虫、洗澡和体重，展开「查看体重趋势」查看称重变化。
3. 从「我的 → 待办提醒」创建护理待办，按需关联一条记录，处理后标记完成。
4. 在「助手」里提问。可以关联当前宠物，也可以先不选择宠物，直接开始对话。

手机底栏可直接进入「附近服务」。允许定位或手动输入地址后，可按类别查找宠物医院、美容和用品店。「我的 → 寻宠信息卡」可整理并复制一张文字卡，供你自行分享。

助手回复适合日常参考。宠物出现急症时，请及时联系兽医。

## 技术栈

| 部分 | 技术 |
| --- | --- |
| 前端 | React、TypeScript、Vite |
| 后端 | Python、FastAPI、Pydantic |
| 数据库与迁移 | SQLite、SQLAlchemy、Alembic |
| 对话助手 | Python Agent、通义千问（Qwen） |
| 附近服务 | 高德开放平台 Web 服务 |

## 启动

### 在线使用

直接访问已部署的站点。[petagent.icu](https://petagent.icu/)

### 本地运行

需要 Python 3.10+ 和 Node.js 20.19+ 或 22.12+。在仓库根目录启动后端：

```bash
python -m pip install -e "./backend[dev]"
python -m uvicorn app.main:app --app-dir backend --reload
```

另开一个终端，从仓库根目录启动前端：

```bash
cd frontend
npm ci
npm run dev
```

打开 Vite 输出的本地地址。开发时，前端默认把 API 请求转发到 `http://127.0.0.1:8000`。

本地前端的档案、对话、记录和待办默认使用演示模式。要接入本地后端，在 `frontend/.env.local` 中添加以下设置，然后重启前端：

```dotenv
VITE_PET_DATA_SOURCE=api
VITE_CHAT_DATA_SOURCE=api
VITE_RECORD_DATA_SOURCE=api
VITE_REMINDER_DATA_SOURCE=api
```

本地使用 Qwen 或查询真实附近地点时，分别在仓库根目录的 `.env` 中配置 `LLM_API_KEY` 和 `AMAP_WEB_SERVICE_KEY`。其他可选配置见 [.env.example](.env.example)。

开发资料可查阅[技术栈说明](docs/TECH_STACK.md)、[接口文档](docs/API.md)和[项目任务记录](docs/TASKS.md)。
