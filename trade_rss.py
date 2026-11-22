#!/usr/bin/env python3
"""Merge Iranian customs, export/import and trade news into one RSS 2.0 feed."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime, format_datetime
from html import unescape
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.parse import quote
import xml.etree.ElementTree as ET
import re

OUT = "trade-feed.xml"
SELF = "https://raw.githubusercontent.com/Alsafirco/qavanin-rss/main/trade-feed.xml"
KEYWORDS = [
    "گمرک", "صادرات", "واردات", "ترخیص", "تعرفه", "حقوق ورودی", "کد تعرفه",
    "ثبت سفارش", "تجارت خارجی", "بازرگانی", "کالای اساسی", "کارت بازرگانی",
    "مناطق آزاد", "مرز تجاری", "واردکننده", "صادرکننده", "مقررات صادرات", "مقررات واردات",
    "سازمان توسعه تجارت", "گمرک جمهوری اسلامی", "سامانه جامع تجارت", "بخشنامه گمرکی",
    "بندر تجاری", "ترانزیت کالا", "حمل‌ونقل بین‌المللی", "حمل و نقل بین‌المللی",
    "کشتیرانی تجاری", "کالاهای وارداتی", "کالاهای صادراتی",
    "trade", "customs", "export", "import", "tariff", "clearance", "freight", "cargo"
]
TELEGRAM_CHANNELS = [
    ("تلگرام - اتحادیه ملی کارگزاران گمرکی", "UnionofCustomsBrokers"),
    ("تلگرام - آخرین بخشنامه‌های بازرگانی و گمرکی", "yaldaregisterservices"),
    ("تلگرام - بخشنامه‌های جدید بازرگانی و گمرکی", "nashreghanoon"),
    ("تلگرام - مجله واردات و صادرات", "Import_Export"),
    ("تلگرام - راهکار تجارت پایا", "Rahkar_tejarat"),
    ("تلگرام - ایران ایمپکس", "iranimpex"),
    ("تلگرام - اطلاعات کسب‌وکار آنلاین", "Onlinebusinessinformationkhr"),
    ("تلگرام - اخبار گمرک", "Gomrok_news"),
    ("تلگرام - ترخیص‌کاران", "Tarkhis_Karan"),
    ("تلگرام - کنفدراسیون صادرات ایران", "iranexpconfederation"),
    ("تلگرام - گمرک و بازرگانی", "customs_commercial"),
    ("تلگرام - مرکز اخبار گمرکی", "CustomsNewsCenteral"),
    ("تلگرام - سفیر تست", "safirtest1"),
]

SOURCES = [
    ("ایرنا - اقتصاد", "https://www.irna.ir/rss/tp/20"),
    ("مهر - اقتصاد", "https://www.mehrnews.com/rss/tp/25"),
    ("ایسنا", "https://www.isna.ir/rss"),
    ("تسنیم - مهم‌ترین اخبار", "https://www.tasnimnews.ir/fa/rss/feed/0/0/8/1/TopStories"),
    ("باشگاه خبرنگاران جوان", "https://www.yjc.ir/fa/rss/allnews"),
    ("تابناک", "https://www.tabnak.ir/fa/rss/allnews"),
    ("خبرآنلاین", "https://www.khabaronline.ir/rss"),
    ("عصر ایران", "https://www.asriran.com/fa/rss/allnews"),
    ("اخبار گمرک - جست‌وجوی منابع رسمی", "https://news.google.com/rss/search?q=" + quote("site:irica.ir گمرک OR صادرات OR واردات") + "&hl=fa&gl=IR&ceid=IR:fa"),
    ("سازمان توسعه تجارت - اخبار", "https://news.google.com/rss/search?q=" + quote("site:tpo.ir صادرات OR واردات OR تجارت") + "&hl=fa&gl=IR&ceid=IR:fa"),
    ("مقررات و بخشنامه‌های تجارت", "https://news.google.com/rss/search?q=" + quote("ایران بخشنامه گمرکی OR تعرفه صادرات واردات") + "&hl=fa&gl=IR&ceid=IR:fa"),
]

class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)

def clean(value):
    if not value:
        return ""
    parser = TextOnly()
    try:
        parser.feed(unescape(value))
        value = " ".join(parser.parts)
    except Exception:
        pass
    return re.sub(r"\s+", " ", value).strip()

def child_text(node, names):
    for name in names:
        el = node.find(name)
        if el is not None and el.text:
            return el.text.strip()
    # namespace-tolerant fallback
    for el in list(node):
        if el.tag.split("}")[-1] in names and el.text:
            return el.text.strip()
    return ""

def parse_date(raw):
    if not raw:
        return datetime.now(timezone.utc)
    try:
        return parsedate_to_datetime(raw).astimezone(timezone.utc)
    except Exception:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)

def read_source(label, url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; IranTradeRSS/1.0)", "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    with urlopen(req, timeout=25) as response:
        data = response.read()
    root = ET.fromstring(data)
    found = []
    for node in root.iter():
        kind = node.tag.split("}")[-1]
        if kind not in ("item", "entry"):
            continue
        title = clean(child_text(node, ["title"]))
        link = child_text(node, ["link"])
        if not link:
            for el in list(node):
                if el.tag.split("}")[-1] == "link":
                    link = el.attrib.get("href", "")
                    if link:
                        break
        desc = clean(child_text(node, ["description", "summary", "content", "encoded"]))
        guid = child_text(node, ["guid", "id"]) or link
        date_raw = child_text(node, ["pubDate", "published", "updated", "date"])
        if title and link:
            haystack = (title + " " + desc).lower()
            if any(k.lower() in haystack for k in KEYWORDS):
                found.append({
                    "title": title, "link": link, "description": desc[:1200],
                    "guid": guid, "date": parse_date(date_raw), "source": label
                })
    return found


def read_telegram_channel(label, username):
    """Read recent public posts from Telegram's t.me/s/<channel> preview."""
    url = f"https://t.me/s/{username}"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; IranTradeRSS/1.0)"})
    with urlopen(req, timeout=25) as response:
        html = response.read().decode("utf-8", errors="replace")

    found = []
    # Telegram public previews wrap each post in a widget_message_wrap block.
    chunks = re.split(r'<div class="tgme_widget_message_wrap', html)
    for chunk in chunks[1:]:
        post_match = re.search(r'data-post="([^"]+)"', chunk)
        if not post_match:
            continue
        post_path = post_match.group(1)
        if "/" not in post_path:
            continue
        message_id = post_path.rsplit("/", 1)[-1]
        date_match = re.search(r'<time[^>]*datetime="([^"]+)"', chunk)
        text_match = re.search(
            r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
            chunk, re.S
        )
        if not text_match:
            continue
        message_html = text_match.group(1)
        desc = clean(message_html)
        if not desc:
            continue
        haystack = desc.lower()
        if not any(k.lower() in haystack for k in KEYWORDS):
            continue
        title = desc if len(desc) <= 180 else desc[:177].rsplit(" ", 1)[0] + "..."
        date_raw = date_match.group(1) if date_match else ""
        link = f"https://t.me/{post_path}"
        found.append({
            "title": title, "link": link, "description": desc[:1200],
            "guid": link, "date": parse_date(date_raw), "source": label
        })
    return found

