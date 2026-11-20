#!/usr/bin/env python3
"""Daily data update for the dashboard.

Appends new rows to the CSV files in data/ and refreshes data/headlines.json.
Each source is independent: if one fails, the others still update, and the
script exits with status 1 so GitHub Actions marks the run as failed and
emails the repository owner.

Run locally:  pip install -r scripts/requirements.txt && python scripts/update_data.py
Backfill NRB: python scripts/update_data.py --forex-from 2016-01-01
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DATA = Path(__file__).resolve().parent.parent / "data"
NPT = dt.timezone(dt.timedelta(hours=5, minutes=45))
TODAY = dt.datetime.now(NPT).date()
UA = {"User-Agent": "Mozilla/5.0 (compatible; sauryakarmacharya.com.np data updater; +https://www.sauryakarmacharya.com.np)"}
DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


# ---------------------------------------------------------------- helpers
def read_rows(name: str) -> tuple[list[str], list[dict]]:
    with open(DATA / name, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames or []), list(r)


def write_rows(name: str, fields: list[str], rows: list[dict], keys: tuple[str, ...]) -> int:
    """Merge-sort-dedupe and write. Returns number of rows written in total."""
    seen: dict[tuple, dict] = {}
    for row in rows:
        seen[tuple(row[k] for k in keys)] = row  # later rows win
    out = sorted(seen.values(), key=lambda r: tuple(r[k] for k in keys))
    with open(DATA / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    return len(out)


def to_number(text: str) -> float | None:
    """First number in a string like 'Rs. 1,62,500.00' or 'रू ६५' → float."""
    m = re.search(r"\d[\d,]*(?:\.\d+)?", text.translate(DEV_DIGITS))
    return float(m.group(0).replace(",", "")) if m else None


def get(url: str, **kw) -> requests.Response:
    last = None
    for attempt in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=40, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException as e:  # retry transient errors
            last = e
            time.sleep(5 * (attempt + 1))
    raise last  # type: ignore[misc]


# ---------------------------------------------------------------- NRB forex
def update_forex(start: dt.date | None) -> str:
    fields, rows = read_rows("forex.csv")
    if start is None:
        last = max((r["date"] for r in rows), default=None)
        start = (dt.date.fromisoformat(last) + dt.timedelta(days=1)) if last else TODAY - dt.timedelta(days=400)
    if start > TODAY:
        return "forex: already up to date"
    added = 0
    chunk_start = start
    while chunk_start <= TODAY:
        chunk_end = min(chunk_start + dt.timedelta(days=90), TODAY)
        page = 1
        while True:
            r = get("https://www.nrb.org.np/api/forex/v1/rates", params={
                "from": chunk_start.isoformat(), "to": chunk_end.isoformat(), "per_page": 100, "page": page})
            j = r.json()
            payload = (j.get("data") or {}).get("payload") or []
            for day in payload:
                date = day["date"]
                for rate in day.get("rates", []):
                    c = rate["currency"]
                    rows.append({"date": date, "iso3": c["iso3"], "name": c["name"], "unit": str(c["unit"]),
                                 "buy": str(rate["buy"]), "sell": str(rate["sell"])})
                    added += 1
            pages = (j.get("pagination") or {}).get("pages") or 1
            if page >= pages:
                break
            page += 1
        chunk_start = chunk_end + dt.timedelta(days=1)
    total = write_rows("forex.csv", fields, rows, ("date", "iso3"))
    return f"forex: +{added} rate rows from {start} ({total} total)"


# ---------------------------------------------------------------- FENEGOSIDA
BULLION_PATTERNS = {
    "fine_gold": r"FINE\s*GOLD",
    "tejabi_gold": r"TEJABI\s*GOLD",
    "silver": r"SILVER",
}


BULLION_URLS = ["https://www.fenegosida.org/", "https://fenegosida.org/", "http://www.fenegosida.org/"]


def _bullion_debug(note: str, text: str = "") -> None:
    """Save a short diagnostic so a failed parse can be fixed without guessing."""
    d = DATA / "_debug"
    d.mkdir(exist_ok=True)
    snippets = [m.start() for m in re.finditer(r"tola|gold|silver|सुन|चाँदी", text, re.I)][:12]
    parts = [text[max(0, i - 150): i + 150] for i in snippets] or [text[:1500]]
    (d / "bullion.txt").write_text(f"{dt.datetime.now(NPT).isoformat()}\n{note}\n\n" + "\n---\n".join(parts), encoding="utf-8")


def parse_bullion(text: str) -> dict[str, float]:
    text = re.sub(r"\s+", " ", text.translate(DEV_DIGITS))
    found: dict[str, float] = {}
    for item, pat in BULLION_PATTERNS.items():
        # e.g. "FINE GOLD (9999) per 1 tola रु 1,62,500" -- allow either order of label/number
        for rx in (pat + r".{0,60}?(?:per\s*)?1\s*tola\D{0,25}?(\d[\d,]{3,})",
                   pat + r"\D{0,80}?(\d{1,3}(?:,\d{2,3})+)"):
            m = re.search(rx, text, re.I)
            if m and (v := to_number(m.group(1))):
                found[item] = v
                break
    return found


def update_bullion() -> str:
    errors = []
    text = ""
    for url in BULLION_URLS:
        try:
            r = requests.get(url, headers=UA, timeout=40)
            text = BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)
            if r.status_code != 200:
                errors.append(f"{url}: HTTP {r.status_code}")
                continue
            found = parse_bullion(text)
            if found:
                break
            errors.append(f"{url}: page loaded ({len(text)} chars) but no prices matched")
        except requests.RequestException as e:
            errors.append(f"{url}: {type(e).__name__}: {e}")
    else:
        _bullion_debug("; ".join(errors), text)
        raise RuntimeError("bullion: " + "; ".join(errors))
    if "fine_gold" in found and found["fine_gold"] < 10000:
        _bullion_debug(f"implausible gold price {found}", text)
        raise RuntimeError(f"bullion: implausible gold price {found['fine_gold']}")
    fields, rows = read_rows("bullion.csv")
    for item, v in found.items():
        rows.append({"date": TODAY.isoformat(), "item": item, "unit": "tola", "price": f"{v:.0f}"})
    write_rows("bullion.csv", fields, rows, ("date", "item", "unit"))
    return f"bullion: {', '.join(f'{k}={v:,.0f}' for k, v in found.items())}"


# ---------------------------------------------------------------- Kalimati
def update_kalimati() -> str:
    s = requests.Session()
    s.headers.update(UA)
    try:
        s.get("https://kalimatimarket.gov.np/lang/en", timeout=40)  # switch site language to English
    except requests.RequestException:
        pass
    html = s.get("https://kalimatimarket.gov.np/price", timeout=40)
    html.raise_for_status()
    soup = BeautifulSoup(html.text, "html.parser")
    new = []
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 5:
                continue
            name, unit, mn, mx, avg = cells[0], cells[1], *(to_number(x) for x in cells[2:5])
            if avg is None or mn is None or mx is None or not name:
                continue
            new.append({"date": TODAY.isoformat(), "commodity": re.sub(r"\s+", " ", name),
                        "unit": unit.strip(), "min": f"{mn:g}", "max": f"{mx:g}", "avg": f"{avg:g}"})
    if len(new) < 10:
        raise RuntimeError(f"kalimati: only {len(new)} rows parsed (page layout may have changed)")
    fields, rows = read_rows("kalimati.csv")
    rows.extend(new)
    write_rows("kalimati.csv", fields, rows, ("date", "commodity"))
    ascii_names = sum(1 for r in new if r["commodity"].isascii())
    note = "" if ascii_names > len(new) / 2 else " (WARNING: names not in English; chart matching may fail)"
    return f"kalimati: {len(new)} commodities{note}"


# ---------------------------------------------------------------- Headlines
def update_headlines() -> str:
    url = "https://news.google.com/rss/search"
    params = {"q": 'Nepal (economy OR "Rastra Bank" OR remittance OR inflation OR budget OR "foreign exchange" OR trade OR agriculture) when:4d', "hl": "en-NP", "gl": "NP", "ceid": "NP:en"}
    root = ET.fromstring(get(url, params=params).content)
    items = []
    seen = set()
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        src = (it.findtext("source") or "").strip()
        if src and title.endswith(" - " + src):
            title = title[: -len(src) - 3]
        key = title.lower()
        if not title or key in seen:
            continue
        seen.add(key)
        pub = it.findtext("pubDate") or ""
        try:
            date = dt.datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %Z").date().isoformat()
        except ValueError:
            date = ""
        items.append({"title": title, "source": src, "link": it.findtext("link") or "", "date": date})
    items.sort(key=lambda x: x["date"], reverse=True)
    items = items[:15]
    if not items:
        raise RuntimeError("headlines: feed returned no items")
    (DATA / "headlines.json").write_text(json.dumps({"items": items, "updated": TODAY.isoformat()}, ensure_ascii=False, indent=1), encoding="utf-8")
    return f"headlines: {len(items)} items"


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--forex-from", type=dt.date.fromisoformat, help="backfill NRB rates from this date (YYYY-MM-DD)")
    ap.add_argument("--only", choices=["forex", "bullion", "kalimati", "headlines"], action="append")
    args = ap.parse_args()

    jobs = {
        "forex": lambda: update_forex(args.forex_from),
        "bullion": update_bullion,
        "kalimati": update_kalimati,
        "headlines": update_headlines,
    }
    failed = []
    for name, fn in jobs.items():
        if args.only and name not in args.only:
            continue
        try:
            print("OK  ", fn())
        except Exception as e:  # keep going; report at the end
            failed.append(name)
            print(f"FAIL {name}: {type(e).__name__}: {e}", file=sys.stderr)
    if failed:
        print(f"\nFailed sources: {', '.join(failed)} (other sources were still updated)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
