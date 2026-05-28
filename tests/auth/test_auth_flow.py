"""测试完整登录流程：游客 → 注册/升级 → 登录 → 刷新 → 登出"""

import asyncio
import sys
import uuid

sys.path.insert(0, "../../backend")

import httpx

BASE = "http://127.0.0.1:8000"


async def main():
    transport = httpx.AsyncHTTPTransport(retries=1)
    async with httpx.AsyncClient(transport=transport, timeout=10) as c:
        fp = "test-fp-" + uuid.uuid4().hex[:12]

        # 1. 游客登录
        print("1. 游客登录...")
        r = await c.post(f"{BASE}/api/v1/auth/guest", json={"fingerprint": fp})
        assert r.status_code == 200, f"status={r.status_code} body={r.text}"
        data = r.json()
        assert data["is_guest"] is True
        assert "access_token" in data and "refresh_token" in data
        access = data["access_token"]
        refresh = data["refresh_token"]
        user_id = data["user_id"]
        print(f"   游客 user_id={user_id[:8]}... token OK")

        # 2. 同一指纹再次登录（会轮换 refresh token）
        print("2. 同一 fingerprint 再次登录...")
        r = await c.post(f"{BASE}/api/v1/auth/guest", json={"fingerprint": fp})
        assert r.status_code == 200
        assert r.json()["user_id"] == user_id
        access = r.json()["access_token"]
        refresh = r.json()["refresh_token"]
        print("   同一用户确认，token 已刷新")

        # 3. 用最新的 refresh token 刷新
        print("3. 刷新 access token...")
        r = await c.post(f"{BASE}/api/v1/auth/refresh", json={"refresh_token": refresh})
        assert r.status_code == 200, f"status={r.status_code} body={r.text}"
        new_data = r.json()
        new_access = new_data["access_token"]
        new_refresh = new_data["refresh_token"]
        assert new_access != access
        assert new_refresh != refresh
        print("   令牌已轮换")

        # 4. 旧 refresh token 此时已失效
        print("4. 旧 refresh token 应失效...")
        r = await c.post(f"{BASE}/api/v1/auth/refresh", json={"refresh_token": refresh})
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"
        print(f"   旧 token 被拒绝 (code={r.json()['detail']['code']})")

        # 5. 游客升级
        print("5. 游客升级为注册用户...")
        email = f"test-{uuid.uuid4().hex}@example.com"
        r = await c.post(f"{BASE}/api/v1/auth/upgrade", json={
            "fingerprint": fp, "email": email, "password": "pass1234",
        })
        assert r.status_code == 200, f"status={r.status_code} body={r.text}"
        assert r.json()["is_guest"] is False
        print("   升级成功")

        # 6. 弱密码校验
        print("6. 密码强度校验...")
        for pw, expected_msg in [
            ("12345678", "letter"),
            ("abcdefgh", "digit"),
            ("ab12", "at least 8"),
        ]:
            r = await c.post(f"{BASE}/api/v1/auth/register", json={"email": f"x-{pw[:4]}@t.com", "password": pw})
            assert r.status_code == 400, f"Expected 400 for pw={pw}, got {r.status_code}"
            print(f"   '{pw}' → {r.json()['detail']['detail']}")

        # 7. 邮箱登录
        print("7. 邮箱+密码登录...")
        r = await c.post(f"{BASE}/api/v1/auth/login", data={"username": email, "password": "pass1234"})
        assert r.status_code == 200, f"status={r.status_code} body={r.text}"
        login_data = r.json()
        assert login_data["is_guest"] is False
        print("   登录成功")

        # 8. 登出
        print("8. 登出...")
        h = {"Authorization": f"Bearer {login_data['access_token']}"}
        r = await c.post(f"{BASE}/api/v1/auth/logout", headers=h)
        assert r.status_code == 200, r.text

        # 9. 黑名单生效
        print("9. 已登出 token 被拒绝...")
        r = await c.get(f"{BASE}/api/v1/users/me", headers=h)
        assert r.status_code == 401
        print(f"   code={r.json()['detail']['code']}")

        print("\n全部 9 项测试通过!")


if __name__ == "__main__":
    print("请先启动后端: cd backend && uvicorn main:app --host 0.0.0.0 --port 8000\n")
    asyncio.run(main())
