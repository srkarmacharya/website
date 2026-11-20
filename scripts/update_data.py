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
import os
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


BULLION_URLS = ["https://www.fenegosida.org/", "https://www.fenegosida.org/rate-history.php"]


def _bullion_debug(note: str, pages: list[tuple[str, str]]) -> None:
    """Save the raw HTML of the pages tried, so a failed parse can be fixed without guessing."""
    d = DATA / "_debug"
    d.mkdir(exist_ok=True)
    body = "\n\n".join(f"===== {u} =====\n{h[:6000]}" for u, h in pages)
    (d / "bullion.txt").write_text(f"{dt.datetime.now(NPT).isoformat()}\n{note}\n\n{body}", encoding="utf-8")


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


FENEGOSIDA_API = "https://api.fenegosida.org/api/website/v1/Dashboard/"
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _fenegosida_json(path: str):
    r = requests.get(FENEGOSIDA_API + path, headers={**UA, "Referer": "https://www.fenegosida.org/"}, timeout=40)
    r.raise_for_status()
    return r.json()


def fetch_bullion_api() -> list[dict]:
    """FENEGOSIDA's own JSON feeds: 'today' (official daily rates) and a 365-day history."""
    rows: list[dict] = []
    # one year of daily history: {"goldData": [{"date": "21", "month": "Oct", "year": "2026", "gm": ..., "tola": ...}], "silverData": [...]}
    hist = _fenegosida_json("WeeklyChartRate?weekmonthyear=365")
    for key, series in (hist.items() if isinstance(hist, dict) else []):
        item = "fine_gold" if "gold" in key.lower() else "silver" if "silver" in key.lower() else None
        if not item or not isinstance(series, list):
            continue
        for p in series:
            try:
                d = dt.date(int(p["year"]), MONTHS[str(p["month"])[:3].lower()], int(p["date"]))
            except (KeyError, ValueError):
                continue
            for unit, field in (("tola", "tola"), ("10g", "gm")):
                if p.get(field):
                    rows.append({"date": d.isoformat(), "item": item, "unit": unit, "price": f"{float(p[field]):g}"})
    # today's official rates: rateType is in Nepali, e.g. "छापावाल सुन (१ तोला)", "असली चाँदी दर (१० ग्राम)"
    for t in _fenegosida_json("today"):
        name = t.get("rateType", "")
        item = "fine_gold" if "सुन" in name else "silver" if "चाँदी" in name else None
        unit = "tola" if "तोला" in name else "10g" if "ग्राम" in name else None
        if item and unit and t.get("todayBaseRatePerGram"):
            when = dt.datetime.fromisoformat(t["todayDate"].replace("Z", "+00:00")).astimezone(NPT).date()
            rows.append({"date": when.isoformat(), "item": item, "unit": unit, "price": f"{float(t['todayBaseRatePerGram']):g}"})
    return rows


def parse_fenegosida_cards(text: str) -> dict[str, float]:
    """Current layout: '... Gold 4.74% Nrs 210,390 Silver 6.75% Nrs 2,666.5 ...'"""
    t = re.sub(r"\s+", " ", text.translate(DEV_DIGITS))
    out = {}
    for item, label in (("fine_gold", "Gold"), ("silver", "Silver")):
        m = re.search(label + r"\s+-?[\d.]+\s*%\s*(?:Nrs|Rs|रु)\.?\s*([\d,]+(?:\.\d+)?)", t)
        if m and (v := to_number(m.group(1))):
            out[item] = v
    return out


def _render_with_browser(url: str) -> tuple[dict[str, dict[str, float]], str, list[str]]:
    """FENEGOSIDA's site is a JavaScript app: load it in headless Chromium, switch the
    unit toggle to each of Tola and 10g, and read the prices shown."""
    from playwright.sync_api import sync_playwright  # installed in the GitHub workflow

    json_urls: list[str] = []
    prices: dict[str, dict[str, float]] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
        page = browser.new_page(user_agent=UA["User-Agent"])
        page.on("response", lambda r: json_urls.append(r.url) if "json" in (r.headers.get("content-type") or "") else None)
        page.goto(url, wait_until="networkidle", timeout=60000)
        try:
            page.wait_for_function("() => /Nrs|tola/i.test(document.body.innerText)", timeout=20000)
        except Exception:
            pass
        text = page.inner_text("body")
        for unit, label in (("tola", "Tola"), ("10g", "10g")):
            try:
                page.get_by_text(label, exact=True).first.click(timeout=5000)
                page.wait_for_timeout(1500)
                found = parse_fenegosida_cards(page.inner_text("body"))
                if found:
                    prices[unit] = found
            except Exception:
                continue
        browser.close()
    return prices, text, json_urls


