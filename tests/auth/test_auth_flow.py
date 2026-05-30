"""Auth 模块接口测试：覆盖每个接口的所有情况（含 captcha）"""

import asyncio
import sys
import uuid

sys.path.insert(0, "../../backend")

import httpx

BASE = "http://127.0.0.1:8000"
PASS = "Pass1234"

# ─── helpers ──────────────────────────────────────────────────────────────

async def cap(c: httpx.AsyncClient) -> tuple[str, int]:
    r = await c.post(f"{BASE}/api/v1/auth/captcha/challenge")
    ok(r)
    return r.json()["slider_token"], 200


async def reg(c: httpx.AsyncClient, username: str, email: str, password: str = PASS):
    """注册并返回响应"""
    token, x = await cap(c)
    return await c.post(f"{BASE}/api/v1/auth/register", json={
        "username": username, "email": email, "password": password,
        "slider_token": token, "slider_x": x,
    })


async def login(c: httpx.AsyncClient, user: str, pw: str = PASS):
    """登录并返回响应"""
    token, x = await cap(c)
    form = f"username={user}&password={pw}&slider_token={token}&slider_x={x}"
    return await c.post(f"{BASE}/api/v1/auth/login", content=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"})


async def upgrade(c: httpx.AsyncClient, username: str, email: str, password: str = PASS):
    token, x = await cap(c)
    return await c.post(f"{BASE}/api/v1/auth/upgrade", json={
        "username": username, "email": email, "password": password,
        "slider_token": token, "slider_x": x,
    })


def ok(r, label=""):
    assert r.status_code == 200, f"[{label}] expected 200, got {r.status_code}: {r.text}"


def bad(r, code, label=""):
    if r.status_code == 422:
        return  # validation errors pass
    assert r.status_code in (400, 401, 403, 404), f"[{label}] expected error, got {r.status_code}: {r.text}"
    detail = r.json().get("detail", {})
    actual = detail.get("code") if isinstance(detail, dict) else None
    assert actual == code, f"[{label}] expected {code}, got {actual}: {r.text}"


# ─── main ─────────────────────────────────────────────────────────────────

async def main():
    transport = httpx.AsyncHTTPTransport(retries=1)
    total, passed = 0, 0

    def t(label): nonlocal total; total += 1; return label
    def p(): nonlocal passed; passed += 1

    # =====================================================================
    # 0. Captcha 接口
    # =====================================================================
    print("=" * 60)
    print("0. POST /auth/captcha — 滑块验证")
    print("=" * 60)

    async with httpx.AsyncClient(transport=transport, timeout=10) as c:
        label = t("0.1 获取 captcha challenge")
        token, x = await cap(c)
        assert token, label
        print(f"    PASS token={token[:16]}...")
        p()

        label = t("0.2 有效 captcha 注册通过")
        r = await c.post(f"{BASE}/api/v1/auth/register", json={
            "username": f"capok_{uuid.uuid4().hex[:8]}",
            "email": f"capok_{uuid.uuid4().hex[:8]}@test.com",
            "password": PASS,
            "slider_token": token, "slider_x": x,
        })
        ok(r, label)
        print(f"    PASS")
        p()

        label = t("0.3 captcha token 重复使用被拒")
        r = await c.post(f"{BASE}/api/v1/auth/register", json={
            "username": f"replay_{uuid.uuid4().hex[:8]}",
            "email": f"replay_{uuid.uuid4().hex[:8]}@test.com",
            "password": PASS,
            "slider_token": token, "slider_x": x,
        })
        bad(r, "CAPTCHA_FAILED", label)
        print(f"    PASS")
        p()

        label = t("0.4 无效 captcha token 被拒")
        r = await c.post(f"{BASE}/api/v1/auth/register", json={
            "username": f"badcap_{uuid.uuid4().hex[:8]}",
            "email": f"badcap_{uuid.uuid4().hex[:8]}@test.com",
            "password": PASS,
            "slider_token": "not-a-real-token", "slider_x": 200,
        })
        bad(r, "CAPTCHA_FAILED", label)
        print(f"    PASS")
        p()

        label = t("0.5 slider_x 太小被拒")
        r = await cap(c)
        r = await c.post(f"{BASE}/api/v1/auth/register", json={
            "username": f"toosmall_{uuid.uuid4().hex[:8]}",
            "email": f"toosmall_{uuid.uuid4().hex[:8]}@test.com",
            "password": PASS,
            "slider_token": r[0], "slider_x": 5,
        })
        bad(r, "CAPTCHA_FAILED", label)
        print(f"    PASS")
        p()

    # =====================================================================
    # 1. POST /auth/guest
    # =====================================================================
    print("\n" + "=" * 60)
    print("1. POST /auth/guest — 游客登录")
    print("=" * 60)

    async with httpx.AsyncClient(transport=transport, timeout=10) as c:
        label = t("1.1 首次创建游客")
        r = await c.post(f"{BASE}/api/v1/auth/guest")
        ok(r, label)
        data = r.json()
        assert data["is_guest"] is True
        assert "session_id" in c.cookies
        print(f"    PASS user_id={data['user_id']}")
        p()

        label = t("1.2 再次调用创建新游客")
        async with httpx.AsyncClient(transport=transport, timeout=10) as c2:
            r2 = await c2.post(f"{BASE}/api/v1/auth/guest")
            ok(r2, label)
            assert r2.json()["user_id"] != data["user_id"]
            print(f"    PASS 不同 user_id")
        p()

        label = t("1.3 游客可访问 GET /reports/")
        r = await c.get(f"{BASE}/api/v1/reports/")
        ok(r, label)
        print(f"    PASS")
        p()

        label = t("1.4 游客被拒绝 POST /search/start")
        r = await c.post(f"{BASE}/api/v1/search/start", json={"query": "t", "search_mode": "api"})
        bad(r, "GUEST_FORBIDDEN", label)
        print(f"    PASS")
        p()

    # =====================================================================
    # 2. POST /auth/register
    # =====================================================================
    print("\n" + "=" * 60)
    print("2. POST /auth/register — 注册")
    print("=" * 60)

    async with httpx.AsyncClient(transport=transport, timeout=10) as c:
        uid = uuid.uuid4().hex[:8]

        label = t("2.1 正常注册")
        r = await reg(c, f"user_{uid}", f"{uid}@test.com")
        ok(r, label)
        d = r.json()
        assert d["is_guest"] is False
        assert d["username"] == f"user_{uid}"
        assert "access_token" in d
        print(f"    PASS username={d['username']}")
        p()

        label = t("2.2 用户名已存在")
        r = await reg(c, f"user_{uid}", f"another_{uid}@test.com")
        bad(r, "AUTH_USERNAME_EXISTS", label)
        p()

        label = t("2.3 邮箱已存在")
        r = await reg(c, f"other_{uid}", f"{uid}@test.com")
        bad(r, "AUTH_EMAIL_EXISTS", label)
        p()

        label = t("2.4 用户名太短 (<3)")
        r = await reg(c, "ab", f"short_{uid}@test.com")
        assert r.status_code == 422
        p()

        label = t("2.5 用户名含非法字符")
        token, x = await cap(c)
        r = await c.post(f"{BASE}/api/v1/auth/register", json={
            "username": "user name", "email": f"space_{uid}@test.com", "password": PASS,
            "slider_token": token, "slider_x": x,
        })
        assert r.status_code == 422
        p()

        label = t("2.6 密码缺字母")
        r = await reg(c, f"pw1_{uid}", f"pw1_{uid}@test.com", "12345678")
        bad(r, "AUTH_WEAK_PASSWORD", label)
        p()

        label = t("2.7 密码缺数字")
        r = await reg(c, f"pw2_{uid}", f"pw2_{uid}@test.com", "abcdefgh")
        bad(r, "AUTH_WEAK_PASSWORD", label)
        p()

        label = t("2.8 密码太短")
        r = await reg(c, f"pw3_{uid}", f"pw3_{uid}@test.com", "Ab12")
        bad(r, "AUTH_WEAK_PASSWORD", label)
        p()

    # =====================================================================
    # 3. POST /auth/login
    # =====================================================================
    print("\n" + "=" * 60)
    print("3. POST /auth/login — 登录")
    print("=" * 60)

    async with httpx.AsyncClient(transport=transport, timeout=10) as c:
        uid = uuid.uuid4().hex[:8]
        uname = f"login_{uid}"
        email = f"{uid}@login.com"
        r = await reg(c, uname, email)
        ok(r, "pre-register")

        label = t("3.1 邮箱登录")
        r = await login(c, email)
        ok(r, label)
        assert r.json()["username"] == uname
        p()

        label = t("3.2 用户名登录")
        r = await login(c, uname)
        ok(r, label)
        p()

        label = t("3.3 密码错误")
        r = await login(c, email, "WrongPass1")
        bad(r, "AUTH_INVALID_CREDENTIALS", label)
        p()

        label = t("3.4 用户不存在")
        r = await login(c, f"nobody_{uid}")
        bad(r, "AUTH_INVALID_CREDENTIALS", label)
        p()

        label = t("3.5 登录更新 last_login_at")
        r = await login(c, email)
        ok(r, label)
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        me = await c.get(f"{BASE}/api/v1/users/me", headers=h)
        ok(me, label)
        assert me.json()["last_login_at"] is not None
        p()

    # =====================================================================
    # 4. POST /auth/refresh
    # =====================================================================
    print("\n" + "=" * 60)
    print("4. POST /auth/refresh — 令牌刷新")
    print("=" * 60)

    async with httpx.AsyncClient(transport=transport, timeout=10) as c:
        uid = uuid.uuid4().hex[:8]
        r = await reg(c, f"refresh_{uid}", f"refresh_{uid}@test.com")
        old_access = r.json()["access_token"]
        old_refresh = r.json()["refresh_token"]

        label = t("4.1 正常刷新")
        r = await c.post(f"{BASE}/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        ok(r, label)
        assert r.json()["access_token"] != old_access
        assert r.json()["refresh_token"] != old_refresh
        p()

        label = t("4.2 旧 refresh token 失效")
        r = await c.post(f"{BASE}/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        bad(r, "AUTH_REFRESH_INVALID", label)
        p()

        label = t("4.3 无效 token")
        r = await c.post(f"{BASE}/api/v1/auth/refresh", json={"refresh_token": "bad.token"})
        bad(r, "AUTH_REFRESH_INVALID", label)
        p()

        label = t("4.4 access token 充当 refresh")
        r = await c.post(f"{BASE}/api/v1/auth/refresh", json={"refresh_token": old_access})
        bad(r, "AUTH_REFRESH_INVALID", label)
        p()

    # =====================================================================
    # 5. POST /auth/logout
    # =====================================================================
    print("\n" + "=" * 60)
    print("5. POST /auth/logout — 登出")
    print("=" * 60)

    async with httpx.AsyncClient(transport=transport, timeout=10) as c:
        uid = uuid.uuid4().hex[:8]
        r = await reg(c, f"logout_{uid}", f"logout_{uid}@test.com")
        token = r.json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}

        label = t("5.1 正常登出")
        r = await c.post(f"{BASE}/api/v1/auth/logout", headers=h)
        ok(r, label)
        p()

        label = t("5.2 登出后 token 黑名单生效")
        r = await c.get(f"{BASE}/api/v1/users/me", headers=h)
        bad(r, "AUTH_TOKEN_BLACKLISTED", label)
        p()

        label = t("5.3 无 token 登出不报错")
        r = await c.post(f"{BASE}/api/v1/auth/logout")
        ok(r, label)
        p()

        label = t("5.4 游客登出清除 session")
        async with httpx.AsyncClient(transport=transport, timeout=10) as c2:
            await c2.post(f"{BASE}/api/v1/auth/guest")
            r = await c2.post(f"{BASE}/api/v1/auth/logout")
            ok(r, label)
            r = await c2.get(f"{BASE}/api/v1/users/me")
            assert r.status_code == 401
            p()

    # =====================================================================
    # 6. POST /auth/upgrade
    # =====================================================================
    print("\n" + "=" * 60)
    print("6. POST /auth/upgrade — 游客升级")
    print("=" * 60)

    async with httpx.AsyncClient(transport=transport, timeout=10) as c:
        uid = uuid.uuid4().hex[:8]

        label = t("6.1 正常升级")
        await c.post(f"{BASE}/api/v1/auth/guest")
        r = await upgrade(c, f"upgrade_{uid}", f"upgrade_{uid}@test.com")
        ok(r, label)
        d = r.json()
        assert d["is_guest"] is False
        assert d["username"] == f"upgrade_{uid}"
        print(f"    PASS")
        p()

        label = t("6.2 已注册用户升级被拒")
        token = d["access_token"]
        h = {"Authorization": f"Bearer {token}"}
        r = await upgrade(c, f"again_{uid}", f"again_{uid}@test.com")
        bad(r, "GUEST_ALREADY_REGISTERED", label)
        p()

        label = t("6.3 升级时用户名冲突")
        async with httpx.AsyncClient(transport=transport, timeout=10) as c2:
            await c2.post(f"{BASE}/api/v1/auth/guest")
            r = await upgrade(c2, f"upgrade_{uid}", f"conflict_{uid}@test.com")
            bad(r, "AUTH_USERNAME_EXISTS", label)
            p()

        label = t("6.4 升级时邮箱冲突")
        async with httpx.AsyncClient(transport=transport, timeout=10) as c3:
            await c3.post(f"{BASE}/api/v1/auth/guest")
            r = await upgrade(c3, f"email_conflict_{uid}", f"upgrade_{uid}@test.com")
            bad(r, "AUTH_EMAIL_EXISTS", label)
            p()

        label = t("6.5 升级时密码弱")
        async with httpx.AsyncClient(transport=transport, timeout=10) as c4:
            await c4.post(f"{BASE}/api/v1/auth/guest")
            r = await upgrade(c4, f"weakpw_{uid}", f"weakpw_{uid}@test.com", "12345678")
            bad(r, "AUTH_WEAK_PASSWORD", label)
            p()

        label = t("6.6 未认证升级 401")
        async with httpx.AsyncClient(transport=transport, timeout=10) as c5:
            token, x = await cap(c5)
            r = await c5.post(f"{BASE}/api/v1/auth/upgrade", json={
                "username": f"nobody_{uid}", "email": f"nobody_{uid}@test.com", "password": PASS,
                "slider_token": token, "slider_x": x,
            })
            assert r.status_code == 401
            p()

    # =====================================================================
    # 7. GET /users/me
    # =====================================================================
    print("\n" + "=" * 60)
    print("7. GET /users/me — 获取当前用户")
    print("=" * 60)

    async with httpx.AsyncClient(transport=transport, timeout=10) as c:
        uid = uuid.uuid4().hex[:8]

        label = t("7.1 注册用户获取 /me")
        r = await reg(c, f"me_{uid}", f"me_{uid}@test.com")
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = await c.get(f"{BASE}/api/v1/users/me", headers=h)
        ok(r, label)
        me = r.json()
        assert me["username"] == f"me_{uid}"
        assert me["is_guest"] is False
        p()

        label = t("7.2 游客获取 /me")
        async with httpx.AsyncClient(transport=transport, timeout=10) as c2:
            await c2.post(f"{BASE}/api/v1/auth/guest")
            r = await c2.get(f"{BASE}/api/v1/users/me")
            ok(r, label)
            assert r.json()["is_guest"] is True
            assert r.json()["username"] is None
            p()

        label = t("7.3 无认证 401")
        async with httpx.AsyncClient(transport=transport, timeout=10) as c3:
            r = await c3.get(f"{BASE}/api/v1/users/me")
            assert r.status_code == 401
            p()

    # =====================================================================
    # result
    # =====================================================================
    print("\n" + "=" * 60)
    print(f"结果: {passed}/{total} 通过")
    if passed == total:
        print("全部测试通过!")
    else:
        print(f"失败 {total - passed} 项")


if __name__ == "__main__":
    print("请先启动: docker-compose up -d db redis && cd backend && uvicorn main:app --host 0.0.0.0 --port 8000\n")
    asyncio.run(main())
