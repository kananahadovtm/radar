"""RADAR feed collector: reads public Telegram channels and news pages, writes feed.json."""
import json, re, datetime as dt
import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (RADAR feed collector)"}
HOURS = 30  # keep posts from the last 30 hours
CHANNELS = ["bagramyan26", "HRAPARAKAM", "ArmenianVendetta", "caucasar"]
PAGES = {
    "armenpress-hy": "https://armenpress.am/hy",
    "armenpress-en": "https://armenpress.am/en",
    "primeminister": "https://www.primeminister.am/en/press-release",
    "caliber": "https://caliber.az",
    "azatutyun": "https://www.azatutyun.am",
    "jam-news": "https://jam-news.net",
    "hraparak": "https://hraparak.am",
    "eeas-press": "https://www.eeas.europa.eu/eeas/press-material_en",
    "eeas-azerbaijan": "https://www.eeas.europa.eu/delegations/azerbaijan_en",
    "eeas-armenia": "https://www.eeas.europa.eu/delegations/armenia_en",
    "euma": "https://www.eeas.europa.eu/euma_en",
    "europarl": "https://www.europarl.europa.eu/news/en/press-room",
    "pace": "https://pace.coe.int/en/news",
    "osce": "https://www.osce.org/news",
    "nato": "https://www.nato.int/en/news-and-events",
    "un-press": "https://press.un.org/en",
    "un-azerbaijan": "https://azerbaijan.un.org",
    "un-armenia": "https://armenia.un.org",
    "undp-azerbaijan": "https://www.undp.org/azerbaijan",
    "undp-armenia": "https://www.undp.org/armenia",
}

now = dt.datetime.now(dt.timezone.utc)
cutoff = now - dt.timedelta(hours=HOURS)


def telegram(channel):
    posts, before = [], None
    for _ in range(6):  # at most 6 pages back
        url = f"https://t.me/s/{channel}" + (f"?before={before}" if before else "")
        soup = BeautifulSoup(requests.get(url, headers=UA, timeout=30).text, "html.parser")
        msgs = soup.select(".tgme_widget_message")
        if not msgs:
            break
        oldest = None
        for m in msgs:
            post = m.get("data-post", "")
            t = m.select_one(".tgme_widget_message_date time")
            if not post or not t:
                continue
            when = dt.datetime.fromisoformat(t["datetime"])
            pid = int(post.split("/")[-1])
            oldest = pid if oldest is None else min(oldest, pid)
            if when >= cutoff:
                txt = m.select_one(".tgme_widget_message_text")
                posts.append({
                    "id": pid,
                    "url": f"https://t.me/{post}",
                    "time_utc": when.isoformat(),
                    "time_baku": (when + dt.timedelta(hours=4)).strftime("%Y-%m-%d %H:%M"),
                    "text": txt.get_text("\n", strip=True)[:1500] if txt else "",
                })
        first = dt.datetime.fromisoformat(msgs[0].select_one(".tgme_widget_message_date time")["datetime"])
        if first < cutoff or oldest is None:
            break
        before = oldest
    uniq = {p["id"]: p for p in posts}
    return sorted(uniq.values(), key=lambda p: p["id"])


def page(url):
    soup = BeautifulSoup(requests.get(url, headers=UA, timeout=30).text, "html.parser")
    links, seen = [], set()
    for a in soup.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).split())
        href = requests.compat.urljoin(url, a["href"])
        if len(text) < 25 or href in seen or not href.startswith("http"):
            continue
        seen.add(href)
        links.append({"title": text[:300], "url": href})
    return links[:120]


out = {"generatedAt": now.isoformat(), "hours": HOURS, "telegram": {}, "pages": {}, "errors": {}}
for ch in CHANNELS:
    try:
        out["telegram"][ch] = telegram(ch)
    except Exception as e:  # keep going if one source fails
        out["errors"][ch] = str(e)[:300]
for key, url in PAGES.items():
    try:
        out["pages"][key] = {"url": url, "links": page(url)}
    except Exception as e:
        out["errors"][key] = str(e)[:300]

with open("feed.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("telegram:", {k: len(v) for k, v in out["telegram"].items()}, "errors:", list(out["errors"]))

