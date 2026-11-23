#!/usr/bin/env python3
"""Build one RSS 2.0 feed from public Telegram channels via RSSHub."""
import datetime as dt
import email.utils
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

CHANNELS = {
    "Tarkhis Karan": "https://rsshub.app/telegram/channel/Tarkhis_Karan",
    "Customs Commercial": "https://rsshub.app/telegram/channel/customs_commercial",
    "Online Business Information Khorasan": "https://rsshub.app/telegram/channel/Onlinebusinessinformationkhr",
}
ATOM = "{http://www.w3.org/2005/Atom}"
items = []
successes = 0
errors = []

for source_name, url in CHANNELS.items():
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SafirTelegramRSS/1.0 (+https://github.com/Alsafirco/qavanin-rss)", "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
        with urllib.request.urlopen(req, timeout=35) as response:
            payload = response.read()
        root = ET.fromstring(payload)
        channel = root.find("channel")
        if channel is not None:
            entries = channel.findall("item")
            for entry in entries:
                title = (entry.findtext("title") or "").strip()
                link = (entry.findtext("link") or "").strip()
                guid = (entry.findtext("guid") or link or title).strip()
                pub = (entry.findtext("pubDate") or "").strip()
                desc = (entry.findtext("description") or "").strip()
                if title and link:
                    items.append({"title": title, "link": link, "guid": guid, "date": pub, "description": desc, "source": source_name})
        else:
            entries = root.findall(f".//{ATOM}entry")
            for entry in entries:
                title = (entry.findtext(f"{ATOM}title") or "").strip()
                link_el = entry.find(f"{ATOM}link")
                link = (link_el.get("href", "") if link_el is not None else "").strip()
                guid = (entry.findtext(f"{ATOM}id") or link or title).strip()
                pub = (entry.findtext(f"{ATOM}published") or entry.findtext(f"{ATOM}updated") or "").strip()
                desc = (entry.findtext(f"{ATOM}summary") or entry.findtext(f"{ATOM}content") or "").strip()
                if title and link:
                    items.append({"title": title, "link": link, "guid": guid, "date": pub, "description": desc, "source": source_name})
        successes += 1
    except Exception as exc:
        errors.append(f"{source_name}: {exc}")

if successes == 0:
    raise SystemExit("No Telegram feed could be fetched; preserving the previously published feed. " + " | ".join(errors))

def timestamp(value):
    if not value:
        return 0
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        return parsed.timestamp()
    except Exception:
        try:
            return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except Exception:
            return 0

deduped = {}
for item in items:
    deduped[item["guid"]] = item
items = sorted(deduped.values(), key=lambda x: timestamp(x["date"]), reverse=True)[:100]

rss = ET.Element("rss", {"version": "2.0"})
channel = ET.SubElement(rss, "channel")
ET.SubElement(channel, "title").text = "اخبار ترخیص و تجارت | سه کانال تلگرام"
ET.SubElement(channel, "link").text = "https://github.com/Alsafirco/qavanin-rss"
ET.SubElement(channel, "description").text = "خوراک تجمیعی کانال‌های تلگرام ترخیص‌کاران، گمرک و تجارت"
ET.SubElement(channel, "language").text = "fa"
ET.SubElement(channel, "lastBuildDate").text = email.utils.formatdate(usegmt=True)
for item in items:
    node = ET.SubElement(channel, "item")
    ET.SubElement(node, "title").text = f'[{item["source"]}] {item["title"]}'
    ET.SubElement(node, "link").text = item["link"]
    ET.SubElement(node, "guid", {"isPermaLink": "false"}).text = item["guid"]
    if item["date"]:
        ET.SubElement(node, "pubDate").text = item["date"]
    if item["description"]:
        ET.SubElement(node, "description").text = item["description"]

ET.indent(rss, space="  ")
Path("telegram-feed.xml").write_bytes(b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(rss, encoding="utf-8"))
print(f"Fetched {successes}/{len(CHANNELS)} channels; published {len(items)} items.")
if errors:
    print("Partial source failures: " + " | ".join(errors))

# Dedicated feed for Yalda Register Services.
yalda_url = "https://rsshub.app/telegram/channel/YaldaRegisterServices"
try:
    req = urllib.request.Request(yalda_url, headers={"User-Agent": "SafirTelegramRSS/1.0", "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    with urllib.request.urlopen(req, timeout=35) as response:
        yalda_root = ET.fromstring(response.read())
    yalda_channel = yalda_root.find("channel")
    yalda_entries = yalda_channel.findall("item") if yalda_channel is not None else yalda_root.findall(f".//{ATOM}entry")
    yalda_rss = ET.Element("rss", {"version": "2.0"})
    yc = ET.SubElement(yalda_rss, "channel")
    ET.SubElement(yc, "title").text = "Yalda Register Services"
    ET.SubElement(yc, "link").text = "https://t.me/YaldaRegisterServices"
    ET.SubElement(yc, "description").text = "خوراک RSS مستقل کانال YaldaRegisterServices"
    ET.SubElement(yc, "language").text = "fa"
    ET.SubElement(yc, "lastBuildDate").text = email.utils.formatdate(usegmt=True)
    for entry in yalda_entries[:100]:
        if yalda_channel is not None:
            title = (entry.findtext("title") or "").strip()
            link = (entry.findtext("link") or "").strip()
            guid = (entry.findtext("guid") or link or title).strip()
            pub = (entry.findtext("pubDate") or "").strip()
            desc = (entry.findtext("description") or "").strip()
        else:
            title = (entry.findtext(f"{ATOM}title") or "").strip()
            le = entry.find(f"{ATOM}link")
            link = (le.get("href", "") if le is not None else "").strip()
            guid = (entry.findtext(f"{ATOM}id") or link or title).strip()
            pub = (entry.findtext(f"{ATOM}published") or entry.findtext(f"{ATOM}updated") or "").strip()
            desc = (entry.findtext(f"{ATOM}summary") or entry.findtext(f"{ATOM}content") or "").strip()
        if title and link:
            node = ET.SubElement(yc, "item")
            ET.SubElement(node, "title").text = title
            ET.SubElement(node, "link").text = link
            ET.SubElement(node, "guid", {"isPermaLink": "false"}).text = guid
            if pub:
                ET.SubElement(node, "pubDate").text = pub
            if desc:
                ET.SubElement(node, "description").text = desc
    ET.indent(yalda_rss, space="  ")
    Path("yalda-register-services.xml").write_bytes(b'<?xml version="1.0" encoding="UTF-8"?>\\n' + ET.tostring(yalda_rss, encoding="utf-8"))
    print(f"Yalda Register Services: published {len(yc.findall('item'))} items.")
except Exception as exc:
    print(f"Yalda Register Services feed unavailable; keeping last published feed: {exc}")
