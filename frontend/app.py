"""Streamlit frontend for the Online Judge system (Step 6 + Advance).

All data flows through the FastAPI backend REST APIs; this frontend never
reads/writes backend data directly. Identity comes from the session cookie
kept in a shared requests.Session -- no hard-coded user identity anywhere.
"""

import json
import time

import requests
import streamlit as st

st.set_page_config(page_title="Online Judge", layout="wide")

API_BASE = "http://127.0.0.1:8000"


# ---------------- API helpers ----------------

def get_session() -> requests.Session:
    if "http" not in st.session_state:
        st.session_state.http = requests.Session()
    return st.session_state.http


def api(method: str, path: str, json_body=None, params=None, silent: bool = False):
    """Call the backend; return (ok, data). Errors surface via st.error."""
    s = get_session()
    try:
        resp = s.request(
            method, f"{API_BASE}{path}", json=json_body, params=params, timeout=60
        )
    except requests.RequestException as e:
        if not silent:
            st.error(f"无法连接后端 ({API_BASE}): {e}")
        return False, None
    try:
        body = resp.json()
    except ValueError:
        if not silent:
            st.error(f"后端返回异常 (HTTP {resp.status_code})")
        return False, None
    if resp.status_code != 200 or body.get("code") != 200:
        if not silent:
            st.error(f"[{body.get('code')}] {body.get('msg')}")
        return False, body
    return True, body.get("data")


def current_user():
    return st.session_state.get("user")


