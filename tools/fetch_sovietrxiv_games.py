#!/usr/bin/env python3
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://sovietrxiv.org/api/v1"
OUT = Path("sovietrxiv_game_export")
TEXTS = OUT / "texts"
OUT.mkdir(exist_ok=True)
TEXTS.mkdir(exist_ok=True)


def get_json(url: str, attempts: int = 8):
    for attempt in range(attempts):
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "SovietRxiv-game-mechanics-research/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                retry = exc.headers.get("Retry-After")
                delay = float(retry) if retry else min(90, 8 * (attempt + 1))
                print(f"Rate limited; sleeping {delay}s", flush=True)
                time.sleep(delay)
                continue
            if 500 <= exc.code < 600:
                delay = min(60, 3 * (attempt + 1))
                print(f"HTTP {exc.code}; retrying in {delay}s", flush=True)
                time.sleep(delay)
                continue
            raise
        except Exception as exc:
            if attempt == attempts - 1:
                raise
            delay = min(60, 3 * (attempt + 1))
            print(f"{type(exc).__name__}: {exc}; retrying in {delay}s", flush=True)
            time.sleep(delay)
    raise RuntimeError(f"Could not fetch {url}")


query = urllib.parse.urlencode(
    {"q": "Game", "source": "russiarxiv", "limit": 100}
)
search_url = f"{BASE}/papers?{query}"
search = get_json(search_url)
(OUT / "search_results.json").write_text(
    json.dumps(search, ensure_ascii=False, indent=2), encoding="utf-8"
)

papers = search.get("data", [])
print(f"Search total={search.get('total')}; returned={len(papers)}", flush=True)

manifest = []
for index, paper in enumerate(papers, 1):
    paper_id = paper["id"]
    print(f"[{index}/{len(papers)}] {paper_id}: {paper.get('title', '')}", flush=True)
    item = dict(paper)
    try:
        text_payload = get_json(f"{BASE}/papers/{urllib.parse.quote(paper_id)}/text")
        body = text_payload.get("body_md", "")
        item["text_word_count"] = text_payload.get("word_count")
        item["text_ok"] = bool(body)
        (TEXTS / f"{paper_id}.md").write_text(body, encoding="utf-8")
        (TEXTS / f"{paper_id}.json").write_text(
            json.dumps(text_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as exc:
        item["text_ok"] = False
        item["text_error"] = f"{type(exc).__name__}: {exc}"
        print(f"  ERROR: {item['text_error']}", flush=True)
    manifest.append(item)
    # Anonymous API tier is 30 requests/minute; stay comfortably below it.
    time.sleep(2.2)

(OUT / "manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(
    json.dumps(
        {
            "total": search.get("total"),
            "returned": len(papers),
            "texts_ok": sum(bool(x.get("text_ok")) for x in manifest),
            "texts_failed": sum(not bool(x.get("text_ok")) for x in manifest),
        },
        indent=2,
    ),
    flush=True,
)
