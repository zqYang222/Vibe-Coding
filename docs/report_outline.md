# 实验报告素材与大纲（实验二：OJ 系统开发）

> 本文件是报告写作素材，最终报告建议输出为 PDF。评分点见课程 requirements.md：
> 系统功能与设计(2) + 关键实现与难点(2) + 成果展示(1) + AI使用说明(0，必写) + 总结与建议(0)。

## 1. 系统功能与设计

- **架构**：前后端分离。后端 FastAPI（全 `async def` 异步接口），前端 Streamlit（Step 6），两者仅通过 REST API 交互。
- **存储**：本地 JSON 文件系统（`data/` 下 problems/submissions/users/logs 分目录），题目每题一个 JSON。
- **模块划分**：
  - `app/routers/`：problems、submissions、languages、auth、users、logs、system、ai 共 8 个路由模块；
  - `app/services/`：problem_ops、judge（异步评测引擎）、language_ops、submission_ops、user_ops、log_ops、ai_ops、auth；
  - `app/models/`：Pydantic 模型（problem/submission/language/user/ai）。
- **功能清单**：题目增删改查、多语言评测（Python/C++，动态注册）、提交列表/详情/重测、用户注册登录与 user/admin/banned 权限、评测日志与可见性、访问审计、系统重置、AI 智能命题。

## 2. 关键实现与难点

- **异步评测引擎**（Step2）：
  - 提交接口立即返回 `pending`，评测经 `asyncio.create_task` 在后台执行；
  - 子进程用 `asyncio.create_subprocess_exec` 启动，`asyncio.wait_for` 实现超时→TLE；
  - 内存用 psutil 异步轮询监控，超限 kill→MLE；
  - 结果集 AC/WA/TLE/MLE/RE/CE/UNK；输出比对忽略行尾空格与末尾多余换行。
  - 限制优先级：题目 → 语言 → 系统默认(3s/128MB)（助教 Q&A 口径）。
- **权限体系**：SessionMiddleware 会话登录；每个请求从存储加载用户记录（角色/封禁即时生效）；异常处理顺序 401>403>400>429>409>404>500，统一 `{code,msg,data}` 信封与 HTTP 状态码。
- **级联一致性**：删除题目级联删除提交/评测日志/访问审计，并回退用户 submit_count/resolve_count。
- **限频**：按"单人+单题"3 次/分钟（内存滑动窗口）。
- **AI 命题**：模型配置（密钥不回显）；后台流式生成 + 实时进度 + 可中断；Token 用量与费用统计（模型无 usage 时按 ~4字符/token 估算并标注）。
- 难点示例：FastAPI 默认 422 改为 400（异常处理器 + 手动解析 body）；评测进程的资源限制与进程回收；审计记录的时机（不记录 401/404/400）。

## 3. 成果展示

- 接口演示脚本：`scripts/seed_demo.py`（管理员登录后灌入 3 道演示题）。
- 测试：`pytest tests/ -v` 共 10+ 用例（CRUD/AC/WA/TLE/429/重测/权限/审计/级联删除/reset）。
- 演示路径建议：登录 admin → 灌题 → 注册普通用户 → 提交 Python/C++ 代码 → 查看评测状态与日志 → 演示 WA/TLE/CE → 管理员改角色/日志可见性/审计 → AI 命题。

## 4. AI 使用说明（模板，需按实际情况填写）

- 使用工具链：DeepSeek Harness 对话式编程助手（Vibe Coding）。
- 工作流：先由 AI 阅读课程文档与助教 Q&A → 建立项目骨架与目录 → 分模块生成代码 → 人工审阅与测试 → 迭代修复。
- AI 生成代码比例（估算）：约 ____%（请填写）；人工主要负责需求澄清、口径核对、测试与修复。
- 关键决策均对照课程 api.md / requirements.md / 助教 Q&A 手工核对。

## 5. 总结与建议

- 收获：异步编程（asyncio 子进程管理）、REST 设计、权限模型、文件存储的级联一致性、LLM 应用开发。
- 建议：评测沙箱可进一步隔离（容器）；存储可换 SQLite；前端可加实时 WebSocket。
- 时间投入：____ 小时（请填写）。
