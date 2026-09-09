"""Streamlit frontend for the Online Judge system (Step 6 + Advance).

In-page navigation only (buttons + st.rerun, never full-page links), so the
login session survives every navigation. The backend session cookie is also
persisted to a local file so a browser refresh keeps you logged in.
"""

import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import streamlit as st

st.set_page_config(page_title="Online Judge", layout="wide")

API_BASE = "http://127.0.0.1:8000"

_AUTH_FILE = Path(__file__).resolve().parent / ".streamlit" / "auth.json"

VERDICT_LABEL = {
    "AC": "Accepted",
    "WA": "Wrong Answer",
    "TLE": "Time Limit Exceeded",
    "MLE": "Memory Limit Exceeded",
    "RE": "Runtime Error",
    "CE": "Compilation Error",
    "UNK": "Unknown",
}


# ---------------- auth persistence ----------------

def _save_auth(cookie, user):
    try:
        _AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
        _AUTH_FILE.write_text(
            json.dumps({"cookie": cookie, "user": user}), encoding="utf-8"
        )
    except Exception:
        pass


def _load_auth():
    try:
        if _AUTH_FILE.exists():
            return json.loads(_AUTH_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def _clear_auth():
    try:
        _AUTH_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def restore_login():
    if "user" in st.session_state:
        return
    saved = _load_auth()
    if not saved:
        return
    cookie = saved.get("cookie")
    if cookie:
        get_session().cookies.set("session", cookie, path="/")
    st.session_state.user = saved.get("user")
    uid = (saved.get("user") or {}).get("user_id")
    if uid:
        ok, _ = api("GET", f"/api/users/{uid}", silent=True)
        if not ok:
            st.session_state.user = None
            _clear_auth()


# ---------------- session & api helpers ----------------

def get_session() -> requests.Session:
    if "http" not in st.session_state:
        st.session_state.http = requests.Session()
    return st.session_state.http


def api(method, path, json_body=None, params=None, silent=False):
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


def _clear_widgets():
    """Drop all page widget state so switching pages never leaks widgets."""
    for k in list(st.session_state.keys()):
        if k in ("user", "http", "ai_task_id") or k.startswith("last_submit_"):
            continue
        del st.session_state[k]


def _nav(page, pid=None, sid=None):
    _clear_widgets()
    st.session_state.page = page
    st.session_state.pid = pid
    st.session_state.sid = sid


def go(page, pid=None, sid=None):
    _nav(page, pid, sid)
    st.rerun()


def beijing_now():
    return datetime.now(timezone(timedelta(hours=8))).strftime("%m-%d %H:%M:%S")


def parse_json_list(text, label):
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


# ---------------- verdict rendering ----------------

def _color(score, counts):
    if counts is None or counts == 0 or score is None:
        return "#e2e3e5", "#383d41"
    ratio = score / counts
    if ratio >= 1:
        return "#d4edda", "#155724"
    if ratio > 0:
        return "#fff3cd", "#856404"
    return "#f8d7da", "#721c24"


def _verdict_bg(result):
    return {
        "AC": "#d4edda",
        "WA": "#f8d7da",
        "TLE": "#f8d7da",
        "MLE": "#f8d7da",
        "RE": "#f8d7da",
        "CE": "#f8d7da",
        "UNK": "#e2e3e5",
    }.get(result, "#e2e3e5")


def badge(text, bg, fg):
    return (
        f'<span style="display:inline-block;background:{bg};color:{fg};'
        f'padding:2px 8px;border-radius:6px;font-weight:600;font-size:0.9rem">'
        f"{text}</span>"
    )


def overall_from_details(details):
    if not details:
        return "Unknown"
    res = [d.get("result") for d in details]
    if all(r == "AC" for r in res):
        return "Accepted"
    for v in ("CE", "TLE", "MLE", "RE"):
        if v in res:
            return VERDICT_LABEL[v]
    return "Wrong Answer"


# ---------------- dialogs ----------------

@st.dialog("登录")
def login_dialog():
    username = st.text_input("用户名", key="login_username")
    password = st.text_input("密码", type="password", key="login_password")
    if st.button("登录", key="login_submit_btn"):
        ok, data = api(
            "POST", "/api/auth/login", {"username": username, "password": password}
        )
        if ok:
            st.session_state.user = data
            _save_auth(get_session().cookies.get("session"), data)
            st.rerun()
    with st.expander("忘记密码？"):
        fp_username = st.text_input("用户名", key="fp_username")
        fp1 = st.text_input("新密码", type="password", key="fp1")
        fp2 = st.text_input("确认新密码", type="password", key="fp2")
        if st.button("重置密码", key="fp_submit_btn"):
            if not fp_username:
                st.error("请输入用户名")
            elif len(fp1) < 6:
                st.error("新密码至少 6 位")
            elif fp1 != fp2:
                st.error("两次输入的新密码不一致")
            else:
                ok2, _ = api(
                    "POST", "/api/auth/reset-password",
                    {"username": fp_username, "new_password": fp1},
                )
                if ok2:
                    st.success("密码已重置，请用新密码登录")


@st.dialog("注册")
def register_dialog():
    username = st.text_input("用户名 (3-40字符)", key="reg_username")
    password = st.text_input("密码 (至少6位)", type="password", key="reg_password")
    if st.button("注册", key="reg_submit_btn"):
        ok, data = api(
            "POST", "/api/users/", {"username": username, "password": password}
        )
        if ok:
            st.success(f"注册成功: {data['username']}，请登录")


# ---------------- top bar ----------------

def topbar():
    st.markdown(
        """
        <style>
        .block-container { padding-top: 0.8rem; padding-bottom: 2rem; }
        .stButton button { font-size: 1.08rem; }
        hr { margin: 0.3rem 0 !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    user = current_user()
    c1, c2, c3 = st.columns([1.4, 4.4, 2.6], gap="small")
    with c1:
        st.markdown(
            '<span style="font-size:1.6rem;font-weight:700;color:#0f1115">'
            "Online Judge</span>",
            unsafe_allow_html=True,
        )
    with c2:
        items = ["题库", "AI命题", "语言"]
        if user and user["role"] == "admin":
            items += ["用户管理", "日志审计"]
        mapping = {
            "题库": "problems",
            "AI命题": "ai",
            "语言": "languages",
            "用户管理": "users",
            "日志审计": "logs",
        }
        nav = st.columns(len(items), gap="small")
        for i, it in enumerate(items):
            page = mapping[it]
            active = st.session_state.get("page") == page
            nav[i].button(
                it,
                key=f"nav_{it}",
                type="primary" if active else "secondary",
                on_click=_nav,
                args=(page, None, None),
            )
    with c3:
        t1, t2 = st.columns([1.5, 1.4], gap="small")
        with t1:
            st.markdown(
                f'<span style="font-size:1.08rem;color:#57606a">🕐 {beijing_now()}</span>',
                unsafe_allow_html=True,
            )
        with t2:
            if user:
                with st.popover(f"👤 {user['username']} ({user['role']})"):
                    st.write(f"用户ID: {user['user_id']}")
                    st.button("✏️ 编辑信息", key="pop_edit", on_click=_nav, args=("profile", None, None))
                    if st.button("🚪 退出登录", key="pop_logout"):
                        api("POST", "/api/auth/logout", silent=True)
                        st.session_state.user = None
                        _clear_auth()
                        go("problems")
            else:
                l1, l2 = st.columns(2, gap="small")
                if l1.button("登录", key="topbar_login"):
                    login_dialog()
                if l2.button("注册", key="topbar_reg"):
                    register_dialog()
    st.markdown("---")


# ---------------- problem form ----------------

def problem_form(defaults=None):
    d = defaults or {}
    prefix = "edit" if defaults else "add"
    with st.form(f"problem_form_{prefix}"):
        pid = st.text_input(
            "id *", value=d.get("id", ""), disabled=bool(d.get("id")), key=f"{prefix}_pid"
        )
        title = st.text_input("title *", value=d.get("title", ""), key=f"{prefix}_title")
        description = st.text_area(
            "description *", value=d.get("description", ""), key=f"{prefix}_desc"
        )
        in_desc = st.text_area(
            "input_description *", value=d.get("input_description", ""), key=f"{prefix}_in"
        )
        out_desc = st.text_area(
            "output_description *", value=d.get("output_description", ""), key=f"{prefix}_out"
        )
        samples = st.text_area(
            "samples (JSON数组) *",
            value=json.dumps(d.get("samples", []), ensure_ascii=False),
            key=f"{prefix}_samples",
        )
        constraints = st.text_area(
            "constraints *", value=d.get("constraints", ""), key=f"{prefix}_cons"
        )
        testcases = st.text_area(
            "testcases (JSON数组) *",
            value=json.dumps(d.get("testcases", []), ensure_ascii=False),
            key=f"{prefix}_cases",
        )
        hint = st.text_input("hint (可选)", value=d.get("hint", ""), key=f"{prefix}_hint")
        source = st.text_input("source (可选)", value=d.get("source", ""), key=f"{prefix}_src")
        tags = st.text_input(
            "tags (逗号分隔，可选)", value=",".join(d.get("tags", [])), key=f"{prefix}_tags"
        )
        t_limit = st.text_input(
            "time_limit 秒 (可选)",
            value="" if d.get("time_limit") is None else str(d["time_limit"]),
            key=f"{prefix}_tl",
        )
        m_limit = st.text_input(
            "memory_limit MB (可选)",
            value="" if d.get("memory_limit") is None else str(d["memory_limit"]),
            key=f"{prefix}_ml",
        )
        author = st.text_input("author (可选)", value=d.get("author", ""), key=f"{prefix}_author")
        difficulty = st.text_input(
            "difficulty (可选)", value=d.get("difficulty", ""), key=f"{prefix}_diff"
        )
        submitted = st.form_submit_button("保存")
    if not submitted:
        return None
    samples_parsed = parse_json_list(samples, "samples")
    cases_parsed = parse_json_list(testcases, "testcases")
    if samples_parsed is None or cases_parsed is None:
        return None
    body = {
        "id": pid,
        "title": title,
        "description": description,
        "input_description": in_desc,
        "output_description": out_desc,
        "samples": samples_parsed,
        "constraints": constraints,
        "testcases": cases_parsed,
        "hint": hint,
        "source": source,
        "tags": [t.strip() for t in tags.split(",") if t.strip()],
        "author": author,
        "difficulty": difficulty,
    }
    if t_limit.strip():
        body["time_limit"] = float(t_limit)
    if m_limit.strip():
        body["memory_limit"] = int(m_limit)
    return body


# ---------------- pages ----------------

def problems_page():
    st.title("题库")
    user = current_user()
    if user is not None:
        with st.expander("➕ 新增题目"):
            body = problem_form()
            if body:
                ok, data = api("POST", "/api/problems/", body)
                if ok:
                    st.success(f"新增成功: {data['id']}")
                    st.rerun()
    ok, problems = api("GET", "/api/problems/", silent=True)
    if not ok or not problems:
        st.info("暂无题目，点击上方「新增题目」添加")
        return
    q = st.text_input("🔍 搜索题目（按题号或标题关键字）", key="search_q")
    if q.strip():
        ql = q.strip().lower()
        problems = [
            p for p in problems
            if ql in p["id"].lower() or ql in p["title"].lower()
        ]
    st.caption(f"共 {len(problems)} 道题目")
    if not problems:
        st.info("没有匹配的题目")
        return
    for p in problems:
        st.button(
            f"{p['id']} · {p['title']}",
            key=f"pt_{p['id']}",
            on_click=_nav,
            args=("problem_detail", p["id"], None),
        )
        okd, d = api("GET", f"/api/problems/{p['id']}", silent=True)
        meta = []
        if okd:
            if d.get("difficulty"):
                meta.append(f"难度 {d['difficulty']}")
            if d.get("tags"):
                meta.append("标签 " + ", ".join(d["tags"]))
            if d.get("source"):
                meta.append(f"来源 {d['source']}")
        if meta:
            st.caption(" | ".join(meta))


def problem_detail_page(pid):
    ok, p = api("GET", f"/api/problems/{pid}")
    if not ok or not p:
        st.error("题目不存在或加载失败")
        return
    user = current_user()
    st.button("← 返回题库", key="back_problems", on_click=_nav, args=("problems", None, None))
    col_title, col_rec = st.columns([4, 1], vertical_alignment="center")
    with col_title:
        st.header(f"{p['id']} · {p['title']}")
    with col_rec:
        if user:
            st.button(
                "📄 提交记录",
                key="detail_records_btn",
                on_click=_nav,
                args=("problem_records", pid, None),
            )

    meta = []
    if p.get("difficulty"):
        meta.append(f"难度 {p['difficulty']}")
    if p.get("tags"):
        meta.append("标签 " + ", ".join(p["tags"]))
    if p.get("source"):
        meta.append(f"来源 {p['source']}")
    tl = p["time_limit"] if p["time_limit"] is not None else "默认"
    ml = p["memory_limit"] if p["memory_limit"] is not None else "默认"
    meta.append(f"时间限制 {tl}s / 内存 {ml}MB")
    st.caption(" | ".join(meta))

    if user is not None:
        with st.expander("✏️ 编辑题目"):
            body = problem_form(p)
            if body:
                ok2, _ = api("PUT", f"/api/problems/{pid}", body)
                if ok2:
                    st.success("已更新")
                    st.rerun()
        if user["role"] == "admin":
            with st.expander("🗑️ 删除题目"):
                if st.button(f"确认删除 {pid}？", type="primary"):
                    ok2, _ = api("DELETE", f"/api/problems/{pid}")
                    if ok2:
                        st.success("已删除")
                        go("problems")

    st.markdown("### 题目描述")
    st.write(p["description"])
    st.markdown("### 输入格式")
    st.write(p["input_description"])
    st.markdown("### 输出格式")
    st.write(p["output_description"])
    if p.get("constraints"):
        st.markdown("### 数据范围与约定")
        st.write(p["constraints"])
    if p.get("hint"):
        st.markdown("### 提示")
        st.write(p["hint"])
    st.markdown("### 样例")
    for i, s in enumerate(p["samples"], 1):
        c1, c2 = st.columns(2)
        c1.markdown(f"**输入 {i}**")
        c1.code(s["input"])
        c2.markdown(f"**输出 {i}**")
        c2.code(s["output"])

    if user is None:
        st.info("请先登录后再提交代码")
        return
    st.markdown("### 提交代码")
    lang_labels = {"python": "Python 3", "cpp": "C++ (GCC)"}
    lang = st.selectbox(
        "语言和编译选项",
        list(lang_labels.keys()),
        format_func=lambda k: lang_labels[k],
        key=f"lang_{pid}",
    )
    code = st.text_area("代码", height=200, key=f"code_{pid}", placeholder="print('hello')")
    if st.button("提交评测", type="primary", key=f"submit_btn_{pid}"):
        if not code.strip():
            st.error("代码不能为空")
        else:
            ok3, data = api(
                "POST", "/api/submissions/",
                {"problem_id": pid, "language": lang, "code": code},
            )
            if ok3:
                st.session_state[f"last_submit_{pid}"] = data["submission_id"]
                st.rerun()
    sid = st.session_state.get(f"last_submit_{pid}")
    if sid:
        st.markdown("#### 评测结果")
        render_submission(sid)


def _poll_submission(sid, tries=100):
    for _ in range(tries):
        ok, d = api("GET", f"/api/submissions/{sid}", silent=True)
        if ok and d and d["status"] != "pending":
            return d
        time.sleep(0.3)
    ok, d = api("GET", f"/api/submissions/{sid}", silent=True)
    return d if ok else None


def build_details_table(details):
    html = [
        '<table style="width:100%;border-collapse:collapse;font-size:0.95rem">',
        '<tr style="background:#f6f8fa;text-align:left">'
        '<th style="padding:6px">#</th><th style="padding:6px">结果</th>'
        '<th style="padding:6px">时间</th><th style="padding:6px">内存</th></tr>',
    ]
    for d in details:
        label = VERDICT_LABEL.get(d["result"], d["result"])
        b = badge(label, _verdict_bg(d["result"]), "#1b1b1b")
        html.append(
            f'<tr style="border-bottom:1px solid #f0f2f5;text-align:left">'
            f'<td style="padding:6px">{d["id"]}</td><td style="padding:6px">{b}</td>'
            f'<td style="padding:6px">{d.get("time", 0)}s</td>'
            f'<td style="padding:6px">{d.get("memory", 0)}MB</td></tr>'
        )
    html.append("</table>")
    return "".join(html)


def render_submission(sid):
    rec = _poll_submission(sid)
    if rec is None:
        st.error("无法获取评测结果")
        return
    if rec["status"] == "pending":
        st.info("评测中…")
        if st.button("刷新"):
            st.rerun()
        return
    if rec["status"] == "error":
        st.error(f"评测出错: {rec.get('error_info') or '未知错误'}")
        return
    score, counts = rec.get("score"), rec.get("counts")
    ok, log = api("GET", f"/api/submissions/{sid}/log", silent=True)
    details = (log or {}).get("details", []) if ok else []
    verdict = overall_from_details(details)
    bg, fg = _color(score, counts)
    st.markdown(badge(verdict, bg, fg), unsafe_allow_html=True)
    st.write(f"得分: **{score} / {counts}**")
    if rec.get("compile_info") and rec["compile_info"].get("result") == "failed":
        st.error(f"编译错误: {rec['compile_info'].get('message')}")
    if details:
        st.markdown("**测试点明细**")
        st.markdown(build_details_table(details), unsafe_allow_html=True)


def problem_records_page(pid):
    st.subheader(f"我的提交记录 · {pid}")
    st.button("← 返回题目", key="recs_back", on_click=_nav, args=("problem_detail", pid, None))
    user = current_user()
    if user is None:
        st.info("请先登录")
        return
    ok, data = api(
        "GET", "/api/submissions/",
        params={"user_id": user["user_id"], "problem_id": pid},
        silent=True,
    )
    if not ok or not data or not data.get("submissions"):
        st.info("暂无该题目的提交记录")
        return
    rows = []
    for it in data["submissions"]:
        sid = it["submission_id"]
        verdict, score, counts = _submission_verdict(
            sid, it["status"], it.get("score"), it.get("counts")
        )
        rows.append(
            {
                "sid": sid,
                "uid": it["user_id"],
                "pid": it["problem_id"],
                "lang": it["language"],
                "verdict": verdict,
                "score": score,
                "counts": counts,
                "time": it.get("created_time", ""),
            }
        )
    header = st.columns([1.1, 1, 1.4, 1, 1.8, 1, 1.6])
    for h, col in zip(
        ["提交编号", "用户", "题目", "语言", "状态", "分数", "时间"], header
    ):
        col.markdown(f"**{h}**")
    for r in rows:
        c = st.columns([1.1, 1, 1.4, 1, 1.8, 1, 1.6])
        c[0].button(f"#{r['sid']}", key=f"sid_{r['sid']}", on_click=_nav, args=("submission", None, r["sid"]))
        c[1].write(r["uid"])
        c[2].button(r["pid"], key=f"pid_{r['sid']}", on_click=_nav, args=("problem_detail", r["pid"], None))
        c[3].write(r["lang"])
        bg, fg = _color(r["score"], r["counts"])
        c[4].markdown(badge(r["verdict"], bg, fg), unsafe_allow_html=True)
        c[5].write(f'{r["score"]}/{r["counts"]}' if r["counts"] is not None else "-")
        c[6].write(r["time"])


def _submission_verdict(sid, status, score, counts):
    if status == "pending":
        return "Pending", score, counts
    if status == "error":
        return "Error", score, counts
    ok, log = api("GET", f"/api/submissions/{sid}/log", silent=True)
    details = (log or {}).get("details", []) if ok else []
    return overall_from_details(details), score, counts


def submission_page(sid):
    ok, rec = api("GET", f"/api/submissions/{sid}", silent=True)
    if not ok or not rec:
        st.error("提交不存在或无权限")
        return
    st.button(
        "← 返回题目",
        key="sub_back",
        on_click=_nav,
        args=("problem_detail", rec["problem_id"], None),
    )
    st.subheader(f"提交 #{sid}")
    st.write(
        f"题目 {rec['problem_id']} | 用户 {rec['user_id']} | "
        f"语言 {rec['language']} | 提交时间 {rec.get('created_time', '')}"
    )
    render_submission(sid)


def profile_page():
    st.title("编辑个人信息")
    user = current_user()
    if user is None:
        st.info("请先登录")
        return
    ok, me = api("GET", f"/api/users/{user['user_id']}", silent=True)
    if not ok:
        return
    st.write(
        f"用户ID: {me['user_id']} | 当前用户名: {me['username']} | "
        f"角色: {me['role']} | 加入时间: {me['join_time']}"
    )
    with st.form("profile_form"):
        new_username = st.text_input("新用户名（留空则不修改）", key="pf_username")
        old_pw = st.text_input("旧密码（改密码时填写）", type="password", key="pf_oldpw")
        new_pw = st.text_input("新密码（至少6位，留空则不修改）", type="password", key="pf_newpw")
        if st.form_submit_button("保存"):
            body = {}
            if new_username.strip():
                body["username"] = new_username.strip()
            if old_pw or new_pw:
                body["old_password"] = old_pw
                body["new_password"] = new_pw
            if not body:
                st.info("没有需要修改的内容")
            else:
                ok2, res = api("PUT", f"/api/users/{user['user_id']}", body)
                if ok2:
                    st.session_state.user = {
                        **user,
                        "username": res.get("username", user["username"]),
                    }
                    _save_auth(get_session().cookies.get("session"), st.session_state.user)
                    st.success("已保存")
                    st.rerun()


def languages_page():
    st.title("语言")
    ok, data = api("GET", "/api/languages/", silent=True)
    if ok:
        st.write("已注册语言: " + ", ".join(data["name"]))
    if current_user() is None:
        st.info("请先登录后注册语言")
        return
    st.subheader("注册新语言（仅登记编译/运行方式，不安装编译器）")
    with st.form("reg_lang"):
        name = st.text_input("name (如 go)", key="lang_name")
        file_ext = st.text_input("file_ext (如 .go)", key="lang_ext")
        compile_cmd = st.text_input("compile_cmd (可选，如 g++ {src} -o {exe})", key="lang_ccmd")
        run_cmd = st.text_input("run_cmd (必填，如 python3 {src} 或 {exe})", key="lang_rcmd")
        t_limit = st.text_input("time_limit 秒 (可选)", key="lang_tl")
        m_limit = st.text_input("memory_limit MB (可选)", key="lang_ml")
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


def users_admin_page():
    st.title("用户管理")
    ok, data = api("GET", "/api/users/", silent=True)
    if not ok:
        return
    st.dataframe(data["users"], hide_index=True)
    st.subheader("修改用户角色")
    c1, c2, c3 = st.columns(3)
    with c1:
        uid = st.selectbox("用户", [u["user_id"] for u in data["users"]], key="role_uid")
    with c2:
        role = st.selectbox("新角色", ["user", "admin", "banned"], key="role_sel")
    with c3:
        if st.button("修改角色", key="role_btn"):
            ok, res = api("PUT", f"/api/users/{uid}/role", {"role": role})
            if ok:
                st.success(f"{res['user_id']} -> {res['role']}")
                st.rerun()
    st.subheader("创建管理员账户")
    with st.form("create_admin"):
        username = st.text_input("用户名 (3-40字符)", key="ca_username")
        password = st.text_input("密码 (至少6位)", type="password", key="ca_password")
        if st.form_submit_button("创建"):
            ok, res = api(
                "POST", "/api/users/admin", {"username": username, "password": password}
            )
            if ok:
                st.success(f"已创建管理员 {res['username']} (id={res['user_id']})")


def logs_admin_page():
    st.title("日志与审计")
    st.subheader("配置题目日志可见性")
    ok, problems = api("GET", "/api/problems/", silent=True)
    if problems:
        c1, c2 = st.columns([2, 1])
        with c1:
            pid = st.selectbox("题目", [p["id"] for p in problems], key="vis_sel")
        with c2:
            public = st.checkbox("public_cases (公开日志)", key="vis_box")
        if st.button("保存可见性", key="vis_btn"):
            ok, res = api(
                "PUT", f"/api/problems/{pid}/log_visibility", {"public_cases": public}
            )
            if ok:
                st.success(f"{res['problem_id']} public_cases={res['public_cases']}")
    st.subheader("查看任意评测日志")
    sid = st.text_input("submission_id", key="log_sid")
    if sid and st.button("查看日志", key="log_btn"):
        ok, log = api("GET", f"/api/submissions/{sid}/log")
        if ok:
            st.dataframe(log["details"], hide_index=True)
            st.write(f"score: {log['score']} / counts: {log['counts']}")
    st.subheader("日志访问审计")
    c1, c2 = st.columns(2)
    with c1:
        f_uid = st.text_input("按用户筛选 (可选)", key="audit_uid")
    with c2:
        f_pid = st.text_input("按题目筛选 (可选)", key="audit_pid")
    if st.button("查询审计记录", key="audit_btn"):
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


def _import_generated_problem(result):
    """Import an AI-generated problem, auto-fixing id conflicts/invalid chars."""
    result = dict(result)
    original = str(result.get("id") or "").strip()
    raw = re.sub(r"[^A-Za-z0-9_\-]", "_", original)[:64]
    if not raw:
        raw = "problem"
    okp, existing = api("GET", "/api/problems/", silent=True)
    existing_ids = {p["id"] for p in existing} if existing else set()
    candidate = raw
    n = 1
    while candidate in existing_ids:
        candidate = f"{raw}_{n}"
        n += 1
    result["id"] = candidate
    ok2, data = api("POST", "/api/problems/", result)
    if ok2:
        if candidate != original:
            st.success(f"题目已导入（id 已自动调整为「{candidate}」）")
        else:
            st.success(f"题目已导入: {candidate}")


def ai_page():
    st.title("AI 智能命题")
    if current_user() is None:
        st.info("请先登录")
        return
    st.subheader("1. 模型配置")
    ok, cfg = api("GET", "/api/ai/model-config", silent=True)
    if ok:
        st.write(
            f"当前配置: provider={cfg['provider_url'] or '-'} | model={cfg['model'] or '-'} | "
            f"api_key={'已配置' if cfg['api_key_configured'] else '未配置'}"
        )
    with st.form("ai_config"):
        provider_url = st.text_input("provider_url", value="https://api.deepseek.com/v1", key="ai_provider")
        model = st.text_input("model", value="deepseek-v4-pro", key="ai_model")
        api_key = st.text_input("api_key", type="password", key="ai_key")
        c1, c2, c3 = st.columns(3)
        with c1:
            in_price = st.text_input("输入价格 ($/百万token)", value="0.27", key="ai_in")
        with c2:
            out_price = st.text_input("输出价格 ($/百万token)", value="1.1", key="ai_out")
        with c3:
            price_unit = st.text_input("计价单位 (token数)", value="1000000", key="ai_unit")
        if st.form_submit_button("保存配置"):
            body = {
                "provider_url": provider_url,
                "model": model,
                "api_key": api_key,
                "input_price": float(in_price),
                "output_price": float(out_price),
                "price_unit": int(price_unit),
            }
            ok, _ = api("PUT", "/api/ai/model-config", body)
            if ok:
                st.success("模型配置已保存")

    st.subheader("2. 发起命题任务")
    with st.form("ai_task"):
        requirement = st.text_area(
            "命题需求 (知识点、难度、数据范围等)",
            placeholder="例如：考察二分查找，难度中等，输入一个有序数组和目标值...",
            key="ai_req",
        )
        problem_id = st.text_input("参考/修改已有题目 id (可选)", key="ai_pid")
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
                st.write(
                    f"Token: 输入 {u['input_tokens']} / 输出 {u['output_tokens']} / "
                    f"总计 {u['total_tokens']} | 费用: {u['cost']} {u['currency']}{note}"
                )
            if t["status"] in ("pending", "running"):
                if st.button("中断任务"):
                    api("PUT", f"/api/ai/problem-tasks/{task_id}/cancel")
                    st.warning("任务已中断")
                    st.rerun()
                time.sleep(1.5)
                st.rerun()
            elif t["status"] == "completed" and t.get("result"):
                st.subheader("4. 生成结果")
                st.json(t["result"])
                if st.button("导入为题目", type="primary"):
                    _import_generated_problem(t["result"])
            elif t["status"] == "cancelled":
                st.warning("任务已中断，可重新发起")
            elif t["status"] == "failed":
                st.error(f"任务失败: {t['progress']}")


# ---------------- router ----------------

restore_login()
topbar()

st.session_state.setdefault("page", "problems")
page = st.session_state.page
pid = st.session_state.get("pid")
sid = st.session_state.get("sid")

if page == "problem_detail":
    problem_detail_page(pid)
elif page == "problem_records":
    problem_records_page(pid)
elif page == "submission":
    submission_page(sid)
elif page == "profile":
    profile_page()
elif page == "ai":
    ai_page()
elif page == "languages":
    languages_page()
elif page == "users":
    users_admin_page()
elif page == "logs":
    logs_admin_page()
else:
    problems_page()
