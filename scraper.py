"""RADAR feed collector.

Reads every RADAR source (news sites, Telegram channels, international
organisations, Google News searches) and writes feed.json with the items
that are new in the last HOURS hours. seen.json remembers when each link
was first seen, so sites without publish times still get a "first seen" time.
"""
import json, os, datetime as dt
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus, urljoin
import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}
HOURS = 30
KEEP_SEEN_DAYS = 7

CHANNELS = ["bagramyan26", "HRAPARAKAM", "ArmenianVendetta", "caucasar"]

PAGES = {
    # Azerbaijan
    "azertag": "https://azertag.az",
    "apa": "https://apa.az",
    "report": "https://report.az",
    "qafqazinfo": "https://qafqazinfo.az",
    "caliber": "https://caliber.az",
    "haqqin": "https://haqqin.az",
    # Armenia (Armenian-language first)
    "news.am": "https://news.am/arm/",
    "armenpress-hy": "https://armenpress.am/hy",
    "armenpress-en": "https://armenpress.am/en",
    "azatutyun": "https://www.azatutyun.am",
    "tert": "https://www.tert.am/am",
    "hetq": "https://hetq.am/hy",
    "hraparak": "https://hraparak.am",
    "1in": "https://www.1in.am",
    "primeminister": "https://www.primeminister.am/en/press-release",
    # Region
    "civilnet": "https://www.civilnet.am/en",
    "oc-media": "https://oc-media.org",
    "jam-news": "https://jam-news.net",
    # International organisations
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

# Google News searches replace the web searches (results carry publish dates).
SEARCHES = [
    "Azerbaijan EU", "Armenia EU", "EUMA Armenia", "European Parliament Azerbaijan",
    "European Parliament Armenia", "PACE Azerbaijan", "PACE Armenia", "OSCE Azerbaijan",
    "OSCE Armenia", "NATO Azerbaijan", "NATO Armenia", "UN Azerbaijan", "UN Armenia",
    "Kallas Azerbaijan Armenia", "UNDP Azerbaijan", "UNDP Armenia",
    "intellinews Azerbaijan Armenia", "eurasianet Azerbaijan Armenia",
    "Азербайджан", "Армения", "ECHR Azerbaijan", "ECHR Armenia",
]

# Headline keywords (stems, lower-case) in Azerbaijani, English, Russian, Armenian.
KEYWORDS = [
    "azərbaycan", "azerbaij", "азербайдж", "ադրբեջ", "bakı", "baku", "баку", "բաքու",
    "ermənistan", "armenia", "армени", "հայաստան", "irəvan", "yerevan", "ереван", "երևան", "երեւան",
    "əliyev", "aliyev", "aliev", "алиев", "ալիև", "ալիեւ", "bayramov", "байрамов", "բայրամով",
    "hacıyev", "hajiyev", "гаджиев", "հաջիև", "paşinyan", "pashinyan", "pashinian", "пашинян", "փաշինյան",
    "mirzoyan", "мирзоян", "միրզոյան", "simonyan", "симонян", "սիմոնյան", "rubinyan", "рубинян", "ռուբինյան",
    "tripp", "trump route", "zəngəzur", "zangezur", "зангезур", "զանգեզուր", "թրամփի",
    "naxçıvan", "nakhchivan", "нахичев", "նախիջև", "նախիջեւ", "qarabağ", "karabakh", "карабах", "ղարաբաղ", "արցախ",
    "sülh", "peace", "мирн", "խաղաղ", "delimit", "делимит", "սահմանազատ", "demarcat", "демаркац", "սահմանագծ",
    "sərhəd", "border", "границ", "սահման", "vaşinqton", "washington", "вашингтон", "վաշինգտոն",
    "kallas", "калас", "կալաս", "euma", "pace", "пасе", "ԵԽԽՎ", "aşpa", "osce", "обсе", "եահկ", "atət",
    "nato", "нато", "նատօ", "echr", "еспч", "միեդ", "aihm", "aİhm",
]

now = dt.datetime.now(dt.timezone.utc)
cutoff = now - dt.timedelta(hours=HOURS)


def baku(t):
    return (t + dt.timedelta(hours=4)).strftime("%Y-%m-%d %H:%M")


def relevant(text):
    low = text.lower()
    return any(k.lower() in low for k in KEYWORDS)


def get(url):
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    return r.text


def telegram(channel):
    posts, before = [], None
    for _ in range(8):
        soup = BeautifulSoup(get(f"https://t.me/s/{channel}" + (f"?before={before}" if before else "")), "html.parser")
        msgs = [m for m in soup.select(".tgme_widget_message") if m.get("data-post") and m.select_one(".tgme_widget_message_date time")]
        if not msgs:
            break
        for m in msgs:
            when = dt.datetime.fromisoformat(m.select_one(".tgme_widget_message_date time")["datetime"])
            if when >= cutoff:
                txt = m.select_one(".tgme_widget_message_text")
                posts.append({
                    "id": int(m["data-post"].split("/")[-1]),
                    "url": "https://t.me/" + m["data-post"],
                    "time_baku": baku(when),
                    "text": txt.get_text("\n", strip=True)[:1500] if txt else "[media]",
                })
        first = dt.datetime.fromisoformat(msgs[0].select_one(".tgme_widget_message_date time")["datetime"])
        if first < cutoff:
            break
        before = min(int(m["data-post"].split("/")[-1]) for m in msgs)
    uniq = {p["id"]: p for p in posts}
    return sorted(uniq.values(), key=lambda p: p["id"])


def page_links(url):
    soup = BeautifulSoup(get(url), "html.parser")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        title = " ".join(a.get_text(" ", strip=True).split())
        href = urljoin(url, a["href"]).split("#")[0]
        if len(title) < 20 or href in seen or not href.startswith("http"):
            continue
        seen.add(href)
        out.append({"title": title[:300], "url": href})
    return out


def google_news(query):
    url = f"https://news.google.com/rss/search?q={quote_plus(query + ' when:2d')}&hl=en&gl=US&ceid=US:en"
    soup = BeautifulSoup(get(url), "xml")
    items = []
    for it in soup.find_all("item"):
        try:
            when = parsedate_to_datetime(it.pubDate.text)
        except Exception:
            continue
        if when >= cutoff:
            items.append({
                "title": it.title.text[:300],
                "url": it.link.text,
                "source": it.source.text if it.source else "",
                "time_baku": baku(when),
            })
    return items


seen = {}
if os.path.exists("seen.json"):
    with open("seen.json", encoding="utf-8") as f:
        seen = json.load(f)
first_run = not seen

out = {"generatedAt": now.isoformat(), "generatedAtBaku": baku(now), "hours": HOURS,
       "firstRun": first_run, "telegram": {}, "pages": {}, "search": {}, "errors": {}}

for ch in CHANNELS:
    try:
        out["telegram"][ch] = telegram(ch)
    except Exception as e:
        out["errors"]["telegram:" + ch] = str(e)[:300]

for key, url in PAGES.items():
    try:
        links = page_links(url)
        new = []
        for l in links:
            first = seen.setdefault(l["url"], now.isoformat())
            l["firstSeenBaku"] = baku(dt.datetime.fromisoformat(first))
            if dt.datetime.fromisoformat(first) >= cutoff and relevant(l["title"]):
                new.append(l)
        out["pages"][key] = {"url": url, "linksOnPage": len(links), "items": new}
        if not links:
            out["errors"][key] = "no links found (page may need JavaScript or blocks bots)"
    except Exception as e:
        out["errors"][key] = str(e)[:300]

for q in SEARCHES:
    try:
        out["search"][q] = google_news(q)
    except Exception as e:
        out["errors"]["search:" + q] = str(e)[:300]

keep_after = now - dt.timedelta(days=KEEP_SEEN_DAYS)
seen = {u: t for u, t in seen.items() if dt.datetime.fromisoformat(t) >= keep_after}
with open("seen.json", "w", encoding="utf-8") as f:
    json.dump(seen, f)
with open("feed.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)

print("telegram:", {k: len(v) for k, v in out["telegram"].items()})
print("pages:", {k: len(v["items"]) for k, v in out["pages"].items()})
print("search:", sum(len(v) for v in out["search"].values()), "errors:", list(out["errors"]))