def update_bullion() -> str:
    try:
        new = fetch_bullion_api()
        source = "FENEGOSIDA API"
    except Exception as e:  # fall back to reading the rendered web page
        print(f"     bullion API failed ({type(e).__name__}: {e}); trying the web page", file=sys.stderr)
        new, source = [], "web page"
    if not any(r["unit"] == "tola" for r in new):
        url = BULLION_URLS[0]
        prices, text, json_urls = _render_with_browser(url)
        if not prices.get("tola"):
            _bullion_debug(f"API and page both failed; parsed={prices}", [(url, text), ("JSON requests", "\n".join(json_urls))])
            raise RuntimeError(f"bullion: no prices from API or page (parsed: {prices})")
        new = [{"date": TODAY.isoformat(), "item": i, "unit": u, "price": f"{v:g}"} for u, items in prices.items() for i, v in items.items()]
        source = "web page"
    latest = max(r["date"] for r in new)
    today_tola = {r["item"]: float(r["price"]) for r in new if r["date"] == latest and r["unit"] == "tola"}
    if "silver" in today_tola and today_tola.get("fine_gold", 0) < today_tola["silver"] * 20:
        raise RuntimeError(f"bullion: implausible prices {today_tola}")
    fields, rows = read_rows("bullion.csv")
    rows.extend(new)
    total = write_rows("bullion.csv", fields, rows, ("date", "item", "unit"))
    return f"bullion ({source}): latest {latest} {today_tola}; {total} rows total"


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


# ---------------------------------------------------------------- NEPSE
def parse_sharesansar_market(html: str) -> tuple[str | None, list[dict]]:
    """sharesansar.com/market has tables headed 'Index Open High Low Close Point % Change Turnover'
    under 'Indices As of YYYY-MM-DD' and 'Sub Indices As of YYYY-MM-DD'."""
    soup = BeautifulSoup(html, "html.parser")
    m = re.search(r"As of\s*(\d{4}-\d{2}-\d{2})", soup.get_text(" ", strip=True))
    date = m.group(1) if m else None
    rows = []
    for table in soup.find_all("table"):
        head = [c.get_text(" ", strip=True).lower() for c in table.find_all("th")]
        if not head or "close" not in head:
            continue
        col = {name: head.index(name) for name in head}
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all("td")]
            if len(cells) < len(head) or not re.search(r"index", cells[0], re.I):
                continue
            def g(key):
                i = next((i for n, i in col.items() if n.startswith(key)), None)
                return to_number(cells[i]) if i is not None else None
            close = g("close")
            if close is None:
                continue
            pct_i = next((i for n, i in col.items() if "%" in n), None)
            pct = cells[pct_i].replace(",", "") if pct_i is not None else ""
            rows.append({"index": cells[0], "open": g("open"), "high": g("high"), "low": g("low"), "close": close,
                         "change_pct": pct, "turnover": g("turnover")})
    return date, rows


def update_nepse() -> str:
    errors = []
    date, rows = None, []
    try:
        r = get("https://www.sharesansar.com/market")
        date, rows = parse_sharesansar_market(r.text)
        if not rows:
            errors.append("sharesansar: no index rows parsed")
            d = DATA / "_debug"; d.mkdir(exist_ok=True)
            (d / "nepse.txt").write_text(r.text[:30000], encoding="utf-8")
    except Exception as e:
        errors.append(f"sharesansar: {type(e).__name__}: {e}")
    if not rows:  # fallback: NEPSE's own API through the nepse-data-api library
        try:
            from nepse_data_api import Nepse  # type: ignore
            data = Nepse().get_nepse_index()
            items = data if isinstance(data, list) else data.get("data", []) if isinstance(data, dict) else []
            for it in items:
                if "index" in it and it.get("close") is not None:
                    rows.append({"index": it["index"], "open": it.get("open"), "high": it.get("high"), "low": it.get("low"),
                                 "close": it["close"], "change_pct": it.get("perChange", ""), "turnover": it.get("turnover")})
            date = date or TODAY.isoformat()
        except Exception as e:
            errors.append(f"nepse-data-api: {type(e).__name__}: {e}")
    if not rows:
        raise RuntimeError("nepse: " + "; ".join(errors))
    date = date or TODAY.isoformat()
    fields, existing = read_rows("nepse.csv")
    fmt = lambda v: "" if v is None else f"{v:g}" if isinstance(v, float) else str(v)
    for row in rows:
        existing.append({"date": date, **{k: fmt(v) for k, v in row.items()}})
    write_rows("nepse.csv", fields, existing, ("date", "index"))
    nepse = next((r for r in rows if r["index"].lower().startswith("nepse")), rows[0])
    return f"nepse: {len(rows)} indices for {date} (NEPSE {nepse['close']})"


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
    ap.add_argument("--only", choices=["forex", "bullion", "kalimati", "nepse", "headlines"], action="append")
    args = ap.parse_args()

    jobs = {
        "forex": lambda: update_forex(args.forex_from),
        "bullion": update_bullion,
        "kalimati": update_kalimati,
        "nepse": update_nepse,
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