def main():
    items, failed = [], []
    for label, url in SOURCES:
        try:
            batch = read_source(label, url)
            items.extend(batch)
            print(f"{label}: {len(batch)} matching items")
        except Exception as exc:
            failed.append((label, str(exc)))
            print(f"WARN {label}: {exc}")

    for label, username in TELEGRAM_CHANNELS:
        try:
            batch = read_telegram_channel(label, username)
            items.extend(batch)
            print(f"{label}: {len(batch)} matching posts")
        except Exception as exc:
            failed.append((label, str(exc)))
            print(f"WARN {label}: {exc}")

    unique = {}
    for item in items:
        key = item["link"].split("#")[0]
        if key not in unique or item["date"] > unique[key]["date"]:
            unique[key] = item
    ordered = sorted(unique.values(), key=lambda x: x["date"], reverse=True)[:150]

    ET.register_namespace("atom", "http://www.w3.org/2005/Atom")
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "RSS یکپارچه گمرک، صادرات و واردات ایران"
    ET.SubElement(channel, "link").text = "https://github.com/Alsafirco/qavanin-rss"
    ET.SubElement(channel, "description").text = "تجمیع اخبار مرتبط با گمرک، بخشنامه‌ها، صادرات، واردات، تعرفه‌ها، ترخیص، تجارت خارجی و لجستیک ایران"
    ET.SubElement(channel, "language").text = "fa"
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(datetime.now(timezone.utc))
    ET.SubElement(channel, "{http://www.w3.org/2005/Atom}link", href=SELF, rel="self", type="application/rss+xml")
    for entry in ordered:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = entry["title"]
        ET.SubElement(item, "link").text = entry["link"]
        ET.SubElement(item, "guid", isPermaLink="false").text = entry["guid"] or entry["link"]
        ET.SubElement(item, "pubDate").text = format_datetime(entry["date"])
        ET.SubElement(item, "category").text = entry["source"]
        ET.SubElement(item, "description").text = entry["description"] or entry["title"]

    ET.indent(rss, space="  ")
    ET.ElementTree(rss).write(OUT, encoding="utf-8", xml_declaration=True)
    print(f"Saved {len(ordered)} unique articles; {len(failed)} source failures.")
    if not ordered:
        raise SystemExit("No matching articles found. Keeping the workflow failed so it can be inspected.")

if __name__ == "__main__":
    main()
