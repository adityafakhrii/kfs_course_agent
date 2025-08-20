# kfs_course_agent/agent.py
import time
import json
import re
from typing import Any, Dict, List, Optional
from google.adk.agents import Agent
from google.adk.tools import ToolContext
import requests

API_URL = "https://api.codepolitan.com/course?page=1&limit=1000"

# ---------- Helpers ----------
def _http_get_json(url: str, timeout: int = 20) -> Dict[str, Any]:
    """HTTP GET JSON helper. Return {status, data|error}."""
    try:
        resp = requests.get(url, timeout=timeout)
        if resp.status_code != 200:
            return {"status": "error", "error_message": f"HTTP {resp.status_code}"}
        # Some APIs wrap data; we pass through—tools will normalize later
        return {"status": "success", "data": resp.json()}
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

def _as_text(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, (dict, list)):
        try:
            return json.dumps(x, ensure_ascii=False)
        except Exception:
            return str(x)
    return str(x)

def _pick_first(d: Dict[str, Any], candidates: List[str]) -> Optional[Any]:
    for k in candidates:
        if k in d and d[k] not in (None, "", []):
            return d[k]
    return None

def _flatten(obj: Any, prefix: str = "") -> Dict[str, Any]:
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(_flatten(v, f"{prefix}{k}."))  # nested dot keys
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(_flatten(v, f"{prefix}{i}."))  # index as part of key
    else:
        out[prefix[:-1]] = obj
    return out

