"""Seed a few demo problems for the acceptance demo.

Usage (with the backend running on :8000):
    python scripts/seed_demo.py
"""

import requests

BASE = "http://127.0.0.1:8000"

PROBLEMS = [
    {
        "id": "P1001",
        "title": "A+B Problem",
        "description": "输入两个整数 a, b，输出它们的和。",
        "input_description": "一行两个整数 a 和 b，空格分隔。",
        "output_description": "一行，输出 a+b 的结果。",
        "samples": [{"input": "1 2", "output": "3"}],
        "constraints": "|a|,|b| <= 10^9",
        "testcases": [
            {"input": "1 2", "output": "3"},
            {"input": "-1 1", "output": "0"},
            {"input": "1000000000 1000000000", "output": "2000000000"},
        ],
        "hint": "注意负数哦！",
        "source": "洛谷",
        "tags": ["基础题", "模拟"],
        "time_limit": 1.0,
        "memory_limit": 128,
        "author": "Luogu",
        "difficulty": "入门",
    },
    {
        "id": "sum_2",
        "title": "两数之和",
        "description": "给定一个整数数组 nums 和一个目标值 target，输出是否存在两个数的和等于 target（输出 Yes/No）。",
        "input_description": "第一行两个整数 n 和 target；第二行 n 个整数。",
        "output_description": "一行 Yes 或 No。",
        "samples": [{"input": "4 9\n2 7 11 15", "output": "Yes"}],
        "constraints": "2 <= n <= 10^4, 数值范围 [-10^9, 10^9]",
        "testcases": [
            {"input": "4 9\n2 7 11 15", "output": "Yes"},
            {"input": "3 6\n3 2 4", "output": "No"},
            {"input": "2 0\n-1 1", "output": "Yes"},
        ],
        "hint": "",
        "source": "LeetCode 改编",
        "tags": ["哈希", "数组"],
        "time_limit": 1.0,
        "memory_limit": 128,
        "author": "demo",
        "difficulty": "简单",
    },
    {
        "id": "fib",
        "title": "斐波那契数列",
        "description": "输出斐波那契数列的第 n 项（从 0 开始：F(0)=0, F(1)=1），结果对 10^9+7 取模。",
        "input_description": "一行一个整数 n。",
        "output_description": "一行，F(n) mod 1e9+7。",
        "samples": [{"input": "10", "output": "55"}],
        "constraints": "0 <= n <= 10^6",
        "testcases": [
            {"input": "0", "output": "0"},
            {"input": "10", "output": "55"},
            {"input": "1000000", "output": "918091266"},
        ],
        "hint": "O(n) 递推即可，注意取模。",
        "source": "自编",
        "tags": ["动态规划"],
        "time_limit": 2.0,
        "memory_limit": 128,
        "author": "demo",
        "difficulty": "中等",
    },
]


def main():
    s = requests.Session()
    resp = s.post(
        f"{BASE}/api/auth/login",
        json={"username": "admin", "password": "admintestpassword"},
    )
    if resp.status_code != 200:
        print("login failed:", resp.text)
        return
    print("logged in as admin")
    for p in PROBLEMS:
        r = s.post(f"{BASE}/api/problems/", json=p)
        if r.status_code == 200:
            print(f"added   {p['id']} - {p['title']}")
        else:
            print(f"skipped {p['id']}: {r.json().get('msg')}")


if __name__ == "__main__":
    main()
