"""Basic API smoke tests. Run with:  pytest tests/ -v

These tests use the real judge, so python must be available on PATH.
Each test starts from a clean state via POST /api/reset/.
"""

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app

PROBLEM = {
    "id": "P1001",
    "title": "A+B Problem",
    "description": "输入两个整数 a, b，输出它们的和。",
    "input_description": "输入两个整数 a 和 b。",
    "output_description": "输出 a+b 的结果。",
    "samples": [{"input": "1 2", "output": "3"}],
    "constraints": "|a|,|b| <= 10^9",
    "testcases": [{"input": "1 2", "output": "3"}, {"input": "-1 1", "output": "0"}],
    "hint": "",
    "source": "luogu",
    "tags": ["基础题"],
    "time_limit": 3.0,
    "memory_limit": 256,
    "author": "test",
    "difficulty": "入门",
}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clean_state(client):
    """Reset the system before every test for isolation."""
    resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admintestpassword"},
    )
    assert resp.status_code == 200, resp.text
    resp = client.post("/api/reset/")
    assert resp.status_code == 200, resp.text


def _login(client: TestClient, username="admin", password="admintestpassword"):
    resp = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp


def _register(client: TestClient, username="alice", password="password123"):
    resp = client.post("/api/users/", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp


def _add_problem(client: TestClient, problem=None):
    resp = client.post("/api/problems/", json=problem or PROBLEM)
    assert resp.status_code == 200, resp.text
    return resp


def _wait_submission(client: TestClient, sid: str, tries: int = 100):
    for _ in range(tries):
        resp = client.get(f"/api/submissions/{sid}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        if data["status"] != "pending":
            return data
        time.sleep(0.2)
    pytest.fail("submission stayed pending")


# ---------------- Step 1 ----------------

def test_problem_crud(client):
    _login(client)
    _add_problem(client)
    # list
    resp = client.get("/api/problems/")
    assert resp.status_code == 200
    assert {"id": "P1001", "title": "A+B Problem"} in resp.json()["data"]
    # detail (testcases visible to normal users, TA Q&A #3)
    resp = client.get("/api/problems/P1001")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["testcases"] == PROBLEM["testcases"]
    assert data["hint"] == ""
    # duplicate -> 409
    resp = client.post("/api/problems/", json=PROBLEM)
    assert resp.status_code == 409
    # update
    updated = dict(PROBLEM, title="A+B Pro")
    resp = client.put("/api/problems/P1001", json=updated)
    assert resp.status_code == 200
    # id mismatch -> 400
    resp = client.put("/api/problems/P1001", json={**updated, "id": "P9999"})
    assert resp.status_code == 400
    # delete (admin)
    resp = client.delete("/api/problems/P1001")
    assert resp.status_code == 200
    resp = client.get("/api/problems/P1001")
    assert resp.status_code == 404


def test_unauthenticated(client):
    resp = client.get("/api/problems/")
    assert resp.status_code == 401
    body = resp.json()
    assert body["code"] == 401 and body["data"] is None


def test_delete_problem_cascades(client):
    """TA Q&A #4/#8: deleting a problem removes related submissions/logs
    and reverts user counters."""
    _login(client)
    _add_problem(client)
    alice_id = _register(client, "alice", "password123").json()["data"]["user_id"]
    client.post("/api/auth/logout")
    _login(client, "alice", "password123")
    resp = client.post(
        "/api/submissions/",
        json={
            "problem_id": "P1001",
            "language": "python",
            "code": "a, b = map(int, input().split())\nprint(a + b)",
        },
    )
    sid = resp.json()["data"]["submission_id"]
    _wait_submission(client, sid)
    # check counters before delete
    client.post("/api/auth/logout")
    _login(client)
    alice = client.get(f"/api/users/{alice_id}").json()["data"]
    assert alice["submit_count"] == 1 and alice["resolve_count"] == 1
    # delete the problem: counters revert, submission disappears
    resp = client.delete("/api/problems/P1001")
    assert resp.status_code == 200
    alice = client.get(f"/api/users/{alice_id}").json()["data"]
    assert alice["submit_count"] == 0 and alice["resolve_count"] == 0
    resp = client.get(f"/api/submissions/{sid}")
    assert resp.status_code == 404


# ---------------- Step 2 & 3 ----------------

def test_submit_python_ac_and_log(client):
    _login(client)
    _add_problem(client)
    resp = client.post(
        "/api/submissions/",
        json={
            "problem_id": "P1001",
            "language": "python",
            "code": "a, b = map(int, input().split())\nprint(a + b)",
        },
    )
    assert resp.status_code == 200
    sid = resp.json()["data"]["submission_id"]
    data = _wait_submission(client, sid)
    assert data["status"] == "success"
    assert data["score"] == data["counts"] == 20
    # judge log details
    resp = client.get(f"/api/submissions/{sid}/log")
    assert resp.status_code == 200
    details = resp.json()["data"]["details"]
    assert [d["result"] for d in details] == ["AC", "AC"]


def test_submit_wa_and_tle(client):
    _login(client)
    _add_problem(client)
    # WA: wrong on every test point (answers are "3" and "0")
    resp = client.post(
        "/api/submissions/",
        json={"problem_id": "P1001", "language": "python", "code": "print('wrong')"},
    )
    sid = resp.json()["data"]["submission_id"]
    data = _wait_submission(client, sid)
    assert data["status"] == "success" and data["score"] == 0
    # TLE
    resp = client.post(
        "/api/submissions/",
        json={
            "problem_id": "P1001",
            "language": "python",
            "code": "import time\ntime.sleep(10)\nprint(1)",
        },
    )
    sid = resp.json()["data"]["submission_id"]
    data = _wait_submission(client, sid, tries=150)
    assert data["status"] == "success"
    log = client.get(f"/api/submissions/{sid}/log").json()["data"]["details"]
    assert any(d["result"] == "TLE" for d in log)


def test_rate_limit_429(client):
    _login(client)
    _add_problem(client)
    body = {"problem_id": "P1001", "language": "python", "code": "print(0)"}
    for _ in range(3):
        resp = client.post("/api/submissions/", json=body)
        assert resp.status_code == 200
    resp = client.post("/api/submissions/", json=body)
    assert resp.status_code == 429


def test_rejudge(client):
    _login(client)
    _add_problem(client)
    resp = client.post(
        "/api/submissions/",
        json={"problem_id": "P1001", "language": "python", "code": "print(0)"},
    )
    sid = resp.json()["data"]["submission_id"]
    _wait_submission(client, sid)
    resp = client.put(f"/api/submissions/{sid}/rejudge")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "pending"


def test_languages(client):
    _login(client)
    resp = client.get("/api/languages/")
    assert resp.status_code == 200
    assert "python" in resp.json()["data"]["name"]
    # register a new language (no compiler installation, TA Q&A #6)
    resp = client.post(
        "/api/languages/",
        json={"name": "py3", "file_ext": ".py", "run_cmd": "python3 {src}"},
    )
    assert resp.status_code == 200
    resp = client.get("/api/languages/")
    assert "py3" in resp.json()["data"]["name"]


# ---------------- Step 4 ----------------

def test_register_login_permissions(client):
    _register(client, "alice", "password123")
    # duplicate register -> 400
    resp = client.post("/api/users/", json={"username": "alice", "password": "password123"})
    assert resp.status_code == 400
    # wrong password -> 401
    resp = client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
    assert resp.status_code == 401
    # normal user cannot change roles
    resp = client.post("/api/auth/login", json={"username": "alice", "password": "password123"})
    assert resp.status_code == 200
    alice_id = resp.json()["data"]["user_id"]
    resp = client.put(f"/api/users/{alice_id}/role", json={"role": "admin"})
    assert resp.status_code == 403
    # admin can ban
    _login(client)
    resp = client.put(f"/api/users/{alice_id}/role", json={"role": "banned"})
    assert resp.status_code == 200
    # banned user cannot log in
    resp = client.post("/api/auth/login", json={"username": "alice", "password": "password123"})
    assert resp.status_code == 403


# ---------------- Step 5 ----------------

def test_log_visibility_and_audit(client):
    _login(client)
    _add_problem(client)
    client.post("/api/auth/logout")
    _register(client, "alice", "password123")
    resp = client.post("/api/auth/login", json={"username": "alice", "password": "password123"})
    resp = client.post(
        "/api/submissions/",
        json={"problem_id": "P1001", "language": "python", "code": "print(0)"},
    )
    sid = resp.json()["data"]["submission_id"]
    _wait_submission(client, sid)
    client.post("/api/auth/logout")
    # admin sees anyone's log: allowed, and it is audited
    _login(client)
    resp = client.get(f"/api/submissions/{sid}/log")
    assert resp.status_code == 200
    resp = client.get("/api/logs/access/", params={"problem_id": "P1001"})
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1
    # both-empty primary conditions -> 400 (TA Q&A #9)
    resp = client.get("/api/logs/access/")
    assert resp.status_code == 400
    # visibility config
    resp = client.put("/api/problems/P1001/log_visibility", json={"public_cases": True})
    assert resp.status_code == 200
    assert resp.json()["data"]["public_cases"] is True


def test_reset(client):
    _login(client)
    _add_problem(client)
    resp = client.post("/api/reset/")
    assert resp.status_code == 200
    resp = client.get("/api/problems/")
    assert resp.status_code == 401  # reset logs everyone out
    _login(client)
    resp = client.get("/api/problems/")
    assert resp.json()["data"] == []


# ---------------- judge statuses: CE / RE / MLE ----------------

def _submit_and_wait(client, problem_id, language, code, tries=150):
    resp = client.post(
        "/api/submissions/",
        json={"problem_id": problem_id, "language": language, "code": code},
    )
    assert resp.status_code == 200, resp.text
    sid = resp.json()["data"]["submission_id"]
    return sid, _wait_submission(client, sid, tries=tries)


def test_compile_error_ce(client):
    """C++ with a syntax error -> CE on every test point, score 0."""
    _login(client)
    _add_problem(client)
    sid, data = _submit_and_wait(
        client, "P1001", "cpp", "int main(){ this is not valid c++ }"
    )
    assert data["status"] == "success" and data["score"] == 0
    assert data["compile_info"]["result"] == "failed"
    log = client.get(f"/api/submissions/{sid}/log").json()["data"]["details"]
    assert all(d["result"] == "CE" for d in log)


def test_runtime_error_re(client):
    """Python division by zero -> RE, score 0."""
    _login(client)
    _add_problem(client)
    sid, data = _submit_and_wait(client, "P1001", "python", "1 // 0")
    assert data["status"] == "success" and data["score"] == 0
    log = client.get(f"/api/submissions/{sid}/log").json()["data"]["details"]
    assert all(d["result"] == "RE" for d in log)


def test_memory_limit_mle(client):
    """Allocating > memory_limit and holding it -> MLE."""
    _login(client)
    _add_problem(client, problem={**PROBLEM, "memory_limit": 64, "time_limit": 10.0})
    code = "x = bytearray(300 * 1024 * 1024)\nimport time\ntime.sleep(5)\nprint(0)"
    sid, data = _submit_and_wait(client, "P1001", "python", code, tries=200)
    assert data["status"] == "success"
    log = client.get(f"/api/submissions/{sid}/log").json()["data"]["details"]
    assert any(d["result"] == "MLE" for d in log)


def test_submission_list_permissions(client):
    """Admins see everyone's records for a problem; users only their own."""
    _login(client)
    _add_problem(client)
    _register(client, "alice", "password123")
    client.post("/api/auth/logout")
    _login(client, "alice", "password123")
    client.post(
        "/api/submissions/",
        json={"problem_id": "P1001", "language": "python", "code": "print(0)"},
    )
    client.post("/api/auth/logout")
    _login(client)
    # admin without user_id sees all records of the problem
    resp = client.get("/api/submissions/", params={"problem_id": "P1001"})
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] == 1
    # pagination rule: page without page_size -> 400
    resp = client.get(
        "/api/submissions/", params={"problem_id": "P1001", "page": 1}
    )
    assert resp.status_code == 400
    # regular user without user_id sees only their own (0 here)
    client.post("/api/auth/logout")
    _login(client, "alice", "password123")
    resp = client.get("/api/submissions/", params={"problem_id": "P1001"})
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] == 1  # alice's own submission
    # alice cannot query as another user
    resp = client.get("/api/submissions/", params={"user_id": "1"})
    assert resp.status_code == 403