def _normalize_course(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Try to normalize unknown JSON shape into a common schema.
    We DO NOT assume exact field names from the API.
    """
    flat = _flatten(raw)

    title = (
        _pick_first(raw, ["title", "name", "course_title"])
        or _pick_first(flat, ["data.title", "attributes.title"])
        or "Untitled Course"
    )
    slug = (
        _pick_first(raw, ["slug", "permalink"])
        or _pick_first(flat, ["data.slug", "attributes.slug"])
    )
    desc = (
        _pick_first(raw, ["description", "intro", "summary"])
        or _pick_first(flat, ["data.description", "attributes.description"])
        or ""
    )
    level = (
        _pick_first(raw, ["level", "difficulty"])
        or _pick_first(flat, ["attributes.level"])
    )
    price = (
        _pick_first(raw, ["price", "harga"])
        or _pick_first(flat, ["attributes.price"])
    )
    categories = _pick_first(raw, ["categories", "category", "tags"]) or []
    if isinstance(categories, str):
        categories = [categories]

    text_blob = " ".join(
        [
            _as_text(title),
            _as_text(desc),
            _as_text(level),
            _as_text(categories),
            _as_text(price),
            _as_text(raw),
        ]
    ).lower()

    return {
        "title": _as_text(title),
        "slug": slug,
        "description": _as_text(desc),
        "level": _as_text(level).lower(),
        "categories": categories,
        "price": price,
        "raw": raw,
        "_text": text_blob,
    }

def _ensure_index(tool_context: ToolContext, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Cache courses in app-level state for speed. Uses 'app:course_index'.
    """
    now = time.time()
    cache = tool_context.state.get("app:course_index")
    if cache and not force_refresh:
        # optional: TTL 6 hours
        if now - cache.get("ts", 0) < 6 * 3600 and cache.get("items"):
            return {"status": "success", "items": cache["items"]}

    res = _http_get_json(API_URL)
    if res["status"] != "success":
        return res

    payload = res["data"]
    # Try common layouts: either list or wrapped {data: [...]}
    items = []
    if isinstance(payload, dict):
        arr = payload.get("data") or payload.get("courses") or payload.get("items") or []
        if isinstance(arr, list):
            items = arr
    elif isinstance(payload, list):
        items = payload

    normalized = [_normalize_course(x) for x in items]
    tool_context.state["app:course_index"] = {
        "ts": now,
        "items": normalized,
        "count": len(normalized),
    }
    return {"status": "success", "items": normalized}

def _score_match(q: str, course: Dict[str, Any], level: Optional[str], topic: Optional[str]) -> float:
    txt = course.get("_text", "")
    score = 0.0
    if q:
        for token in re.findall(r"[a-z0-9]+", q.lower()):
            if token in txt:
                score += 3
        # exact phrase bonus
        if q.lower() in txt:
            score += 5
    if level:
        if level.lower() in (course.get("level") or ""):
            score += 2
    if topic:
        if topic.lower() in txt:
            score += 2
    return score

# ---------- Tools (function tools) ----------
def refresh_courses(tool_context: ToolContext) -> Dict[str, Any]:
    """Refresh cache dari API Codepolitan. Return jumlah item.
    Returns:
      dict: {status, count} atau {status:"error", error_message}
    """
    res = _ensure_index(tool_context, force_refresh=True)
    if res["status"] != "success":
        return res
    return {"status": "success", "count": len(res["items"])}

def search_courses(
    query: Optional[str] = None,
    level: Optional[str] = None,
    topic: Optional[str] = None,
    max_results: int = 10,
    tool_context: ToolContext = None,
) -> Dict[str, Any]:
    """Cari kursus berdasarkan keyword, level, atau topik.
    Args:
      query: kata kunci, contoh "Laravel pemula", "Tailwind CSS".
      level: tingkat kesulitan (bebas teks; dicocokkan longgar).
      topic: topik spesifik/stack (mis. "laravel", "react", "api").
      max_results: maksimal hasil.
    Returns:
      dict: {status, results:[{title, slug, level, price, categories, preview}]}.
    Note:
      Skema field API bisa berubah; fungsi ini fleksibel & fuzzy.
    """
    idx = _ensure_index(tool_context)
    if idx["status"] != "success":
        return idx
    items = idx["items"]

    scored = []
    for c in items:
        s = _score_match(query or "", c, level, topic)
        if s > 0 or not (query or level or topic):
            scored.append((s, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for s, c in scored[:max_results]:
        results.append(
            {
                "title": c["title"],
                "slug": c["slug"],
                "level": c["level"],
                "price": c["price"],
                "categories": c["categories"],
                "preview": (c["description"][:200] + "…") if c["description"] else "",
                "score": round(s, 2),
            }
        )
    return {"status": "success", "results": results, "total_indexed": len(items)}

def get_course_detail(
    slug_or_title: str,
    tool_context: ToolContext = None,
) -> Dict[str, Any]:
    """Ambil detail 1 kursus berdasarkan slug atau judul.
    Args:
      slug_or_title: slug (jika ada) atau potongan judul.
    Returns:
      dict: {status, course:{...}} atau {status:"error", error_message}
    """
    idx = _ensure_index(tool_context)
    if idx["status"] != "success":
        return idx

    target = slug_or_title.lower().strip()
    for c in idx["items"]:
        if c["slug"] and target == str(c["slug"]).lower():
            return {"status": "success", "course": c}
    # fallback fuzzy by title
    for c in idx["items"]:
        if target in c["title"].lower():
            return {"status": "success", "course": c}
    return {"status": "error", "error_message": f"Kelas '{slug_or_title}' tidak ketemu."}

def set_user_pref(
    preferred_topic: Optional[str] = None,
    preferred_level: Optional[str] = None,
    budget_hint: Optional[str] = None,
    tool_context: ToolContext = None,
) -> Dict[str, Any]:
    """Simpan preferensi user ke state (dipakai rekomendasi berikutnya).
    Args:
      preferred_topic: ex "laravel", "react", "tailwind".
      preferred_level: ex "beginner", "intermediate".
      budget_hint: ex "gratis", "<=500k", "hemat".
    Returns:
      dict: {status, saved:{...}}
    """
    key = "user:preferences"
    prefs = tool_context.state.get(key, {})
    if preferred_topic:
        prefs["topic"] = preferred_topic
    if preferred_level:
        prefs["level"] = preferred_level
    if budget_hint:
        prefs["budget"] = budget_hint
    tool_context.state[key] = prefs
    return {"status": "success", "saved": prefs}

def recommend_for_user(
    max_results: int = 5,
    tool_context: ToolContext = None,
) -> Dict[str, Any]:
    """Rekomendasi berdasar 'user:preferences' yang tersimpan."""
    prefs = tool_context.state.get("user:preferences", {})
    q = prefs.get("topic")
    lvl = prefs.get("level")
    res = search_courses(query=q, level=lvl, topic=q, max_results=max_results, tool_context=tool_context)
    if res["status"] != "success":
        return res
    return {"status": "success", "recommendations": res["results"], "prefs": prefs}

# ---------- Root Agent ----------
root_agent = Agent(
    name="kfs_course_agent",
    model="gemini-2.0-flash",
    description="Agent tanya-jawab tentang kursus KelasFullstack menggunakan API Codepolitan.",
    instruction=(
        "Kamu adalah agen yang MENJAWAB FAKTA kursus berdasarkan tool, bukan ngarang. "
        "Selalu pakai search_courses untuk pertanyaan umum ('ada kelas X?', 'buat pemula apa?'). "
        "Pakai get_course_detail kalau user sebut slug/judul spesifik. "
        "Kalau user sebut preferensi (topik/level/budget), simpan via set_user_pref lalu beri saran "
        "dengan recommend_for_user. Jika data tidak ada, bilang jujur 'tidak ditemukan'. "
        "Jawaban ringkas, to the point, pakai bullet bila cocok."
    ),
    tools=[refresh_courses, search_courses, get_course_detail, set_user_pref, recommend_for_user],
)
