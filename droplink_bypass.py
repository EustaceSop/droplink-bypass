"""
droplink.co bypass — 貼上短連結，回傳真實下載連結。

Flow:
  1. GET https://droplink.co/<code>  with Referer: https://game5s.com/
       -> HTTP 200 (the real "final page" instead of the 307 to safe2.php)
  2. Parse the <form id="go-link"> hidden fields:
       _csrfToken, ad_form_data, _Token[fields], _Token[unlocked], _method
  3. POST them to https://droplink.co/links/go with the same cookie jar
       -> {"status":"success","url":"https://www.mediafire.com/..."}

Usage:
  python droplink_bypass.py U0Mm
  python droplink_bypass.py https://droplink.co/U0Mm
"""
import re
import sys
import time
import json
import argparse
import urllib.parse
from urllib.request import Request, build_opener, HTTPCookieProcessor
from http.cookiejar import CookieJar

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/131.0.0.0 Safari/537.36")

MAGIC_REFERER = "https://game5s.com/"

FORM_RE = re.compile(r'<form[^>]*id="go-link"[^>]*>(.*?)</form>', re.DOTALL)
ACTION_RE = re.compile(r'action="([^"]+)"')
INPUT_RE = re.compile(r'<input[^>]+name="([^"]+)"[^>]+value="([^"]*)"')
COUNTER_RE = re.compile(r'"counter_value"\s*:\s*"?(\d+)"?')


def expand_tco(url: str) -> str:
    """t.co 對非瀏覽器回 200 + HTML 跳轉,解析出內嵌目標 URL。"""
    req = Request(url, headers={"User-Agent": UA})
    jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))
    with opener.open(req, timeout=30) as r:
        html = r.read().decode("utf-8", errors="replace")
    m = re.search(r'https?://droplink\.co/[^\s"\'<>]+', html)
    if m:
        return m.group(0)
    m = re.search(r'(?:URL=|href=["\']|location\.href=["\'])(https?://[^\s"\'<>]+)', html)
    return m.group(1) if m else url


def extract_code(arg: str) -> str:
    arg = arg.strip()
    if "t.co/" in arg:
        arg = expand_tco(arg)
    if "://" in arg:
        p = urllib.parse.urlparse(arg)
        return p.path.lstrip("/").split("/")[0]
    return arg.lstrip("/")


FOLDER_KEY_RE = re.compile(r"mediafire\.com/folder/([a-z0-9]+)", re.I)
FILE_KEY_RE = re.compile(r"mediafire\.com/(?:file|file_premium|view|download)/([a-z0-9]+)", re.I)
MF_API = "https://www.mediafire.com/api/1.5/folder/get_content.php"


def mediafire_list(url: str) -> dict:
    """把 mediafire 資料夾/檔案連結展開成檔案清單(含每檔直鏈)。"""
    fm = FOLDER_KEY_RE.search(url)
    if not fm:
        fk = FILE_KEY_RE.search(url)
        if fk:
            return {"kind": "file", "folder_key": None, "files": [{
                "filename": url.rstrip("/").split("/")[-1] or fk.group(1),
                "size": None, "quickkey": fk.group(1), "download": url,
            }]}
        return {"kind": "unknown", "folder_key": None, "files": []}

    key = fm.group(1)
    files, chunk = [], 1
    while True:
        q = urllib.parse.urlencode({
            "folder_key": key, "content_type": "files",
            "chunk": chunk, "chunk_size": 100, "response_format": "json",
        })
        req = Request(f"{MF_API}?{q}", headers={"User-Agent": UA})
        with build_opener().open(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
        fc = data.get("response", {}).get("folder_content", {})
        for f in fc.get("files", []):
            files.append({
                "filename": f.get("filename"),
                "size": int(f.get("size", 0)) or None,
                "quickkey": f.get("quickkey"),
                "downloads": f.get("downloads"),
                "created": f.get("created"),
                "download": f.get("links", {}).get("normal_download"),
            })
        if fc.get("more_chunks") == "yes":
            chunk += 1
        else:
            break
    return {"kind": "folder", "folder_key": key, "files": files}


def resolve(code: str) -> dict:
    jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))

    # Step 1: fetch the final page (Referer trick unlocks it)
    url1 = f"https://droplink.co/{code}"
    req1 = Request(url1, headers={
        "User-Agent": UA,
        "Referer": MAGIC_REFERER,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with opener.open(req1, timeout=30) as r:
        if r.status != 200:
            raise RuntimeError(f"stage 1 HTTP {r.status}")
        html = r.read().decode("utf-8", errors="replace")

    form_m = FORM_RE.search(html)
    if not form_m:
        raise RuntimeError("go-link form not found — link may be dead or format changed")
    form = form_m.group(0)
    action_m = ACTION_RE.search(form)
    if not action_m:
        raise RuntimeError("form action missing")
    action = urllib.parse.urljoin(url1, action_m.group(1))
    fields = dict(INPUT_RE.findall(form))
    if "_csrfToken" not in fields or "ad_form_data" not in fields:
        raise RuntimeError(f"expected fields missing: {list(fields)}")

    # Time-lock: server rejects POST until `counter_value` seconds have elapsed
    counter_m = COUNTER_RE.search(html)
    wait = int(counter_m.group(1)) if counter_m else 3
    time.sleep(wait + 0.5)

    # Step 2: POST form (no captcha needed — server accepts empty g-recaptcha-response)
    fields.setdefault("g-recaptcha-response", "")
    body = urllib.parse.urlencode(fields).encode("utf-8")
    req2 = Request(action, data=body, method="POST", headers={
        "User-Agent": UA,
        "Referer": url1,
        "Origin": "https://droplink.co",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    })
    with opener.open(req2, timeout=30) as r:
        raw = r.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except Exception:
            raise RuntimeError(f"non-JSON response ({r.status}): {raw[:200]}")

    if payload.get("status") != "success" or not payload.get("url"):
        raise RuntimeError(f"unlock failed: {payload}")
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description="Resolve a droplink.co short URL to its real destination.")
    ap.add_argument("target", help="short code (e.g. U0Mm) or full URL (https://droplink.co/U0Mm)")
    ap.add_argument("--json", action="store_true", help="print full JSON response")
    args = ap.parse_args()

    code = extract_code(args.target)
    try:
        result = resolve(code)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["url"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
