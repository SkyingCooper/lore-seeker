"""搜索服务：API 搜索 + RSS/静态/动态爬取决策。

本文件负责两类能力：
1. 搜索 API provider 调用。
2. 网页抓取决策链路：RSS -> HTTP 静态抓取 -> 必要时降级到 Playwright。

抓取决策的长期学习结果进入 `site_crawl_profiles`，热缓存进入 Redis。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree

import httpx
import yaml
from bs4 import BeautifulSoup
from redis.asyncio import Redis
from sqlalchemy import select

from core.config import settings
from core.database import AsyncSessionLocal
from core.redis_client import get_redis
from core.task_redis import append_log
from db.models import SiteCrawlProfile

TOOL_MCP_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "tool_mcp.yaml"


@dataclass
class CrawlPayload:
    title: str
    url: str
    html: str
    content: str
    extractor: str
    status: str = "succeeded"
    error: dict[str, Any] | None = None


async def search_api(query: str, site_filter: list[str] | None = None) -> list[dict]:
    """调用搜索 API，返回 [{title, url, content}]。"""
    p = settings.SEARCH_API_PROVIDER

    if p == "tavily":
        return await _tavily_search(query, site_filter)
    if p == "serpapi":
        return await _serpapi_search(query, site_filter)
    if p == "bing":
        return await _bing_search(query, site_filter)
    return []


async def crawl_sites(
    sites: list[str],
    queries: list[str],
    *,
    task_id: str | int | None = None,
    crawler_mode: str = "auto",
) -> list[dict]:
    """按站点执行 RSS / 静态 HTTP / 动态 Playwright 抓取。

    `crawler_mode`:
    - `auto`: 先静态，命中规则再降级动态。
    - `static`: 强制静态。
    - `dynamic`: 强制动态。
    """
    if not settings.CRAWLER_ENABLED:
        return []

    cfg = _crawler_runtime()
    redis = await get_redis()
    results: list[dict[str, Any]] = []
    queries = [query for query in queries if query]

    for site in sites[:5]:
        domain = _domain_from_url(site)
        capability = _source_capability(domain, cfg)
        profile = await _load_site_profile(redis, domain, capability, cfg)

        if capability.get("rss_url"):
            rss_results = await _crawl_via_rss(
                rss_url=str(capability["rss_url"]),
                site=site,
                queries=queries,
                task_id=task_id,
            )
            if rss_results:
                results.extend(rss_results)
                await _update_site_profile(
                    redis=redis,
                    domain=domain,
                    capability=capability,
                    final_mode="rss",
                    decision={"score": 0.0, "matched_rules": ["rss_configured"], "reason": "configured_rss"},
                    final_payload=CrawlPayload(
                        title=rss_results[0].get("title") or site,
                        url=site,
                        html="",
                        content="\n".join(item.get("content", "") for item in rss_results[:3]),
                        extractor="rss",
                    ),
                )
                continue

        static_payload = await _crawl_static(site, cfg)
        decision = _evaluate_dynamic_need(
            html=static_payload.html,
            extracted_text=static_payload.content,
            domain=domain,
            profile=profile,
            cfg=cfg,
            forced_mode=crawler_mode,
        )

        final_mode = "static"
        final_payload = static_payload
        if crawler_mode == "dynamic" or decision["should_use_dynamic"]:
            dynamic_payload = await _crawl_dynamic(site, cfg)
            if _prefer_dynamic(static_payload, dynamic_payload):
                final_mode = "dynamic"
                final_payload = dynamic_payload

        result = _build_crawl_result(
            site=site,
            domain=domain,
            payload=final_payload,
            decision=decision,
            final_mode=final_mode,
            queries=queries,
        )
        results.append(result)

        if task_id:
            await _append_crawl_decision(redis, int(task_id), result["crawl_decision"])
            await append_log(
                redis,
                int(task_id),
                "searcher",
                f"抓取决策：{domain}",
                interaction_type="state_update",
                status="running",
                payload=result["crawl_decision"],
            )

        await _update_site_profile(
            redis=redis,
            domain=domain,
            capability=capability,
            final_mode=final_mode,
            decision=decision,
            final_payload=final_payload,
        )

    return results


async def _crawl_via_rss(
    *,
    rss_url: str,
    site: str,
    queries: list[str],
    task_id: str | int | None,
) -> list[dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(rss_url)
            resp.raise_for_status()
    except Exception:
        return []

    try:
        root = ElementTree.fromstring(resp.text)
    except ElementTree.ParseError:
        return []

    items = root.findall(".//item") or root.findall(".//entry")
    query_terms = _tokenize(" ".join(queries))
    results: list[dict[str, Any]] = []
    for item in items[:10]:
        title = _xml_text(item, "title")
        link = _xml_text(item, "link")
        summary = _xml_text(item, "description") or _xml_text(item, "summary") or _xml_text(item, "content")
        text_blob = f"{title}\n{summary}"
        if query_terms and _overlap_ratio(query_terms, _tokenize(text_blob)) <= 0:
            continue
        results.append(
            {
                "title": title or site,
                "url": link or site,
                "content": _normalize_whitespace(summary)[:3000],
                "source": _domain_from_url(link or site),
                "kind": "rss",
                "search_mode": "crawl",
                "crawl_decision": {
                    "initial_mode": "rss",
                    "final_mode": "rss",
                    "score": 0.0,
                    "matched_rules": ["rss_configured"],
                    "extractor": "rss",
                    "fallback_to_dynamic": False,
                    "reason": "configured_rss",
                },
            }
        )
    if task_id and results:
        redis = await get_redis()
        await append_log(
            redis,
            int(task_id),
            "searcher",
            f"RSS 抓取命中：{rss_url}",
            interaction_type="tool_result",
            status="running",
            payload={"rss_url": rss_url, "result_count": len(results)},
        )
    return results


async def _crawl_static(site: str, cfg: dict[str, Any]) -> CrawlPayload:
    crawler_cfg = cfg.get("http_crawler", {})
    headers = dict(crawler_cfg.get("headers") or {})
    headers["User-Agent"] = str(crawler_cfg.get("user_agent") or settings.CRAWLER_USER_AGENT)
    timeout = int(crawler_cfg.get("timeout_seconds") or 30)
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=bool(crawler_cfg.get("follow_redirects", True)),
        verify=bool(crawler_cfg.get("verify_ssl", True)),
        headers=headers,
    ) as client:
        try:
            resp = await client.get(site)
            resp.raise_for_status()
            html = resp.text
        except Exception as exc:
            return CrawlPayload(
                title=site,
                url=site,
                html="",
                content="",
                extractor="http_error",
                status="failed",
                error={"type": type(exc).__name__, "message": str(exc)},
            )
    title, content, extractor = _extract_static_content(html)
    return CrawlPayload(title=title or site, url=site, html=html, content=content, extractor=extractor)


async def _crawl_dynamic(site: str, cfg: dict[str, Any]) -> CrawlPayload:
    crawler_cfg = cfg.get("dynamic_crawler", {})
    wait_until = str(crawler_cfg.get("wait_until") or "networkidle")
    timeout_ms = int(crawler_cfg.get("timeout_seconds") or 60) * 1000
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=bool(crawler_cfg.get("headless", settings.PLAYWRIGHT_HEADLESS)))
        page = await browser.new_page()
        try:
            await page.goto(site, timeout=timeout_ms, wait_until=wait_until)
            html = await page.content()
            title, content, extractor = _extract_static_content(html)
            return CrawlPayload(title=title or site, url=site, html=html, content=content, extractor=f"dynamic:{extractor}")
        except Exception as exc:
            return CrawlPayload(
                title=site,
                url=site,
                html="",
                content="",
                extractor="dynamic_error",
                status="failed",
                error={"type": type(exc).__name__, "message": str(exc)},
            )
        finally:
            await browser.close()


def _extract_static_content(html: str) -> tuple[str, str, str]:
    if not html:
        return "", "", "empty"
    title = ""
    try:
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
    except Exception:
        soup = None
    parser_order = [_try_trafilatura, _try_readability, _bs4_extract]
    for parser in parser_order:
        content = parser(html)
        if content:
            return title, _normalize_whitespace(content), parser.__name__.replace("_try_", "").replace("_", "")
    if soup is not None:
        return title, _normalize_whitespace(soup.get_text(separator="\n", strip=True)), "bs4"
    return title, "", "fallback"


def _evaluate_dynamic_need(
    *,
    html: str,
    extracted_text: str,
    domain: str,
    profile: dict[str, Any],
    cfg: dict[str, Any],
    forced_mode: str = "auto",
) -> dict[str, Any]:
    decision_cfg = cfg.get("decision", {})
    if domain in set(decision_cfg.get("force_dynamic_domains") or []):
        return _decision(domain, 100.0, ["force_dynamic_domain"], True, "force_dynamic_domain")
    if domain in set(decision_cfg.get("force_static_domains") or []) or forced_mode == "static":
        return _decision(domain, 0.0, ["force_static_domain"], False, "force_static_domain")
    if forced_mode == "dynamic":
        return _decision(domain, 100.0, ["forced_dynamic_mode"], True, "forced_dynamic_mode")

    weights = decision_cfg.get("score_weights", {})
    matched_rules: list[str] = []
    html_lower = html.lower()
    text = extracted_text or ""
    score = 0.0

    if not text.strip():
        score += float(weights.get("empty_content", 35))
        matched_rules.append("empty_content")
    if len(text) < int(decision_cfg.get("static_min_text_length", 300)):
        score += float(weights.get("short_content", 20))
        matched_rules.append("short_content")
    if len(html.encode("utf-8")) < int(decision_cfg.get("static_min_html_bytes", 8192)):
        score += float(weights.get("short_html", 15))
        matched_rules.append("short_html")
    for marker in decision_cfg.get("spa_markers", []):
        if marker.lower() in html_lower:
            score += float(weights.get("spa_marker", 30))
            matched_rules.append("spa_marker")
            break
    if any(keyword in html_lower for keyword in ("please enable javascript", "enable javascript", "javascript required")):
        score += float(weights.get("noscript_js_hint", 25))
        matched_rules.append("noscript_js_hint")
    if html_lower.count("<script") >= 8 and len(text) < int(decision_cfg.get("static_min_text_length", 300)):
        score += float(weights.get("script_heavy_shell", 20))
        matched_rules.append("script_heavy_shell")
    if _link_density(html, text) > float(decision_cfg.get("static_max_link_density", 0.35)):
        score += float(weights.get("high_link_density", 15))
        matched_rules.append("high_link_density")
    if any(keyword in html_lower for keyword in decision_cfg.get("error_keywords", [])):
        score += float(weights.get("anti_bot_keyword", 25))
        matched_rules.append("anti_bot_keyword")

    static_attempts = int(profile.get("static_attempts") or 0)
    static_successes = int(profile.get("static_successes") or 0)
    dynamic_attempts = int(profile.get("dynamic_attempts") or 0)
    dynamic_successes = int(profile.get("dynamic_successes") or 0)
    if static_attempts >= 3 and static_successes / max(1, static_attempts) < 0.3:
        score += float(weights.get("historical_static_failure", 25))
        matched_rules.append("historical_static_failure")
    if dynamic_attempts >= 3 and dynamic_successes / max(1, dynamic_attempts) >= 0.8:
        score += float(weights.get("historical_dynamic_success", 20))
        matched_rules.append("historical_dynamic_success")

    threshold = float(decision_cfg.get("dynamic_threshold", 60))
    should_use_dynamic = score >= threshold
    reason = "score_above_dynamic_threshold" if should_use_dynamic else "static_result_accepted"
    return _decision(domain, score, matched_rules, should_use_dynamic, reason)


def _decision(domain: str, score: float, matched_rules: list[str], should_use_dynamic: bool, reason: str) -> dict[str, Any]:
    return {
        "domain": domain,
        "initial_mode": "static",
        "score": round(score, 2),
        "matched_rules": matched_rules,
        "fallback_to_dynamic": should_use_dynamic,
        "should_use_dynamic": should_use_dynamic,
        "reason": reason,
    }


def _prefer_dynamic(static_payload: CrawlPayload, dynamic_payload: CrawlPayload) -> bool:
    if dynamic_payload.status != "succeeded" or not dynamic_payload.content.strip():
        return False
    if static_payload.status != "succeeded" or not static_payload.content.strip():
        return True
    return len(dynamic_payload.content) >= len(static_payload.content) * 1.1


def _build_crawl_result(
    *,
    site: str,
    domain: str,
    payload: CrawlPayload,
    decision: dict[str, Any],
    final_mode: str,
    queries: list[str],
) -> dict[str, Any]:
    return {
        "title": payload.title or site,
        "url": payload.url,
        "content": payload.content[:3000],
        "source": domain,
        "kind": "crawler",
        "search_mode": "crawl",
        "matched_queries": [query for query in queries if _query_matches_content(query, payload.content, payload.title)],
        "crawl_decision": {
            **decision,
            "final_mode": final_mode,
            "extractor": payload.extractor,
        },
        **({"error": payload.error} if payload.error else {}),
    }


async def _append_crawl_decision(redis: Redis, task_id: int, decision: dict[str, Any]) -> None:
    key = f"task:{task_id}:crawl_decisions"
    raw = await redis.get(key)
    items = json.loads(raw) if raw else []
    items.append(decision)
    ttl = await redis.ttl(f"task:{task_id}:context")
    await redis.setex(key, max(ttl, 60), json.dumps(items, ensure_ascii=False))


async def _load_site_profile(redis: Redis, domain: str, capability: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    ttl = int((cfg.get("decision") or {}).get("cache_ttl_seconds", 1800))
    cache_key = f"site_profile:{domain}"
    raw = await redis.get(cache_key)
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

    async with AsyncSessionLocal() as db:
        row = await db.scalar(select(SiteCrawlProfile).where(SiteCrawlProfile.domain == domain))
        if row:
            payload = _profile_to_dict(row)
        else:
            payload = {
                "domain": domain,
                "preferred_mode": "rss" if capability.get("rss_url") else "static",
                "api_available": bool(capability.get("api_tool")),
                "rss_available": bool(capability.get("rss_url")),
                "static_attempts": 0,
                "static_successes": 0,
                "dynamic_attempts": 0,
                "dynamic_successes": 0,
                "avg_static_content_length": 0.0,
                "avg_dynamic_content_length": 0.0,
                "avg_static_score": 0.0,
                "avg_dynamic_score": 0.0,
                "last_mode": None,
                "last_reason": None,
                "js_required_score": 0.0,
                "feature_flags": {},
            }
    await redis.setex(cache_key, ttl, json.dumps(payload, ensure_ascii=False))
    return payload


async def _update_site_profile(
    *,
    redis: Redis,
    domain: str,
    capability: dict[str, Any],
    final_mode: str,
    decision: dict[str, Any],
    final_payload: CrawlPayload,
) -> None:
    profile = await _load_site_profile(redis, domain, capability, _crawler_runtime())
    score = float(decision.get("score") or 0.0)
    content_length = len(final_payload.content or "")

    profile["api_available"] = bool(capability.get("api_tool"))
    profile["rss_available"] = bool(capability.get("rss_url"))
    profile["last_mode"] = final_mode
    profile["last_reason"] = decision.get("reason")
    profile["feature_flags"] = {
        **(profile.get("feature_flags") or {}),
        "last_matched_rules": decision.get("matched_rules") or [],
        "last_extractor": final_payload.extractor,
    }
    profile["preferred_mode"] = _preferred_mode(profile, final_mode, content_length)
    profile["js_required_score"] = _moving_average(
        float(profile.get("js_required_score") or 0.0),
        100.0 if final_mode == "dynamic" else score,
        count=max(int(profile.get("dynamic_attempts") or 0) + int(profile.get("static_attempts") or 0), 1),
    )

    if final_mode == "dynamic":
        profile["dynamic_attempts"] = int(profile.get("dynamic_attempts") or 0) + 1
        if final_payload.status == "succeeded" and content_length > 0:
            profile["dynamic_successes"] = int(profile.get("dynamic_successes") or 0) + 1
        profile["avg_dynamic_content_length"] = _moving_average(
            float(profile.get("avg_dynamic_content_length") or 0.0),
            float(content_length),
            int(profile["dynamic_attempts"]),
        )
        profile["avg_dynamic_score"] = _moving_average(
            float(profile.get("avg_dynamic_score") or 0.0),
            score,
            int(profile["dynamic_attempts"]),
        )
    elif final_mode == "static":
        profile["static_attempts"] = int(profile.get("static_attempts") or 0) + 1
        if final_payload.status == "succeeded" and content_length > 0:
            profile["static_successes"] = int(profile.get("static_successes") or 0) + 1
        profile["avg_static_content_length"] = _moving_average(
            float(profile.get("avg_static_content_length") or 0.0),
            float(content_length),
            int(profile["static_attempts"]),
        )
        profile["avg_static_score"] = _moving_average(
            float(profile.get("avg_static_score") or 0.0),
            score,
            int(profile["static_attempts"]),
        )

    async with AsyncSessionLocal() as db:
        row = await db.scalar(select(SiteCrawlProfile).where(SiteCrawlProfile.domain == domain))
        if row is None:
            row = SiteCrawlProfile(domain=domain)
            db.add(row)
        row.preferred_mode = str(profile["preferred_mode"])
        row.api_available = bool(profile["api_available"])
        row.rss_available = bool(profile["rss_available"])
        row.static_attempts = int(profile["static_attempts"])
        row.static_successes = int(profile["static_successes"])
        row.dynamic_attempts = int(profile["dynamic_attempts"])
        row.dynamic_successes = int(profile["dynamic_successes"])
        row.avg_static_content_length = float(profile["avg_static_content_length"])
        row.avg_dynamic_content_length = float(profile["avg_dynamic_content_length"])
        row.avg_static_score = float(profile["avg_static_score"])
        row.avg_dynamic_score = float(profile["avg_dynamic_score"])
        row.last_mode = profile["last_mode"]
        row.last_reason = profile["last_reason"]
        row.js_required_score = float(profile["js_required_score"])
        row.feature_flags = dict(profile.get("feature_flags") or {})
        await db.commit()

    ttl = int((_crawler_runtime().get("decision") or {}).get("cache_ttl_seconds", 1800))
    await redis.setex(f"site_profile:{domain}", ttl, json.dumps(profile, ensure_ascii=False))


def _preferred_mode(profile: dict[str, Any], final_mode: str, content_length: int) -> str:
    if profile.get("api_available"):
        return "api"
    if profile.get("rss_available"):
        return "rss"
    if final_mode == "dynamic":
        return "dynamic"
    if int(profile.get("static_attempts") or 0) >= 3:
        success_rate = int(profile.get("static_successes") or 0) / max(1, int(profile.get("static_attempts") or 0))
        if success_rate >= 0.7 and content_length >= 300:
            return "static"
    return final_mode


def _profile_to_dict(row: SiteCrawlProfile) -> dict[str, Any]:
    return {
        "domain": row.domain,
        "preferred_mode": row.preferred_mode,
        "api_available": row.api_available,
        "rss_available": row.rss_available,
        "static_attempts": row.static_attempts,
        "static_successes": row.static_successes,
        "dynamic_attempts": row.dynamic_attempts,
        "dynamic_successes": row.dynamic_successes,
        "avg_static_content_length": row.avg_static_content_length,
        "avg_dynamic_content_length": row.avg_dynamic_content_length,
        "avg_static_score": row.avg_static_score,
        "avg_dynamic_score": row.avg_dynamic_score,
        "last_mode": row.last_mode,
        "last_reason": row.last_reason,
        "js_required_score": row.js_required_score,
        "feature_flags": row.feature_flags or {},
    }


def _moving_average(current: float, new_value: float, count: int) -> float:
    if count <= 1:
        return round(new_value, 2)
    return round(((current * (count - 1)) + new_value) / count, 2)


def _link_density(html: str, text: str) -> float:
    if not html or not text:
        return 1.0 if html else 0.0
    link_count = html.lower().count("<a ")
    return link_count / max(1.0, len(text.split()))


def _query_matches_content(query: str, content: str, title: str) -> bool:
    query_terms = _tokenize(query)
    return _overlap_ratio(query_terms, _tokenize(f"{title} {content}")) > 0


def _overlap_ratio(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, len(left))


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[\w\u4e00-\u9fff]+", (text or "").lower()))


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text or "")).strip()


def _xml_text(item: ElementTree.Element, tag_name: str) -> str:
    node = item.find(tag_name)
    if node is not None and node.text:
        return node.text.strip()
    for child in item:
        if child.tag.endswith(tag_name) and child.text:
            return child.text.strip()
        if tag_name == "link" and child.tag.endswith("link"):
            href = child.attrib.get("href")
            if href:
                return href.strip()
    return ""


def _try_trafilatura(html: str) -> str | None:
    try:
        import trafilatura  # type: ignore

        return trafilatura.extract(html)
    except Exception:
        return None


def _try_readability(html: str) -> str | None:
    try:
        from readability import Document  # type: ignore

        doc = Document(html)
        soup = BeautifulSoup(doc.summary(), "html.parser")
        return soup.get_text(separator="\n", strip=True)
    except Exception:
        return None


def _bs4_extract(html: str) -> str | None:
    try:
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(separator="\n", strip=True)
    except Exception:
        return None


def _crawler_runtime() -> dict[str, Any]:
    if not TOOL_MCP_CONFIG_PATH.exists():
        return {}
    with TOOL_MCP_CONFIG_PATH.open("r", encoding="utf-8") as f:
        return ((yaml.safe_load(f) or {}).get("tool_mcp") or {}).get("crawler", {})


def _source_capability(domain: str, cfg: dict[str, Any]) -> dict[str, Any]:
    caps = cfg.get("source_capabilities") or {}
    return caps.get(domain, caps.get("default", {}))


async def _tavily_search(query: str, site_filter: list[str] | None) -> list[dict]:
    from tavily import AsyncTavilyClient

    client = AsyncTavilyClient(api_key=settings.TAVILY_API_KEY)
    params = {"query": query, "max_results": 10, "search_depth": "advanced"}
    if site_filter:
        params["include_domains"] = site_filter

    resp = await client.search(**params)
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
            "source": _domain_from_url(r.get("url", "")),
            "kind": "search_api",
            "search_mode": "api",
        }
        for r in resp.get("results", [])
    ]


async def _serpapi_search(query: str, site_filter: list[str] | None) -> list[dict]:
    q = query
    if site_filter:
        q += " site:" + " OR site:".join(site_filter)

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://serpapi.com/search",
            params={"q": q, "api_key": settings.SERPAPI_KEY, "num": 10},
        )
        resp.raise_for_status()
        data = resp.json()

    return [
        {
            "title": r.get("title", ""),
            "url": r.get("link", ""),
            "content": r.get("snippet", ""),
            "source": _domain_from_url(r.get("link", "")),
            "kind": "search_api",
            "search_mode": "api",
        }
        for r in data.get("organic_results", [])
    ]


async def _bing_search(query: str, site_filter: list[str] | None) -> list[dict]:
    q = query
    if site_filter:
        q += " site:" + " OR site:".join(site_filter)

    headers = {"Ocp-Apim-Subscription-Key": settings.BING_SEARCH_API_KEY}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://api.bing.microsoft.com/v7.0/search",
            params={"q": q, "count": 10},
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()

    return [
        {
            "title": r.get("name", ""),
            "url": r.get("url", ""),
            "content": r.get("snippet", ""),
            "source": _domain_from_url(r.get("url", "")),
            "kind": "search_api",
            "search_mode": "api",
        }
        for r in data.get("webPages", {}).get("value", [])
    ]


def _domain_from_url(url: str) -> str:
    parsed = urlparse(url or "")
    return (parsed.netloc or url).lower()
