from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import socket
import sqlite3
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser
import zipfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


APP_NAME = "运去哪·小红书市场情报助手"
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
OUTPUT_DIR = BASE_DIR / "outputs"
CONFIG_PATH = DATA_DIR / "config.json"
DB_PATH = DATA_DIR / "state.db"
DEFAULT_API_BASE = "https://api.tikhub.io"
DEFAULT_TEST_MAX_CALLS = 30
DEFAULT_MAX_COST = 0.05


ENDPOINTS: dict[str, dict[str, Any]] = {
    "get_image_note_detail": {
        "name": "图文笔记详情",
        "path": "/api/v1/xiaohongshu/app_v2/get_image_note_detail",
        "unit_price": 0.01,
    },
    "get_video_note_detail": {
        "name": "视频笔记详情",
        "path": "/api/v1/xiaohongshu/app_v2/get_video_note_detail",
        "unit_price": 0.01,
    },
    "get_note_comments": {
        "name": "笔记评论",
        "path": "/api/v1/xiaohongshu/app_v2/get_note_comments",
        "unit_price": 0.01,
    },
    "get_note_sub_comments": {
        "name": "二级评论",
        "path": "/api/v1/xiaohongshu/app_v2/get_note_sub_comments",
        "unit_price": 0.01,
    },
    "get_user_info": {
        "name": "用户信息",
        "path": "/api/v1/xiaohongshu/app_v2/get_user_info",
        "unit_price": 0.01,
    },
    "get_user_posted_notes": {
        "name": "用户发布笔记",
        "path": "/api/v1/xiaohongshu/app_v2/get_user_posted_notes",
        "unit_price": 0.01,
    },
    "get_user_faved_notes": {
        "name": "用户收藏笔记",
        "path": "/api/v1/xiaohongshu/app_v2/get_user_faved_notes",
        "unit_price": 0.01,
    },
    "get_topic_info": {
        "name": "话题详情",
        "path": "/api/v1/xiaohongshu/app_v2/get_topic_info",
        "unit_price": 0.01,
    },
    "get_topic_feed": {
        "name": "话题笔记",
        "path": "/api/v1/xiaohongshu/app_v2/get_topic_feed",
        "unit_price": 0.01,
    },
    "search_notes": {
        "name": "搜索笔记",
        "path": "/api/v1/xiaohongshu/app_v2/search_notes",
        "unit_price": 0.01,
    },
    "search_users": {
        "name": "搜索用户",
        "path": "/api/v1/xiaohongshu/app_v2/search_users",
        "unit_price": 0.01,
    },
    "search_images": {
        "name": "搜索图片",
        "path": "/api/v1/xiaohongshu/app_v2/search_images",
        "unit_price": 0.01,
    },
    "search_products": {
        "name": "搜索商品",
        "path": "/api/v1/xiaohongshu/app_v2/search_products",
        "unit_price": 0.01,
    },
    "search_groups": {
        "name": "搜索群聊",
        "path": "/api/v1/xiaohongshu/app_v2/search_groups",
        "unit_price": 0.01,
    },
    "get_product_detail": {
        "name": "商品详情",
        "path": "/api/v1/xiaohongshu/app_v2/get_product_detail",
        "unit_price": 0.01,
    },
    "get_product_review_overview": {
        "name": "商品评论总览",
        "path": "/api/v1/xiaohongshu/app_v2/get_product_review_overview",
        "unit_price": 0.01,
    },
    "get_product_reviews": {
        "name": "商品评论列表",
        "path": "/api/v1/xiaohongshu/app_v2/get_product_reviews",
        "unit_price": 0.01,
    },
    "get_product_recommendations": {
        "name": "商品推荐",
        "path": "/api/v1/xiaohongshu/app_v2/get_product_recommendations",
        "unit_price": 0.01,
    },
    "get_creator_inspiration_feed": {
        "name": "创作者推荐灵感",
        "path": "/api/v1/xiaohongshu/app_v2/get_creator_inspiration_feed",
        "unit_price": 0.01,
    },
    "get_creator_hot_inspiration_feed": {
        "name": "创作者热点灵感",
        "path": "/api/v1/xiaohongshu/app_v2/get_creator_hot_inspiration_feed",
        "unit_price": 0.01,
    },
}

TASKS: dict[str, dict[str, Any]] = {
    "material": {
        "name": "市场素材搜索",
        "description": "先搜笔记，再查少量笔记详情。",
    },
    "competitor": {
        "name": "竞品账号研究",
        "description": "搜索账号，再看账号资料和作品。",
    },
    "comments": {
        "name": "评论需求分析",
        "description": "先找相关笔记，再抓评论看需求。",
    },
    "topic": {
        "name": "话题趋势研究",
        "description": "先找话题线索，再看话题热度。",
    },
    "product": {
        "name": "商品与用户痛点研究",
        "description": "搜索商品，再看商品详情和评价。",
    },
    "images": {
        "name": "图片补充搜索",
        "description": "按关键词找图片素材。",
    },
    "groups": {
        "name": "群聊搜索",
        "description": "按关键词找相关群聊。",
    },
}

SHEETS: dict[str, list[str]] = {
    "笔记素材": [
        "任务",
        "关键词",
        "笔记ID",
        "类型",
        "标题",
        "正文摘要",
        "作者昵称",
        "作者ID",
        "点赞",
        "收藏",
        "评论",
        "分享链接",
        "图片或封面",
        "发布时间",
        "数据来源",
    ],
    "评论需求": [
        "任务",
        "关键词",
        "笔记ID",
        "评论ID",
        "评论内容",
        "评论用户",
        "点赞",
        "是否二级评论",
        "需求判断",
        "数据来源",
    ],
    "竞品账号": [
        "任务",
        "关键词",
        "用户ID",
        "昵称",
        "简介",
        "粉丝",
        "关注",
        "作品数",
        "主页链接",
        "数据来源",
    ],
    "账号作品": [
        "任务",
        "关键词",
        "用户ID",
        "昵称",
        "笔记ID",
        "标题",
        "类型",
        "点赞",
        "收藏",
        "评论",
        "发布时间",
        "数据来源",
    ],
    "话题趋势": [
        "任务",
        "关键词",
        "话题ID",
        "话题名",
        "浏览量",
        "讨论数",
        "关联笔记ID",
        "标题",
        "热度说明",
        "数据来源",
    ],
    "商品研究": [
        "任务",
        "关键词",
        "商品ID/SKU",
        "商品名",
        "价格",
        "店铺",
        "评分或好评",
        "评论摘要",
        "痛点判断",
        "数据来源",
    ],
    "图片结果": [
        "任务",
        "关键词",
        "图片ID",
        "图片链接",
        "来源笔记ID",
        "标题",
        "作者",
        "数据来源",
    ],
    "群聊结果": [
        "任务",
        "关键词",
        "群聊ID",
        "群聊名称",
        "简介",
        "人数或热度",
        "入口信息",
        "数据来源",
    ],
    "API调用与费用记录": [
        "时间",
        "运行ID",
        "接口",
        "中文名",
        "参数",
        "状态",
        "是否缓存",
        "本次计费",
        "说明",
    ],
}


class BudgetExceeded(Exception):
    pass


