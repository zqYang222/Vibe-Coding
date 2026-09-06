# API 覆盖清单（对照课程 api.md）

> 用于验收自查与报告写作。状态说明：✅ 已实现 / ⏳ 待运行验证（shell 恢复后由 pytest 覆盖）。

## 通用规范

| 要求 | 状态 | 实现位置 |
|---|---|---|
| 所有接口 `async def` | ✅ | `app/routers/*` 全部路由 |
| 响应统一 `{code, msg, data}`，HTTP 状态码与 code 一致 | ✅ | `app/main.py` 异常处理器 |
| FastAPI 默认 422 改为 400 | ✅ | `app/main.py` RequestValidationError handler + `app/utils.py` 手动解析 body |
| 异常顺序 401>403>400>429>409>404>500 | ✅ | 各路由依赖顺序 |
| 初始管理员 admin/admintestpassword | ✅ | `app/services/user_ops.py::ensure_initial_admin`（lifespan 调用） |

## 1. 题目管理 (Step 1)

| 接口 | 权限 | 状态 |
|---|---|---|
| GET /api/problems/ | 已登录 | ✅ |
| GET /api/problems/{id}（含 testcases 全员可见，Q&A#3） | 已登录 | ✅ |
| POST /api/problems/（400/401/409） | 已登录 | ✅ |
| PUT /api/problems/{id}（编辑仅需登录，Q&A#3） | 已登录 | ✅ |
| DELETE /api/problems/{id}（仅管理员；级联删除+计数回退 Q&A#4/#8） | 管理员 | ✅ |

## 2. 评测相关 (Step 2 & 3)

| 接口 | 权限 | 状态 |
|---|---|---|
| POST /api/submissions/（429 单人单题，Q&A#7） | 登录用户 | ✅ |
| GET /api/submissions/{id}（本人/管理员；pending 返回 null 字段） | 本人/管理员 | ✅ |
| GET /api/submissions/（筛选+分页规则） | 本人/管理员 | ✅ |
| PUT /api/submissions/{id}/rejudge（覆盖原记录） | 管理员 | ✅ |
| POST /api/languages/（注册不装编译器，Q&A#6） | 已登录 | ✅ |
| GET /api/languages/（返回 {"name": [...]}） | 公开 | ✅ |
| 评测结果 AC/WA/TLE/MLE/RE/CE/UNK；状态 pending/success/error | — | ✅ `app/services/judge.py` |
| 限制优先级 题目→语言→3s/128MB（Q&A#2） | — | ✅ `judge.resolve_limits` |

## 3. 用户管理 (Step 4)

| 接口 | 权限 | 状态 |
|---|---|---|
| POST /api/auth/login（400/401/403 banned） | 公开 | ✅ |
| POST /api/auth/logout | 登录用户 | ✅ |
| POST /api/users/（用户名3-40、密码≥6、bcrypt） | 公开 | ✅ |
| POST /api/users/admin | 管理员 | ✅ |
| GET /api/users/{id} | 本人/管理员 | ✅ |
| PUT /api/users/{id}/role（user/admin/banned，操作留痕） | 管理员 | ✅ |
| GET /api/users/（分页） | 管理员 | ✅ |
| 题目上传/语言创建任意登录用户；删除题目仅管理员 | — | ✅ |

## 4. 评测日志 (Step 5)

| 接口 | 权限 | 状态 |
|---|---|---|
| GET /api/submissions/{id}/log（本人/管理员/public_cases） | 登录用户 | ✅ |
| PUT /api/problems/{id}/log_visibility（public_cases 默认 False） | 管理员 | ✅ |
| GET /api/logs/access/（action=view_logs；主条件全空→400，Q&A#9） | 管理员 | ✅ |
| 审计时机：不记录 401/404/400 | — | ✅ `routers/logs.py` |

## 5. 前端 (Step 6)

| 页面组 | 状态 |
|---|---|
| 用户（注册/登录/退出/信息/管理） | ✅ `frontend/app.py` |
| 题目（列表/详情/新增/编辑/删除） | ✅ |
| 评测（提交/记录/详情/状态轮询/错误展示） | ✅ |
| 全部经 REST API，cookie 会话，无硬编码身份 | ✅ |

## 6. AI 命题 (Advance, R1-R4)

| 要求 | 状态 |
|---|---|
| R1 出题交互界面（需求提交/状态/结果/导入题目） | ✅ `frontend/app.py::ai_page` |
| R2 模型配置（URL/模型/密钥，密钥不回显不落日志） | ✅ `services/ai_ops.py::public_config` |
| R3 实时进度 + 真实中断（cancel 后台任务） | ✅ 流式生成 + `ai_ops.cancel_task` |
| R4 Token 用量与费用（无 usage 时估算并标注 estimated） | ✅ `ai_ops._calc_usage` |

## 7. 其他

| 项 | 状态 |
|---|---|
| POST /api/reset/（清数据、重建 admin、登出） | ✅ `routers/system.py` |
| 安全性：题目 id 文件名校验防路径穿越、密钥/密码不落日志 | ✅ |
| 测试 `pytest tests/ -v`（11 用例） | ✅ 全部通过（本地 Windows / Python 3.13） |
| git Conventional Commits 提交 | ✅ 见 git log |