def parse_json_list(text: str, label: str):
    """Parse a JSON array from a text area for samples/testcases."""
    text = (text or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        st.error(f"{label} 不是合法 JSON")
        return None
    if not isinstance(data, list):
        st.error(f"{label} 必须是 JSON 数组")
        return None
    return data


# ---------------- sidebar: login / register / logout ----------------

def sidebar():
    st.sidebar.title("OJ 导航")
    st.sidebar.caption(f"后端地址: {API_BASE}")
    user = current_user()
    if user is None:
        mode = st.sidebar.radio("未登录", ["登录", "注册"])
        if mode == "登录":
            with st.sidebar.form("login_form"):
                username = st.text_input("用户名")
                password = st.text_input("密码", type="password")
                if st.form_submit_button("登录"):
                    ok, data = api(
                        "POST", "/api/auth/login",
                        {"username": username, "password": password},
                    )
                    if ok:
                        st.session_state.user = data
                        st.rerun()
        else:
            with st.sidebar.form("register_form"):
                username = st.text_input("用户名 (3-40字符)")
                password = st.text_input("密码 (至少6位)", type="password")
                if st.form_submit_button("注册"):
                    ok, data = api(
                        "POST", "/api/users/",
                        {"username": username, "password": password},
                    )
                    if ok:
                        st.sidebar.success(f"注册成功: {data['username']}，请登录")
    else:
        st.sidebar.success(f"已登录: {user['username']}（{user['role']}）")
        if st.sidebar.button("刷新我的信息"):
            ok, data = api("GET", f"/api/users/{user['user_id']}")
            if ok:
                st.session_state.user = {**user, "role": data["role"]}
                st.rerun()
        if st.sidebar.button("退出登录"):
            api("POST", "/api/auth/logout", silent=True)
            st.session_state.user = None
            st.rerun()


# ---------------- problems page ----------------

def problems_page():
    st.header("题目")
    ok, problems = api("GET", "/api/problems/")
    if not ok:
        return
    st.write(f"共 {len(problems) if problems else 0} 道题目")
    if problems:
        st.dataframe(problems, hide_index=True)

    if current_user() is None:
        st.warning("请先登录后管理题目")
        return

    action = st.radio("操作", ["查看详情", "新增题目", "编辑题目", "删除题目"], horizontal=True)

    if action == "查看详情":
        if not problems:
            st.info("暂无题目")
            return
        pid = st.selectbox("选择题目", [p["id"] for p in problems])
        show_problem_detail(pid)

    elif action == "新增题目":
        with st.form("add_problem"):
            pid = st.text_input("id (唯一，字母数字-_ )")
            title = st.text_input("title")
            description = st.text_area("description")
            in_desc = st.text_area("input_description")
            out_desc = st.text_area("output_description")
            samples = st.text_area(
                "samples (JSON数组，元素含 input/output)",
                value='[{"input": "1 2", "output": "3"}]',
            )
            constraints = st.text_area("constraints")
            testcases = st.text_area(
                "testcases (JSON数组，元素含 input/output)",
                value='[{"input": "1 2", "output": "3"}]',
            )
            hint = st.text_input("hint (可选)")
            source = st.text_input("source (可选)")
            tags = st.text_input("tags (逗号分隔，可选)")
            t_limit = st.text_input("time_limit 秒 (可选，留空走语言/系统默认)")
            m_limit = st.text_input("memory_limit MB (可选)")
            author = st.text_input("author (可选)")
            difficulty = st.text_input("difficulty (可选)")
            if st.form_submit_button("新增"):
                samples_parsed = parse_json_list(samples, "samples")
                cases_parsed = parse_json_list(testcases, "testcases")
                if samples_parsed is None or cases_parsed is None:
                    st.stop()
                body = {
                    "id": pid, "title": title, "description": description,
                    "input_description": in_desc, "output_description": out_desc,
                    "samples": samples_parsed, "constraints": constraints,
                    "testcases": cases_parsed, "hint": hint, "source": source,
                    "tags": [t.strip() for t in tags.split(",") if t.strip()],
                    "author": author, "difficulty": difficulty,
                }
                if t_limit.strip():
                    body["time_limit"] = float(t_limit)
                if m_limit.strip():
                    body["memory_limit"] = int(m_limit)
                ok, data = api("POST", "/api/problems/", body)
                if ok:
                    st.success(f"新增成功: {data['id']}")

    elif action == "编辑题目":
        if not problems:
            st.info("暂无题目")
            return
        pid = st.selectbox("选择题目", [p["id"] for p in problems], key="edit_sel")
        ok, cur = api("GET", f"/api/problems/{pid}")
        if not ok:
            return
        with st.form("edit_problem"):
            title = st.text_input("title", value=cur["title"])
            description = st.text_area("description", value=cur["description"])
            in_desc = st.text_area("input_description", value=cur["input_description"])
            out_desc = st.text_area("output_description", value=cur["output_description"])
            samples = st.text_area(
                "samples (JSON数组)", value=json.dumps(cur["samples"], ensure_ascii=False)
            )
            constraints = st.text_area("constraints", value=cur["constraints"])
            testcases = st.text_area(
                "testcases (JSON数组)",
                value=json.dumps(cur["testcases"], ensure_ascii=False),
            )
            hint = st.text_input("hint", value=cur["hint"])
            source = st.text_input("source", value=cur["source"])
            tags = st.text_input("tags (逗号分隔)", value=",".join(cur["tags"]))
            t_limit = st.text_input(
                "time_limit 秒", value="" if cur["time_limit"] is None else str(cur["time_limit"])
            )
            m_limit = st.text_input(
                "memory_limit MB",
                value="" if cur["memory_limit"] is None else str(cur["memory_limit"]),
            )
            author = st.text_input("author", value=cur["author"])
            difficulty = st.text_input("difficulty", value=cur["difficulty"])
            if st.form_submit_button("保存修改"):
                samples_parsed = parse_json_list(samples, "samples")
                cases_parsed = parse_json_list(testcases, "testcases")
                if samples_parsed is None or cases_parsed is None:
                    st.stop()
                body = {
                    "id": pid, "title": title, "description": description,
                    "input_description": in_desc, "output_description": out_desc,
                    "samples": samples_parsed, "constraints": constraints,
                    "testcases": cases_parsed, "hint": hint, "source": source,
                    "tags": [t.strip() for t in tags.split(",") if t.strip()],
                    "author": author, "difficulty": difficulty,
                }
                if t_limit.strip():
                    body["time_limit"] = float(t_limit)
                if m_limit.strip():
                    body["memory_limit"] = int(m_limit)
                ok, data = api("PUT", f"/api/problems/{pid}", body)
                if ok:
                    st.success(f"更新成功: {data['id']}")

    elif action == "删除题目":
        if current_user()["role"] != "admin":
            st.warning("仅管理员可删除题目")
            return
        if not problems:
            st.info("暂无题目")
            return
        pid = st.selectbox("选择题目", [p["id"] for p in problems], key="del_sel")
        if st.button(f"删除 {pid}", type="primary"):
            ok, data = api("DELETE", f"/api/problems/{pid}")
            if ok:
                st.success(f"已删除: {data['id']}")
                st.rerun()


def show_problem_detail(pid: str):
    ok, p = api("GET", f"/api/problems/{pid}")
    if not ok:
        return
    st.subheader(f"{p['id']} - {p['title']}")
    st.write(f"难度: {p['difficulty'] or '-'} | 来源: {p['source'] or '-'} | 作者: {p['author'] or '-'}")
    st.write(f"时间限制: {p['time_limit'] if p['time_limit'] is not None else '默认'} s | "
             f"内存限制: {p['memory_limit'] if p['memory_limit'] is not None else '默认'} MB")
    if p["tags"]:
        st.write("标签: " + ", ".join(p["tags"]))
    st.markdown("**题目描述**")
    st.write(p["description"])
    st.markdown("**输入说明**")
    st.write(p["input_description"])
    st.markdown("**输出说明**")
    st.write(p["output_description"])
    st.markdown("**数据范围**")
    st.write(p["constraints"])
    if p["hint"]:
        st.markdown("**提示**")
        st.write(p["hint"])
    st.markdown("**样例**")
    for i, s in enumerate(p["samples"], 1):
        st.text(f"样例{i} 输入:\n{s['input']}\n样例{i} 输出:\n{s['output']}")
    st.markdown("**测试点**")
    st.dataframe(p["testcases"], hide_index=True)


# ---------------- submissions page ----------------

def submission_detail(sid: str):
    ok, d = api("GET", f"/api/submissions/{sid}")
    if not ok:
        return
    st.write(f"状态: **{d['status']}**")
    if d["status"] == "pending":
        if st.checkbox("自动刷新 (每2秒)", key=f"auto_{sid}"):
            time.sleep(2)
            st.rerun()
    elif d["status"] == "success":
        st.write(f"得分: **{d['score']} / {d['counts']}**")
        if d.get("compile_info"):
            st.write(f"编译: {d['compile_info']}")
        if d.get("run_info"):
            st.write(f"运行: {d['run_info']}")
        ok_log, log = api("GET", f"/api/submissions/{sid}/log", silent=True)
        if ok_log and log.get("details"):
            st.dataframe(log["details"], hide_index=True)
    else:
        st.error(f"评测出错: {d.get('error_info') or '未知错误'}")


def submissions_page():
    st.header("提交评测")
    user = current_user()
    if user is None:
        st.warning("请先登录后提交")
        return

    ok_p, problems = api("GET", "/api/problems/", silent=True)
    ok_l, langs = api("GET", "/api/languages/", silent=True)
    problem_ids = [p["id"] for p in problems] if problems else []
    lang_names = langs["name"] if ok_l else ["python"]
    if not problem_ids:
        st.info("暂无题目，请先在「题目」页新增题目后再提交")
        return
    with st.form("submit_code"):
        c1, c2 = st.columns(2)
        with c1:
            problem_id = st.selectbox("题目", problem_ids)
        with c2:
            language = st.selectbox("语言", lang_names)
        code = st.text_area("代码", height=280, placeholder="print('hello')")
        if st.form_submit_button("提交评测"):
            if not code.strip():
                st.error("代码不能为空")
            else:
                ok, data = api(
                    "POST", "/api/submissions/",
                    {"problem_id": problem_id, "language": language, "code": code},
                )
                if ok:
                    st.success(f"提交成功: submission_id={data['submission_id']}")

    st.subheader("我的提交记录")
    ok, data = api("GET", "/api/submissions/", params={"user_id": user["user_id"]})
    if ok and data and data["submissions"]:
        items = data["submissions"]
        table = []
        for it in items:
            row = {
                "submission_id": it["submission_id"],
                "problem_id": it["problem_id"],
                "language": it["language"],
                "status": it["status"],
            }
            if it["status"] == "success":
                row["score"] = f"{it['score']}/{it['counts']}"
            table.append(row)
        st.dataframe(table, hide_index=True)
        sid = st.selectbox("查看提交详情", [i["submission_id"] for i in items])
        submission_detail(sid)
    else:
        st.info("暂无提交记录")


# ---------------- languages page ----------------

def languages_page():
    st.header("语言")
    ok, data = api("GET", "/api/languages/")
    if ok:
        st.write("已注册语言: " + ", ".join(data["name"]))
    if current_user() is None:
        st.warning("请先登录后注册语言")
        return
    st.subheader("注册新语言（仅登记编译/运行方式，不安装编译器）")
    with st.form("reg_lang"):
        name = st.text_input("name (如 go)")
        file_ext = st.text_input("file_ext (如 .go)")
        compile_cmd = st.text_input("compile_cmd (可选，如 g++ {src} -o {exe})")
        run_cmd = st.text_input("run_cmd (必填，如 python3 {src} 或 {exe})")
        t_limit = st.text_input("time_limit 秒 (可选)")
        m_limit = st.text_input("memory_limit MB (可选)")
        if st.form_submit_button("注册"):
            body = {"name": name, "file_ext": file_ext, "run_cmd": run_cmd}
            if compile_cmd.strip():
                body["compile_cmd"] = compile_cmd
            if t_limit.strip():
                body["time_limit"] = float(t_limit)
            if m_limit.strip():
                body["memory_limit"] = int(m_limit)
            ok, data = api("POST", "/api/languages/", body)
            if ok:
                st.success(f"已注册: {data['name']}")


# ---------------- admin pages ----------------

def users_admin_page():
    st.header("用户管理 (管理员)")
    ok, data = api("GET", "/api/users/")
    if not ok:
        return
    st.dataframe(data["users"], hide_index=True)
    st.subheader("修改用户角色")
    c1, c2, c3 = st.columns(3)
    with c1:
        uid = st.selectbox("用户", [u["user_id"] for u in data["users"]])
    with c2:
        role = st.selectbox("新角色", ["user", "admin", "banned"])
    with c3:
        if st.button("修改角色"):
            ok, res = api("PUT", f"/api/users/{uid}/role", {"role": role})
            if ok:
                st.success(f"{res['user_id']} -> {res['role']}")
                st.rerun()
    st.subheader("创建管理员账户")
    with st.form("create_admin"):
        username = st.text_input("用户名 (3-40字符)")
        password = st.text_input("密码 (至少6位)", type="password")
        if st.form_submit_button("创建"):
            ok, res = api(
                "POST", "/api/users/admin", {"username": username, "password": password}
            )
            if ok:
                st.success(f"已创建管理员 {res['username']} (id={res['user_id']})")


def logs_admin_page():
    st.header("日志与审计 (管理员)")
    st.subheader("配置题目日志可见性")
    ok, problems = api("GET", "/api/problems/", silent=True)
    if problems:
        c1, c2 = st.columns([2, 1])
        with c1:
            pid = st.selectbox("题目", [p["id"] for p in problems], key="vis_sel")
        with c2:
            public = st.checkbox("public_cases (公开日志)", key="vis_box")
        if st.button("保存可见性"):
            ok, res = api(
                "PUT", f"/api/problems/{pid}/log_visibility", {"public_cases": public}
            )
            if ok:
                st.success(f"{res['problem_id']} public_cases={res['public_cases']}")

    st.subheader("查看任意评测日志")
    sid = st.text_input("submission_id")
    if sid and st.button("查看日志"):
        ok, log = api("GET", f"/api/submissions/{sid}/log")
        if ok:
            st.dataframe(log["details"], hide_index=True)
            st.write(f"score: {log['score']} / counts: {log['counts']}")

    st.subheader("日志访问审计")
    c1, c2 = st.columns(2)
    with c1:
        f_uid = st.text_input("按用户筛选 (可选)")
    with c2:
        f_pid = st.text_input("按题目筛选 (可选)")
    if st.button("查询审计记录"):
        params = {}
        if f_uid.strip():
            params["user_id"] = f_uid.strip()
        if f_pid.strip():
            params["problem_id"] = f_pid.strip()
        ok, entries = api("GET", "/api/logs/access/", params=params)
        if ok:
            if entries:
                st.dataframe(entries, hide_index=True)
            else:
                st.info("无审计记录")


# ---------------- AI page (Advance) ----------------

def ai_page():
    st.header("AI 智能命题")
    if current_user() is None:
        st.warning("请先登录")
        return

    st.subheader("1. 模型配置")
    ok, cfg = api("GET", "/api/ai/model-config", silent=True)
    if ok:
        st.write(f"当前配置: provider={cfg['provider_url'] or '-'} | model={cfg['model'] or '-'} | "
                 f"api_key={'已配置' if cfg['api_key_configured'] else '未配置'}")
    with st.form("ai_config"):
        provider_url = st.text_input("provider_url", value="https://api.openai.com/v1")
        model = st.text_input("model", value="gpt-4o-mini")
        api_key = st.text_input("api_key", type="password")
        c1, c2, c3 = st.columns(3)
        with c1:
            in_price = st.text_input("输入价格 ($/百万token)", value="0.15")
        with c2:
            out_price = st.text_input("输出价格 ($/百万token)", value="0.6")
        with c3:
            price_unit = st.text_input("计价单位 (token数)", value="1000000")
        if st.form_submit_button("保存配置"):
            body = {
                "provider_url": provider_url, "model": model, "api_key": api_key,
                "input_price": float(in_price), "output_price": float(out_price),
                "price_unit": int(price_unit),
            }
            ok, data = api("PUT", "/api/ai/model-config", body)
            if ok:
                st.success("模型配置已保存")

    st.subheader("2. 发起命题任务")
    with st.form("ai_task"):
        requirement = st.text_area(
            "命题需求 (知识点、难度、数据范围等)",
            placeholder="例如：考察二分查找，难度中等，输入一个有序数组和目标值...",
        )
        problem_id = st.text_input("参考/修改已有题目 id (可选)")
        if st.form_submit_button("开始生成"):
            if not requirement.strip():
                st.error("命题需求不能为空")
            else:
                body = {"requirement": requirement}
                if problem_id.strip():
                    body["problem_id"] = problem_id.strip()
                ok, data = api("POST", "/api/ai/problem-tasks/", body)
                if ok:
                    st.session_state.ai_task_id = data["task_id"]
                    st.rerun()

    task_id = st.session_state.get("ai_task_id")
    if task_id:
        ok, t = api("GET", f"/api/ai/problem-tasks/{task_id}", silent=True)
        if ok:
            st.subheader(f"3. 任务状态 ({t['task_id']})")
            st.write(f"status: **{t['status']}** | progress: {t['progress']}")
            if t.get("usage"):
                u = t["usage"]
                note = "（估算）" if u.get("estimated") else ""
                st.write(f"Token: 输入 {u['input_tokens']} / 输出 {u['output_tokens']} / 总计 {u['total_tokens']} | "
                         f"费用: {u['cost']} {u['currency']}{note}")
            if t["status"] in ("pending", "running"):
                if st.button("中断任务"):
                    ok2, _ = api("PUT", f"/api/ai/problem-tasks/{task_id}/cancel")
                    if ok2:
                        st.warning("任务已中断")
                        st.rerun()
                time.sleep(1.5)
                st.rerun()
            elif t["status"] == "completed" and t.get("result"):
                st.subheader("4. 生成结果")
                st.json(t["result"])
                if st.button("导入为题目 (POST /api/problems/)", type="primary"):
                    ok2, data = api("POST", "/api/problems/", t["result"])
                    if ok2:
                        st.success(f"题目已导入: {data['id']}")
                st.caption("也可以复制 JSON 后在「题目 → 编辑题目」中人工审阅修改")
            elif t["status"] == "cancelled":
                st.warning("任务已中断，可重新发起")
            elif t["status"] == "failed":
                st.error(f"任务失败: {t['progress']}")


# ---------------- main ----------------

sidebar()
user = current_user()
st.title("Online Judge")

if user is None:
    st.info("请从左侧登录（初始管理员：admin / admintestpassword）后使用各功能。")
    tabs = st.tabs(["题目", "语言"])
    with tabs[0]:
        problems_page()
    with tabs[1]:
        languages_page()
else:
    tab_names = ["题目", "提交评测", "语言", "AI 命题"]
    if user["role"] == "admin":
        tab_names += ["用户管理", "日志与审计"]
    tabs = st.tabs(tab_names)
    with tabs[0]:
        problems_page()
    with tabs[1]:
        submissions_page()
    with tabs[2]:
        languages_page()
    with tabs[3]:
        ai_page()
    if user["role"] == "admin":
        with tabs[4]:
            users_admin_page()
        with tabs[5]:
            logs_admin_page()