class Budget:
    def __init__(self, max_calls: int, max_cost: float, prices: dict[str, float]):
        self.max_calls = max_calls
        self.max_cost = max_cost
        self.prices = prices
        self.paid_calls = 0
        self.spent = 0.0

    def check(self, endpoint_key: str) -> float:
        price = float(self.prices.get(endpoint_key, ENDPOINTS[endpoint_key]["unit_price"]))
        if self.paid_calls + 1 > self.max_calls:
            raise BudgetExceeded(f"已达到本次最大调用次数 {self.max_calls}，自动停止。")
        if self.spent + price > self.max_cost + 1e-9:
            raise BudgetExceeded(f"预计超过本次最高费用 ${self.max_cost:.2f}，自动停止。")
        return price

    def register_paid_call(self, price: float) -> None:
        self.paid_calls += 1
        self.spent = round(self.spent + price, 6)


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    ensure_dirs()
    with db_connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS api_cache (
                cache_key TEXT PRIMARY KEY,
                endpoint_key TEXT NOT NULL,
                endpoint_path TEXT NOT NULL,
                params_json TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS api_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                endpoint_key TEXT NOT NULL,
                endpoint_path TEXT NOT NULL,
                params_json TEXT NOT NULL,
                status TEXT NOT NULL,
                from_cache INTEGER NOT NULL,
                cost REAL NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {"api_key": "", "api_base": DEFAULT_API_BASE}
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"api_key": "", "api_base": DEFAULT_API_BASE}
    return {
        "api_key": "",
        "api_base": data.get("api_base", DEFAULT_API_BASE) or DEFAULT_API_BASE,
    }


def save_config(api_key: str, api_base: str) -> None:
    ensure_dirs()
    CONFIG_PATH.write_text(
        json.dumps(
            {
                "api_key": "",
                "api_base": api_base.strip() or DEFAULT_API_BASE,
                "saved_at": now_text(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def api_key_preview(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return api_key[:4] + "*" * max(4, len(api_key) - 8) + api_key[-4:]


def endpoint_price_map(api_base: str) -> tuple[dict[str, float], str]:
    prices = {key: float(item["unit_price"]) for key, item in ENDPOINTS.items()}
    url = api_base.rstrip("/") + "/api/v1/tikhub/user/get_all_endpoints_info"
    try:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "YQN-XHS-Intel/0.1",
            },
        )
        with urlopen_with_system_certs(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        rows = payload.get("data", [])
        by_path = {item["path"]: key for key, item in ENDPOINTS.items()}
        for row in rows:
            path = row.get("endpoint_uri")
            if path in by_path:
                prices[by_path[path]] = float(row.get("endpoint_cost", prices[by_path[path]]))
        return prices, "已从 TikHub 实时查到单价"
    except Exception as exc:  # noqa: BLE001
        return prices, f"实时查价失败，暂用本地保守单价：{exc}"


def check_tikhub_connection(api_key: str, api_base: str) -> dict[str, Any]:
    api_key = api_key.strip()
    if not api_key:
        return {"ok": False, "message": "还没有填写 API Key。"}
    url = api_base.rstrip("/") + "/api/v1/tikhub/user/get_user_info"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "YQN-XHS-Intel/0.1",
        },
    )
    try:
        with urlopen_with_system_certs(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if payload.get("code") == 200:
            return {
                "ok": True,
                "message": "连接成功：这个 API Key 可以访问 TikHub。",
                "data": payload.get("data", {}),
            }
        return {
            "ok": False,
            "message": payload.get("message_zh") or payload.get("message") or "TikHub 返回了异常，请检查 API Key。",
            "data": payload,
        }
    except urllib.error.HTTPError as exc:
        try:
            err_body = exc.read().decode("utf-8")
            err_payload = json.loads(err_body)
            message = err_payload.get("detail", {}).get("message_zh") or err_payload.get("message_zh") or err_payload.get("message")
        except Exception:  # noqa: BLE001
            message = str(exc)
        return {"ok": False, "message": message or f"连接失败：HTTP {exc.code}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "message": f"连接失败：{exc}"}


def urlopen_with_system_certs(req: urllib.request.Request, timeout: int):
    contexts: list[ssl.SSLContext | None] = [None]
    for cert_path in [
        os.environ.get("SSL_CERT_FILE", ""),
        "/etc/ssl/cert.pem",
        "/opt/homebrew/etc/ca-certificates/cert.pem",
    ]:
        if cert_path and Path(cert_path).exists():
            try:
                contexts.append(ssl.create_default_context(cafile=cert_path))
            except Exception:
                continue

    last_error: Exception | None = None
    for context in contexts:
        try:
            return urllib.request.urlopen(req, timeout=timeout, context=context)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    if last_error:
        raise last_error
    raise RuntimeError("无法发起网络请求")


def safe_int(value: Any, default: int, minimum: int = 1, maximum: int = 1000) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def safe_float(value: Any, default: float, minimum: float = 0.0, maximum: float = 100000.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def estimate_task(payload: dict[str, Any]) -> dict[str, Any]:
    config = load_config()
    api_base = payload.get("apiBase") or config.get("api_base") or DEFAULT_API_BASE
    prices, price_message = endpoint_price_map(api_base)
    task = payload.get("task") or "material"
    quantity = safe_int(payload.get("quantity"), 3, 1, 500)
    test_mode = bool(payload.get("testMode", True))
    user_max_calls = safe_int(payload.get("maxCalls"), DEFAULT_TEST_MAX_CALLS, 1, 100000)
    max_calls = min(user_max_calls, DEFAULT_TEST_MAX_CALLS) if test_mode else user_max_calls
    max_cost = safe_float(payload.get("maxCost"), DEFAULT_MAX_COST, 0.0, 100000)
    counts = plan_endpoint_counts(task, quantity)
    planned_calls = sum(counts.values())
    planned_cost = round(sum(prices.get(key, 0.01) * count for key, count in counts.items()), 6)
    limited_by = []
    if planned_calls > max_calls:
        limited_by.append(f"预计调用 {planned_calls} 次，超过上限 {max_calls} 次，运行时会到上限停止")
    if planned_cost > max_cost:
        limited_by.append(f"预计费用 ${planned_cost:.2f}，超过上限 ${max_cost:.2f}，运行时会到上限停止")

    steps = [
        {
            "endpointKey": key,
            "endpoint": ENDPOINTS[key]["path"],
            "name": ENDPOINTS[key]["name"],
            "count": count,
            "unitPrice": prices.get(key, 0.01),
            "cost": round(prices.get(key, 0.01) * count, 6),
        }
        for key, count in counts.items()
    ]
    return {
        "task": task,
        "taskName": TASKS.get(task, TASKS["material"])["name"],
        "quantity": quantity,
        "plannedCalls": planned_calls,
        "plannedCost": planned_cost,
        "maxCalls": max_calls,
        "maxCost": max_cost,
        "testMode": test_mode,
        "limitedBy": limited_by,
        "steps": steps,
        "prices": prices,
        "priceMessage": price_message,
        "hasApiKey": bool(str(payload.get("apiKey") or "").strip()),
        "apiKeyPreview": api_key_preview(str(payload.get("apiKey") or "").strip()),
        "apiBase": api_base,
    }


def plan_endpoint_counts(task: str, quantity: int) -> dict[str, int]:
    pages = max(1, (quantity + 19) // 20)
    if task == "competitor":
        return {
            "search_users": pages,
            "get_user_info": quantity,
            "get_user_posted_notes": quantity,
        }
    if task == "comments":
        note_count = min(quantity, 10)
        return {
            "search_notes": pages,
            "get_note_comments": note_count,
        }
    if task == "topic":
        return {
            "search_notes": pages,
            "get_topic_info": min(quantity, 3),
            "get_topic_feed": min(quantity, 3),
        }
    if task == "product":
        product_count = min(quantity, 10)
        return {
            "search_products": pages,
            "get_product_detail": product_count,
            "get_product_review_overview": product_count,
            "get_product_reviews": product_count,
        }
    if task == "images":
        return {"search_images": pages}
    if task == "groups":
        return {"search_groups": max(1, (quantity + 19) // 20)}
    return {
        "search_notes": pages,
        "get_image_note_detail": quantity,
    }


def cache_key(endpoint_key: str, params: dict[str, Any]) -> str:
    raw = endpoint_key + "::" + json.dumps(params, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_cached(endpoint_key: str, params: dict[str, Any]) -> Any | None:
    key = cache_key(endpoint_key, params)
    with db_connect() as conn:
        row = conn.execute("SELECT response_json FROM api_cache WHERE cache_key = ?", (key,)).fetchone()
    if row:
        return json.loads(row["response_json"])
    return None


def put_cached(endpoint_key: str, params: dict[str, Any], response: Any) -> None:
    endpoint_path = ENDPOINTS[endpoint_key]["path"]
    key = cache_key(endpoint_key, params)
    with db_connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO api_cache
            (cache_key, endpoint_key, endpoint_path, params_json, response_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                endpoint_key,
                endpoint_path,
                json.dumps(params, ensure_ascii=False, sort_keys=True),
                json.dumps(response, ensure_ascii=False),
                now_text(),
            ),
        )


def record_call(
    run_id: str,
    endpoint_key: str,
    params: dict[str, Any],
    status: str,
    from_cache: bool,
    cost: float,
    message: str,
) -> None:
    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO api_calls
            (run_id, endpoint_key, endpoint_path, params_json, status, from_cache, cost, message, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                endpoint_key,
                ENDPOINTS[endpoint_key]["path"],
                json.dumps(params, ensure_ascii=False, sort_keys=True),
                status,
                1 if from_cache else 0,
                float(cost),
                message,
                now_text(),
            ),
        )


def save_raw(run_id: str, endpoint_key: str, params: dict[str, Any], payload: Any) -> None:
    folder = RAW_DIR / run_id
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H%M%S_%f")
    safe_name = re.sub(r"[^a-zA-Z0-9_]+", "_", endpoint_key)
    path = folder / f"{stamp}_{safe_name}.json"
    path.write_text(
        json.dumps(
            {
                "endpoint": ENDPOINTS[endpoint_key]["path"],
                "params": params,
                "saved_at": now_text(),
                "response": payload,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def clean_params(params: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if value not in (None, "")}


def tikhub_get(
    endpoint_key: str,
    params: dict[str, Any],
    run_id: str,
    config: dict[str, Any],
    budget: Budget,
) -> Any:
    params = clean_params(params)
    cached = get_cached(endpoint_key, params)
    if cached is not None:
        record_call(run_id, endpoint_key, params, "成功", True, 0.0, "本地缓存命中，未重复付费调用")
        return cached

    api_key = config.get("api_key", "").strip()
    if not api_key:
        raise RuntimeError("未填写 API Key，无法正式调用 TikHub。")

    unit_price = budget.check(endpoint_key)
    base = (config.get("api_base") or DEFAULT_API_BASE).rstrip("/")
    query = urllib.parse.urlencode(params, doseq=True)
    url = base + ENDPOINTS[endpoint_key]["path"] + ("?" + query if query else "")
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "YQN-XHS-Intel/0.1",
    }
    last_error = ""
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urlopen_with_system_certs(req, timeout=35) as resp:
                body = resp.read().decode("utf-8")
            payload = json.loads(body)
            put_cached(endpoint_key, params, payload)
            save_raw(run_id, endpoint_key, params, payload)
            budget.register_paid_call(unit_price)
            record_call(run_id, endpoint_key, params, "成功", False, unit_price, f"第 {attempt} 次尝试成功")
            time.sleep(0.15)
            return payload
        except urllib.error.HTTPError as exc:
            try:
                err_body = exc.read().decode("utf-8")
            except Exception:  # noqa: BLE001
                err_body = str(exc)
            last_error = f"HTTP {exc.code}: {err_body[:300]}"
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
        time.sleep(0.7 * attempt)

    record_call(run_id, endpoint_key, params, "失败", False, 0.0, last_error)
    raise RuntimeError(last_error)


def walk_dicts(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        found.append(value)
        for child in value.values():
            found.extend(walk_dicts(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(walk_dicts(child))
    return found


def first_value(obj: dict[str, Any], keys: list[str], default: Any = "") -> Any:
    for key in keys:
        if key in obj and obj[key] not in (None, ""):
            return obj[key]
    return default


def path_value(obj: Any, path: list[str | int], default: Any = "") -> Any:
    current = obj
    for part in path:
        if isinstance(part, int):
            if not isinstance(current, list) or part >= len(current):
                return default
            current = current[part]
        else:
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]
        if current in (None, ""):
            return default
    return current


def deep_first_value(value: Any, keys: list[str], default: Any = "") -> Any:
    for item in walk_dicts(value):
        result = first_value(item, keys, None)
        if result not in (None, ""):
            return result
    return default


def note_public_url(note_id: Any, xsec_token: Any = "") -> str:
    note_id_text = str(note_id or "").strip()
    if not note_id_text:
        return ""
    url = f"https://www.xiaohongshu.com/explore/{note_id_text}"
    token_text = str(xsec_token or "").strip()
    if token_text:
        url += "?xsec_token=" + urllib.parse.quote(token_text)
    return url


def note_share_link(note: dict[str, Any], note_card: dict[str, Any]) -> str:
    candidates = [
        path_value(note, ["share_info", "link"]),
        path_value(note_card, ["share_info", "link"]),
        path_value(note, ["mini_program_info", "webpage_url"]),
        path_value(note_card, ["mini_program_info", "webpage_url"]),
        path_value(note, ["qq_mini_program_info", "webpage_url"]),
        path_value(note_card, ["qq_mini_program_info", "webpage_url"]),
        first_value(note, ["share_url", "shareUrl", "webpage_url"]),
        first_value(note_card, ["share_url", "shareUrl", "webpage_url"]),
    ]
    for value in candidates:
        text = str(value or "").strip()
        if text.startswith(("http://", "https://")) and "xiaohongshu.com" in text:
            return text
    note_id = first_value(note, ["note_id", "noteId", "id"]) or first_value(note_card, ["note_id", "noteId", "id"])
    xsec_token = first_value(note, ["xsec_token", "xsecToken"]) or first_value(note_card, ["xsec_token", "xsecToken"])
    return note_public_url(note_id, xsec_token)


def note_cover_image(note: dict[str, Any], note_card: dict[str, Any]) -> str:
    candidates = [
        first_value(note, ["cover", "image", "image_url"]),
        first_value(note_card, ["cover", "image", "image_url"]),
        path_value(note, ["cover", "url"]),
        path_value(note_card, ["cover", "url"]),
        path_value(note, ["images_list", 0, "url"]),
        path_value(note_card, ["images_list", 0, "url"]),
        path_value(note, ["images_list", 0, "url_size_large"]),
        path_value(note_card, ["images_list", 0, "url_size_large"]),
        path_value(note, ["share_info", "image"]),
        path_value(note_card, ["share_info", "image"]),
    ]
    for value in candidates:
        text = str(value or "").strip()
        if text.startswith(("http://", "https://")):
            return text
        if text:
            return text
    return ""


def compact_text(value: Any, limit: int = 240) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def unique_by(items: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for item in items:
        ident = first_value(item, keys, "")
        if not ident:
            ident = hashlib.sha1(json.dumps(item, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        if ident in seen:
            continue
        seen.add(ident)
        result.append(item)
    return result


def note_signal_score(item: dict[str, Any]) -> int:
    score = 0
    note_card = item.get("note_card")
    if isinstance(note_card, dict):
        score += 6
    if first_value(item, ["title", "display_title", "desc"]):
        score += 4
    if any(isinstance(item.get(key), dict) for key in ["share_info", "mini_program_info", "qq_mini_program_info"]):
        score += 4
    if any(key in item for key in ["images_list", "cover", "liked_count", "collected_count", "comments_count", "comment_count"]):
        score += 3
    if isinstance(item.get("user"), dict):
        score += 2
    if first_value(item, ["type", "note_type", "model_type", "xsec_token"]):
        score += 1
    return score


def extract_notes(payload: Any) -> list[dict[str, Any]]:
    candidates = []
    for item in walk_dicts(payload):
        note_id = first_value(item, ["note_id", "noteId", "id", "noteIdStr", "noteIdString"], "")
        if note_id and note_signal_score(item) >= 4:
            candidates.append(item)
    return unique_by(candidates, ["note_id", "noteId", "id"])[:200]


def extract_users(payload: Any) -> list[dict[str, Any]]:
    candidates = []
    for item in walk_dicts(payload):
        user_id = first_value(item, ["user_id", "userId", "id", "userid"], "")
        name = first_value(item, ["nickname", "nick_name", "name", "user_name"], "")
        if user_id and name:
            candidates.append(item)
    return unique_by(candidates, ["user_id", "userId", "id"])[:200]


def extract_products(payload: Any) -> list[dict[str, Any]]:
    candidates = []
    for item in walk_dicts(payload):
        sku_id = first_value(item, ["sku_id", "skuId", "id", "goods_id", "product_id"], "")
        title = first_value(item, ["title", "name", "goods_name", "product_name"], "")
        if sku_id and title:
            candidates.append(item)
    return unique_by(candidates, ["sku_id", "skuId", "id", "goods_id", "product_id"])[:200]


def extract_comments(payload: Any) -> list[dict[str, Any]]:
    candidates = []
    for item in walk_dicts(payload):
        comment_id = first_value(item, ["comment_id", "commentId", "id"], "")
        content = first_value(item, ["content", "text", "desc"], "")
        if comment_id and content:
            candidates.append(item)
    return unique_by(candidates, ["comment_id", "commentId", "id"])[:200]


def extract_images(payload: Any) -> list[dict[str, Any]]:
    candidates = []
    for item in walk_dicts(payload):
        url = first_value(item, ["url", "image_url", "imageUrl", "origin_url", "thumbnail"], "")
        if url and isinstance(url, str) and url.startswith(("http://", "https://")):
            candidates.append(item)
    return unique_by(candidates, ["url", "image_url", "imageUrl", "id"])[:200]


def extract_groups(payload: Any) -> list[dict[str, Any]]:
    candidates = []
    for item in walk_dicts(payload):
        group_id = first_value(item, ["group_id", "groupId", "chat_id", "id"], "")
        name = first_value(item, ["group_name", "name", "title"], "")
        if group_id and name:
            candidates.append(item)
    return unique_by(candidates, ["group_id", "groupId", "chat_id", "id"])[:200]


def note_row(task_name: str, keyword: str, note: dict[str, Any], source: str) -> dict[str, Any]:
    note_card = note.get("note_card") if isinstance(note.get("note_card"), dict) else {}
    user = note.get("user") if isinstance(note.get("user"), dict) else {}
    interact = note.get("interact_info") if isinstance(note.get("interact_info"), dict) else {}
    note_id = first_value(note, ["note_id", "noteId", "id"]) or first_value(note_card, ["note_id", "id"])
    title = first_value(note, ["title", "display_title"]) or first_value(note_card, ["title", "display_title"])
    desc = first_value(note, ["desc", "content", "text"]) or first_value(note_card, ["desc", "content"])
    note_type = first_value(note, ["type", "note_type", "model_type"]) or first_value(note_card, ["type", "note_type"])
    cover = note_cover_image(note, note_card)
    return {
        "任务": task_name,
        "关键词": keyword,
        "笔记ID": note_id,
        "类型": compact_text(note_type, 60),
        "标题": compact_text(title, 160),
        "正文摘要": compact_text(desc, 260),
        "作者昵称": compact_text(first_value(note, ["nickname", "nick_name"]) or first_value(user, ["nickname", "nick_name", "name"]), 80),
        "作者ID": first_value(note, ["user_id", "userId", "userid"]) or first_value(user, ["user_id", "userId", "userid", "id"]),
        "点赞": first_value(note, ["liked_count", "like_count", "likes"]) or first_value(interact, ["liked_count", "like_count"]),
        "收藏": first_value(note, ["collected_count", "collect_count"]) or first_value(interact, ["collected_count", "collect_count"]),
        "评论": first_value(note, ["comment_count", "comments_count"]) or first_value(interact, ["comment_count", "comments_count"]),
        "分享链接": note_share_link(note, note_card),
        "图片或封面": compact_text(cover, 220),
        "发布时间": first_value(note, ["time", "create_time", "created_at", "timestamp"]) or first_value(note_card, ["time", "create_time"]),
        "数据来源": source,
    }


def user_row(task_name: str, keyword: str, user: dict[str, Any], source: str) -> dict[str, Any]:
    return {
        "任务": task_name,
        "关键词": keyword,
        "用户ID": first_value(user, ["user_id", "userId", "userid", "id"]),
        "昵称": compact_text(first_value(user, ["nickname", "nick_name", "name", "user_name"]), 120),
        "简介": compact_text(first_value(user, ["desc", "description", "bio", "signature"]), 220),
        "粉丝": first_value(user, ["fans", "fans_count", "follower_count", "followers"]),
        "关注": first_value(user, ["follows", "following_count", "follow_count"]),
        "作品数": first_value(user, ["note_count", "notes", "post_count"]),
        "主页链接": first_value(user, ["share_url", "url", "link"]),
        "数据来源": source,
    }


def comment_row(task_name: str, keyword: str, note_id: str, comment: dict[str, Any], source: str, is_sub: bool = False) -> dict[str, Any]:
    user = comment.get("user") if isinstance(comment.get("user"), dict) else {}
    content = first_value(comment, ["content", "text", "desc"])
    return {
        "任务": task_name,
        "关键词": keyword,
        "笔记ID": note_id,
        "评论ID": first_value(comment, ["comment_id", "commentId", "id"]),
        "评论内容": compact_text(content, 320),
        "评论用户": compact_text(first_value(comment, ["nickname", "nick_name"]) or first_value(user, ["nickname", "nick_name", "name"]), 100),
        "点赞": first_value(comment, ["like_count", "liked_count", "likes"]),
        "是否二级评论": "是" if is_sub else "否",
        "需求判断": simple_need_label(content),
        "数据来源": source,
    }


def simple_need_label(text: Any) -> str:
    content = compact_text(text, 500)
    if any(word in content for word in ["多少钱", "价格", "费用", "报价", "贵"]):
        return "价格/报价需求"
    if any(word in content for word in ["多久", "时效", "几天", "延误"]):
        return "时效需求"
    if any(word in content for word in ["清关", "税", "海关", "查验"]):
        return "清关/合规痛点"
    if any(word in content for word in ["丢", "破", "赔", "售后"]):
        return "售后/风险痛点"
    if content:
        return "普通反馈"
    return ""


def product_row(task_name: str, keyword: str, product: dict[str, Any], source: str) -> dict[str, Any]:
    return {
        "任务": task_name,
        "关键词": keyword,
        "商品ID/SKU": first_value(product, ["sku_id", "skuId", "id", "goods_id", "product_id"]),
        "商品名": compact_text(first_value(product, ["title", "name", "goods_name", "product_name"]), 180),
        "价格": first_value(product, ["price", "sale_price", "min_price"]),
        "店铺": compact_text(first_value(product, ["shop_name", "seller_name", "brand_name"]), 120),
        "评分或好评": first_value(product, ["score", "rating", "positive_rate", "good_rate"]),
        "评论摘要": compact_text(first_value(product, ["review", "comment", "summary", "desc"]), 260),
        "痛点判断": simple_need_label(first_value(product, ["review", "comment", "summary", "desc"])),
        "数据来源": source,
    }


def image_row(task_name: str, keyword: str, item: dict[str, Any], source: str) -> dict[str, Any]:
    return {
        "任务": task_name,
        "关键词": keyword,
        "图片ID": first_value(item, ["id", "image_id", "imageId"]),
        "图片链接": compact_text(first_value(item, ["url", "image_url", "imageUrl", "origin_url", "thumbnail"]), 260),
        "来源笔记ID": first_value(item, ["note_id", "noteId"]),
        "标题": compact_text(first_value(item, ["title", "display_title", "desc"]), 160),
        "作者": compact_text(first_value(item, ["nickname", "nick_name", "author"]), 100),
        "数据来源": source,
    }


def group_row(task_name: str, keyword: str, item: dict[str, Any], source: str) -> dict[str, Any]:
    return {
        "任务": task_name,
        "关键词": keyword,
        "群聊ID": first_value(item, ["group_id", "groupId", "chat_id", "id"]),
        "群聊名称": compact_text(first_value(item, ["group_name", "name", "title"]), 160),
        "简介": compact_text(first_value(item, ["desc", "description", "intro"]), 220),
        "人数或热度": first_value(item, ["member_count", "members", "heat", "count"]),
        "入口信息": compact_text(first_value(item, ["url", "link", "join_url"]), 220),
        "数据来源": source,
    }


def run_task(payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    estimate = estimate_task(payload)
    config = load_config()
    config["api_key"] = str(payload.get("apiKey") or "").strip()
    config["api_base"] = payload.get("apiBase") or config.get("api_base") or DEFAULT_API_BASE
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    keyword = str(payload.get("keyword") or "墨西哥海外仓").strip() or "墨西哥海外仓"
    quantity = safe_int(payload.get("quantity"), 3, 1, 500)
    task = payload.get("task") or "material"
    task_name = TASKS.get(task, TASKS["material"])["name"]
    max_calls = estimate["maxCalls"]
    max_cost = estimate["maxCost"]
    budget = Budget(max_calls=max_calls, max_cost=max_cost, prices=estimate["prices"])
    workbook = empty_workbook_data()
    messages: list[str] = []

    if not config.get("api_key"):
        workbook = mock_workbook(keyword, task_name, run_id)
        record_call(run_id, "search_notes", {"keyword": keyword}, "演示", True, 0.0, "未填写 API Key，使用本地演示数据，未调用 TikHub")
        messages.append("未填写 API Key，本次使用演示数据，不产生费用。")
    else:
        try:
            if task == "competitor":
                run_competitor(keyword, quantity, task_name, run_id, config, budget, workbook, messages)
            elif task == "comments":
                run_comments(keyword, quantity, task_name, run_id, config, budget, workbook, messages)
            elif task == "topic":
                run_topic(keyword, quantity, task_name, run_id, config, budget, workbook, messages)
            elif task == "product":
                run_product(keyword, quantity, task_name, run_id, config, budget, workbook, messages)
            elif task == "images":
                run_images(keyword, quantity, task_name, run_id, config, budget, workbook, messages)
            elif task == "groups":
                run_groups(keyword, quantity, task_name, run_id, config, budget, workbook, messages)
            else:
                run_material(keyword, quantity, task_name, run_id, config, budget, workbook, messages)
        except BudgetExceeded as exc:
            messages.append(str(exc))
        except Exception as exc:  # noqa: BLE001
            messages.append(f"运行中遇到错误，已保存已拿到的数据：{exc}")

    workbook["API调用与费用记录"] = call_log_rows(run_id)
    output_path = OUTPUT_DIR / f"运去哪_小红书市场情报_{keyword}_{run_id}.xlsx"
    write_xlsx(output_path, workbook)
    return {
        "ok": True,
        "runId": run_id,
        "taskName": task_name,
        "keyword": keyword,
        "outputFile": str(output_path),
        "downloadUrl": "/outputs/" + urllib.parse.quote(output_path.name),
        "paidCalls": budget.paid_calls,
        "spent": round(budget.spent, 6),
        "messages": messages,
        "estimate": estimate,
    }


def empty_workbook_data() -> dict[str, list[dict[str, Any]]]:
    return {sheet: [] for sheet in SHEETS}


def run_material(
    keyword: str,
    quantity: int,
    task_name: str,
    run_id: str,
    config: dict[str, Any],
    budget: Budget,
    workbook: dict[str, list[dict[str, Any]]],
    messages: list[str],
) -> None:
    notes = search_notes(keyword, quantity, run_id, config, budget)
    for note in notes[:quantity]:
        note_id = first_value(note, ["note_id", "noteId", "id"])
        detail_payload = None
        detail_source = "搜索笔记"
        if note_id:
            endpoint_key = guess_note_detail_endpoint(note)
            try:
                detail_payload = tikhub_get(endpoint_key, {"note_id": note_id}, run_id, config, budget)
                detail_notes = extract_notes(detail_payload)
                if detail_notes:
                    note = detail_notes[0]
                detail_source = ENDPOINTS[endpoint_key]["name"]
            except Exception as exc:  # noqa: BLE001
                messages.append(f"笔记 {note_id} 详情暂未拿到，已保留搜索结果：{exc}")
        workbook["笔记素材"].append(note_row(task_name, keyword, note, detail_source))


def search_notes(keyword: str, quantity: int, run_id: str, config: dict[str, Any], budget: Budget) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    page = 1
    search_id = ""
    search_session_id = ""
    while len(notes) < quantity and page <= 10:
        params = {
            "keyword": keyword,
            "page": page,
            "sort_type": "general",
            "note_type": "不限",
            "time_filter": "不限",
            "search_id": search_id,
            "search_session_id": search_session_id,
        }
        payload = tikhub_get("search_notes", params, run_id, config, budget)
        notes.extend(extract_notes(payload))
        notes = unique_by(notes, ["note_id", "noteId", "id"])
        search_id = deep_first_value(payload, ["search_id", "searchId"], search_id)
        search_session_id = deep_first_value(payload, ["search_session_id", "searchSessionId"], search_session_id)
        if len(notes) >= quantity or not search_id and page > 1:
            break
        page += 1
    return notes[:quantity]


def guess_note_detail_endpoint(note: dict[str, Any]) -> str:
    note_type = compact_text(first_value(note, ["type", "note_type", "model_type"]) or first_value(note.get("note_card", {}) if isinstance(note.get("note_card"), dict) else {}, ["type", "note_type"]), 80).lower()
    if "video" in note_type or "视频" in note_type:
        return "get_video_note_detail"
    return "get_image_note_detail"


def run_competitor(
    keyword: str,
    quantity: int,
    task_name: str,
    run_id: str,
    config: dict[str, Any],
    budget: Budget,
    workbook: dict[str, list[dict[str, Any]]],
    messages: list[str],
) -> None:
    payload = tikhub_get("search_users", {"keyword": keyword, "page": 1}, run_id, config, budget)
    users = extract_users(payload)[:quantity]
    for user in users:
        user_id = first_value(user, ["user_id", "userId", "id", "userid"])
        if user_id:
            try:
                info = tikhub_get("get_user_info", {"user_id": user_id}, run_id, config, budget)
                extracted = extract_users(info)
                if extracted:
                    user = extracted[0]
            except Exception as exc:  # noqa: BLE001
                messages.append(f"用户 {user_id} 信息暂未拿到：{exc}")
        workbook["竞品账号"].append(user_row(task_name, keyword, user, "搜索用户/用户信息"))
        if user_id:
            try:
                posted = tikhub_get("get_user_posted_notes", {"user_id": user_id}, run_id, config, budget)
                for note in extract_notes(posted)[:5]:
                    row = note_row(task_name, keyword, note, "用户发布笔记")
                    row["用户ID"] = user_id
                    row["昵称"] = workbook["竞品账号"][-1].get("昵称", "")
                    workbook["账号作品"].append(row)
            except Exception as exc:  # noqa: BLE001
                messages.append(f"用户 {user_id} 作品暂未拿到：{exc}")


def run_comments(
    keyword: str,
    quantity: int,
    task_name: str,
    run_id: str,
    config: dict[str, Any],
    budget: Budget,
    workbook: dict[str, list[dict[str, Any]]],
    messages: list[str],
) -> None:
    notes = search_notes(keyword, quantity, run_id, config, budget)
    for note in notes[:quantity]:
        workbook["笔记素材"].append(note_row(task_name, keyword, note, "搜索笔记"))
        note_id = first_value(note, ["note_id", "noteId", "id"])
        if not note_id:
            continue
        try:
            payload = tikhub_get("get_note_comments", {"note_id": note_id, "index": 0, "sort_strategy": "latest_v2"}, run_id, config, budget)
            for comment in extract_comments(payload)[:30]:
                workbook["评论需求"].append(comment_row(task_name, keyword, note_id, comment, "笔记评论"))
        except Exception as exc:  # noqa: BLE001
            messages.append(f"笔记 {note_id} 评论暂未拿到：{exc}")


def run_topic(
    keyword: str,
    quantity: int,
    task_name: str,
    run_id: str,
    config: dict[str, Any],
    budget: Budget,
    workbook: dict[str, list[dict[str, Any]]],
    messages: list[str],
) -> None:
    notes = search_notes(keyword, quantity, run_id, config, budget)
    topic_ids: list[str] = []
    for note in notes:
        workbook["笔记素材"].append(note_row(task_name, keyword, note, "搜索笔记"))
        topic_id = first_value(note, ["page_id", "topic_id", "tag_id"])
        if topic_id:
            topic_ids.append(topic_id)
    for topic_id in list(dict.fromkeys(topic_ids))[:3]:
        try:
            info = tikhub_get("get_topic_info", {"page_id": topic_id}, run_id, config, budget)
            feed = tikhub_get("get_topic_feed", {"page_id": topic_id, "sort": "trend"}, run_id, config, budget)
            workbook["话题趋势"].append(
                {
                    "任务": task_name,
                    "关键词": keyword,
                    "话题ID": topic_id,
                    "话题名": compact_text(deep_first_value(info, ["name", "title", "tag_name"]), 120),
                    "浏览量": deep_first_value(info, ["view_count", "views", "read_count"]),
                    "讨论数": deep_first_value(info, ["discussion_count", "note_count", "count"]),
                    "关联笔记ID": deep_first_value(feed, ["note_id", "id"]),
                    "标题": compact_text(deep_first_value(feed, ["title", "display_title"]), 160),
                    "热度说明": "来自话题详情和话题笔记",
                    "数据来源": "话题详情/话题笔记",
                }
            )
        except Exception as exc:  # noqa: BLE001
            messages.append(f"话题 {topic_id} 暂未拿到：{exc}")
    if not topic_ids:
        messages.append("搜索结果里没有稳定识别到话题 ID，本次只保存了笔记线索。")


def run_product(
    keyword: str,
    quantity: int,
    task_name: str,
    run_id: str,
    config: dict[str, Any],
    budget: Budget,
    workbook: dict[str, list[dict[str, Any]]],
    messages: list[str],
) -> None:
    payload = tikhub_get("search_products", {"keyword": keyword, "page": 1}, run_id, config, budget)
    products = extract_products(payload)[:quantity]
    for product in products:
        sku_id = first_value(product, ["sku_id", "skuId", "id", "goods_id", "product_id"])
        workbook["商品研究"].append(product_row(task_name, keyword, product, "搜索商品"))
        if not sku_id:
            continue
        for endpoint_key, params in [
            ("get_product_detail", {"sku_id": sku_id}),
            ("get_product_review_overview", {"sku_id": sku_id}),
            ("get_product_reviews", {"sku_id": sku_id, "page": 0}),
        ]:
            try:
                detail = tikhub_get(endpoint_key, params, run_id, config, budget)
                for item in extract_products(detail)[:3] or [product]:
                    workbook["商品研究"].append(product_row(task_name, keyword, item, ENDPOINTS[endpoint_key]["name"]))
            except Exception as exc:  # noqa: BLE001
                messages.append(f"商品 {sku_id} 的 {ENDPOINTS[endpoint_key]['name']} 暂未拿到：{exc}")


def run_images(
    keyword: str,
    quantity: int,
    task_name: str,
    run_id: str,
    config: dict[str, Any],
    budget: Budget,
    workbook: dict[str, list[dict[str, Any]]],
    messages: list[str],
) -> None:
    images: list[dict[str, Any]] = []
    page = 1
    search_id = ""
    search_session_id = ""
    word_request_id = ""
    while len(images) < quantity and page <= 10:
        payload = tikhub_get(
            "search_images",
            {
                "keyword": keyword,
                "page": page,
                "search_id": search_id,
                "search_session_id": search_session_id,
                "word_request_id": word_request_id,
            },
            run_id,
            config,
            budget,
        )
        images.extend(extract_images(payload))
        images = unique_by(images, ["url", "image_url", "imageUrl", "id"])
        search_id = deep_first_value(payload, ["search_id", "searchId"], search_id)
        search_session_id = deep_first_value(payload, ["search_session_id", "searchSessionId"], search_session_id)
        word_request_id = deep_first_value(payload, ["word_request_id", "wordRequestId"], word_request_id)
        page += 1
    for item in images[:quantity]:
        workbook["图片结果"].append(image_row(task_name, keyword, item, "搜索图片"))


def run_groups(
    keyword: str,
    quantity: int,
    task_name: str,
    run_id: str,
    config: dict[str, Any],
    budget: Budget,
    workbook: dict[str, list[dict[str, Any]]],
    messages: list[str],
) -> None:
    groups: list[dict[str, Any]] = []
    page_no = 0
    search_id = ""
    while len(groups) < quantity and page_no <= 10:
        payload = tikhub_get(
            "search_groups",
            {"keyword": keyword, "page_no": page_no, "search_id": search_id, "is_recommend": 0},
            run_id,
            config,
            budget,
        )
        groups.extend(extract_groups(payload))
        groups = unique_by(groups, ["group_id", "groupId", "chat_id", "id"])
        search_id = deep_first_value(payload, ["search_id", "searchId"], search_id)
        page_no += 1
    for item in groups[:quantity]:
        workbook["群聊结果"].append(group_row(task_name, keyword, item, "搜索群聊"))


def call_log_rows(run_id: str) -> list[dict[str, Any]]:
    with db_connect() as conn:
        rows = conn.execute(
            "SELECT * FROM api_calls WHERE run_id = ? ORDER BY id ASC",
            (run_id,),
        ).fetchall()
    result = []
    for row in rows:
        endpoint_key = row["endpoint_key"]
        result.append(
            {
                "时间": row["created_at"],
                "运行ID": row["run_id"],
                "接口": ENDPOINTS[endpoint_key]["path"],
                "中文名": ENDPOINTS[endpoint_key]["name"],
                "参数": row["params_json"],
                "状态": row["status"],
                "是否缓存": "是" if row["from_cache"] else "否",
                "本次计费": row["cost"],
                "说明": row["message"],
            }
        )
    return result


def mock_workbook(keyword: str, task_name: str, run_id: str) -> dict[str, list[dict[str, Any]]]:
    workbook = empty_workbook_data()
    notes = [
        {
            "任务": task_name,
            "关键词": keyword,
            "笔记ID": "demo_note_001",
            "类型": "图文笔记",
            "标题": "墨西哥海外仓怎么选？3 个避坑点",
            "正文摘要": "演示数据：重点看清关能力、尾程派送稳定性、退货处理费用。",
            "作者昵称": "跨境仓配观察",
            "作者ID": "demo_user_001",
            "点赞": 128,
            "收藏": 42,
            "评论": 18,
            "分享链接": "演示数据，无真实链接",
            "图片或封面": "墨西哥仓库货架、打包台、尾程面单",
            "发布时间": "2026-06-15",
            "数据来源": "本地演示数据",
        },
        {
            "任务": task_name,
            "关键词": keyword,
            "笔记ID": "demo_note_002",
            "类型": "视频笔记",
            "标题": "美客多卖家入仓前要问清楚什么",
            "正文摘要": "演示数据：问仓租、操作费、贴标费、退件费，别只看首月报价。",
            "作者昵称": "拉美电商小记",
            "作者ID": "demo_user_002",
            "点赞": 96,
            "收藏": 31,
            "评论": 12,
            "分享链接": "演示数据，无真实链接",
            "图片或封面": "海外仓打包视频封面",
            "发布时间": "2026-06-14",
            "数据来源": "本地演示数据",
        },
        {
            "任务": task_name,
            "关键词": keyword,
            "笔记ID": "demo_note_003",
            "类型": "图文笔记",
            "标题": "墨西哥尾程慢，问题可能不在仓库",
            "正文摘要": "演示数据：用户关心派送时效、偏远地区附加费、丢件赔付。",
            "作者昵称": "海外仓运营笔记",
            "作者ID": "demo_user_003",
            "点赞": 77,
            "收藏": 25,
            "评论": 9,
            "分享链接": "演示数据，无真实链接",
            "图片或封面": "尾程派送线路图",
            "发布时间": "2026-06-13",
            "数据来源": "本地演示数据",
        },
    ]
    workbook["笔记素材"] = notes
    workbook["评论需求"] = [
        {
            "任务": "评论需求分析",
            "关键词": keyword,
            "笔记ID": "demo_note_001",
            "评论ID": "demo_comment_001",
            "评论内容": "墨西哥清关一般多久？会不会经常查验？",
            "评论用户": "新手卖家A",
            "点赞": 8,
            "是否二级评论": "否",
            "需求判断": "清关/合规痛点",
            "数据来源": "本地演示数据",
        },
        {
            "任务": "评论需求分析",
            "关键词": keyword,
            "笔记ID": "demo_note_002",
            "评论ID": "demo_comment_002",
            "评论内容": "报价里有没有贴标费和退件费？怕后面加钱。",
            "评论用户": "做拉美的小卖家",
            "点赞": 5,
            "是否二级评论": "否",
            "需求判断": "价格/报价需求",
            "数据来源": "本地演示数据",
        },
    ]
    workbook["竞品账号"] = [
        {
            "任务": "竞品账号研究",
            "关键词": keyword,
            "用户ID": "demo_user_001",
            "昵称": "跨境仓配观察",
            "简介": "演示数据：分享拉美仓储、清关、尾程经验。",
            "粉丝": 3200,
            "关注": 128,
            "作品数": 86,
            "主页链接": "演示数据，无真实链接",
            "数据来源": "本地演示数据",
        }
    ]
    workbook["账号作品"] = [
        {
            "任务": "竞品账号研究",
            "关键词": keyword,
            "用户ID": "demo_user_001",
            "昵称": "跨境仓配观察",
            "笔记ID": "demo_note_001",
            "标题": "墨西哥海外仓怎么选？3 个避坑点",
            "类型": "图文笔记",
            "点赞": 128,
            "收藏": 42,
            "评论": 18,
            "发布时间": "2026-06-15",
            "数据来源": "本地演示数据",
        }
    ]
    workbook["话题趋势"] = [
        {
            "任务": "话题趋势研究",
            "关键词": keyword,
            "话题ID": "demo_topic_001",
            "话题名": "墨西哥海外仓",
            "浏览量": "演示：较小但精准",
            "讨论数": 38,
            "关联笔记ID": "demo_note_001",
            "标题": "墨西哥海外仓怎么选？3 个避坑点",
            "热度说明": "适合做垂直行业内容，不适合盲目大规模投放。",
            "数据来源": "本地演示数据",
        }
    ]
    workbook["商品研究"] = [
        {
            "任务": "商品与用户痛点研究",
            "关键词": keyword,
            "商品ID/SKU": "demo_sku_001",
            "商品名": "海外仓服务咨询",
            "价格": "按仓储/操作/尾程报价",
            "店铺": "演示服务商",
            "评分或好评": "演示：重点看差评标签",
            "评论摘要": "担心隐藏费用、清关慢、丢件赔付不清楚。",
            "痛点判断": "价格/报价需求",
            "数据来源": "本地演示数据",
        }
    ]
    workbook["图片结果"] = [
        {
            "任务": "图片补充搜索",
            "关键词": keyword,
            "图片ID": "demo_img_001",
            "图片链接": "演示：墨西哥仓库货架图",
            "来源笔记ID": "demo_note_001",
            "标题": "墨西哥海外仓怎么选？3 个避坑点",
            "作者": "跨境仓配观察",
            "数据来源": "本地演示数据",
        }
    ]
    workbook["群聊结果"] = [
        {
            "任务": "群聊搜索",
            "关键词": keyword,
            "群聊ID": "demo_group_001",
            "群聊名称": "墨西哥跨境卖家交流群",
            "简介": "演示数据：适合观察卖家问题和服务需求。",
            "人数或热度": "演示：中等",
            "入口信息": "演示数据，无真实入口",
            "数据来源": "本地演示数据",
        }
    ]
    return workbook


def column_name(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def cell_xml(row_idx: int, col_idx: int, value: Any) -> str:
    ref = f"{column_name(col_idx)}{row_idx}"
    if value is None:
        text = ""
    else:
        text = str(value)
    text = escape(text)
    return f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>'


def sheet_xml(headers: list[str], rows: list[dict[str, Any]]) -> str:
    xml_rows = []
    header_cells = "".join(cell_xml(1, idx + 1, header) for idx, header in enumerate(headers))
    xml_rows.append(f'<row r="1">{header_cells}</row>')
    for row_idx, row in enumerate(rows, start=2):
        cells = "".join(cell_xml(row_idx, col_idx + 1, row.get(header, "")) for col_idx, header in enumerate(headers))
        xml_rows.append(f'<row r="{row_idx}">{cells}</row>')
    dimension = f"A1:{column_name(max(1, len(headers)))}{max(1, len(rows) + 1)}"
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<dimension ref="{dimension}"/>'
        "<sheetViews><sheetView workbookViewId=\"0\"/></sheetViews>"
        "<sheetFormatPr defaultRowHeight=\"18\"/>"
        "<sheetData>"
        + "".join(xml_rows)
        + "</sheetData>"
        "</worksheet>"
    )


def write_xlsx(path: Path, workbook: dict[str, list[dict[str, Any]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet_names = list(SHEETS.keys())
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            + "".join(
                f'<Override PartName="/xl/worksheets/sheet{idx}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                for idx in range(1, len(sheet_names) + 1)
            )
            + "</Types>",
        )
        zf.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(
                f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{idx}.xml"/>'
                for idx in range(1, len(sheet_names) + 1)
            )
            + "</Relationships>",
        )
        workbook_sheets = "".join(
            f'<sheet name="{escape(name)}" sheetId="{idx}" r:id="rId{idx}"/>'
            for idx, name in enumerate(sheet_names, start=1)
        )
        zf.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f"<sheets>{workbook_sheets}</sheets>"
            "</workbook>",
        )
        for idx, name in enumerate(sheet_names, start=1):
            zf.writestr(f"xl/worksheets/sheet{idx}.xml", sheet_xml(SHEETS[name], workbook.get(name, [])))


def json_response(handler: BaseHTTPRequestHandler, data: Any, status: int = 200) -> None:
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length <= 0:
        return {}
    body = handler.rfile.read(length).decode("utf-8")
    return json.loads(body)


def serve_file(handler: BaseHTTPRequestHandler, path: Path, download: bool = False) -> None:
    if not path.exists() or not path.is_file():
        handler.send_error(404, "File not found")
        return
    ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    data = path.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(data)))
    if download:
        handler.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{urllib.parse.quote(path.name)}")
    handler.end_headers()
    handler.wfile.write(data)


class YqnHandler(BaseHTTPRequestHandler):
    server_version = "YQN_XHS_Intel/0.1"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)
        if path in ("/", "/index.html"):
            serve_file(self, STATIC_DIR / "index.html")
            return
        if path.startswith("/static/"):
            rel = path.replace("/static/", "", 1)
            serve_file(self, STATIC_DIR / rel)
            return
        if path == "/api/settings":
            config = load_config()
            json_response(
                self,
                {
                    "hasApiKey": False,
                    "apiKeyPreview": "",
                    "apiBase": config.get("api_base") or DEFAULT_API_BASE,
                    "configPath": "朋友模式：服务器不保存 API Key",
                },
            )
            return
        if path == "/api/prices":
            config = load_config()
            prices, message = endpoint_price_map(config.get("api_base") or DEFAULT_API_BASE)
            json_response(
                self,
                {
                    "message": message,
                    "prices": [
                        {
                            "endpointKey": key,
                            "name": ENDPOINTS[key]["name"],
                            "endpoint": ENDPOINTS[key]["path"],
                            "unitPrice": prices.get(key, 0.01),
                        }
                        for key in ENDPOINTS
                    ],
                },
            )
            return
        if path.startswith("/outputs/"):
            name = Path(path).name
            serve_file(self, OUTPUT_DIR / name, download=True)
            return
        json_response(self, {"ok": False, "message": "没有找到这个页面"}, 404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            payload = read_json(self)
            if path == "/api/settings":
                api_base = str(payload.get("apiBase", DEFAULT_API_BASE)).strip() or DEFAULT_API_BASE
                save_config("", api_base)
                config = load_config()
                json_response(
                    self,
                    {
                        "ok": True,
                        "hasApiKey": bool(config.get("api_key")),
                        "apiKeyPreview": api_key_preview(config.get("api_key", "")),
                        "apiBase": config.get("api_base"),
                    },
                )
                return
            if path == "/api/check-connection":
                api_key = str(payload.get("apiKey") or "").strip()
                api_base = str(payload.get("apiBase") or DEFAULT_API_BASE).strip()
                result = check_tikhub_connection(api_key, api_base)
                json_response(self, result, 200 if result.get("ok") else 400)
                return
            if path == "/api/estimate":
                json_response(self, {"ok": True, "estimate": estimate_task(payload)})
                return
            if path == "/api/run":
                json_response(self, run_task(payload))
                return
            json_response(self, {"ok": False, "message": "没有找到这个接口"}, 404)
        except Exception as exc:  # noqa: BLE001
            json_response(self, {"ok": False, "message": str(exc)}, 500)


def find_free_port(start: int = 8765) -> int:
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("没有找到可用端口")


def main() -> None:
    init_db()
    host = os.environ.get("HOST", "127.0.0.1")
    port = safe_int(os.environ.get("PORT"), 8765, 1, 65535)
    if host == "127.0.0.1" and "PORT" not in os.environ:
        port = find_free_port(8765)
    server = ThreadingHTTPServer((host, port), YqnHandler)
    display_host = "127.0.0.1" if host == "0.0.0.0" else host
    url = f"http://{display_host}:{port}"
    print(f"{APP_NAME} 已启动：{url}")
    if "--no-browser" not in sys.argv and host != "0.0.0.0":
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("已停止。")


if __name__ == "__main__":
    main()
