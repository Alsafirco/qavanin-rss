#!/usr/bin/env python3
"""Build a persistent RSS 2.0 feed from public Telegram channel previews."""

import email.utils
import html
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

CHANNELS = (
    "Gomruk_news",
    "customs_commercial",
    "Onlinebusinessinformationkhr",
)
OUTPUT = Path("customs_circulars.xml")
MAX_ITEMS = 100
MAX_FEED_BYTES = 1024 * 1024
MAX_PDF_BYTES = 20 * 1024 * 1024
TIMEOUT_SECONDS = 20
RETRIES = 3
USER_AGENT = (
    "Mozilla/5.0 (compatible; CustomsCircularsRSS/1.0; "
    "+https://github.com/Alsafirco/qavanin-rss)"
)


def fetch(url, limit=8 * 1024 * 1024):
    """GET with a 20-second timeout and three total attempts."""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/pdf,*/*",
        },
    )
    last_error = None
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                data = response.read(limit + 1)
                if len(data) > limit:
                    raise ValueError("response exceeds configured size limit")
                return data
        except Exception as exc:
            last_error = exc
            if attempt + 1 < RETRIES:
                time.sleep(attempt + 1)
    raise RuntimeError(f"GET failed after {RETRIES} attempts: {url}: {last_error}")


def plain_text(fragment, limit):
    fragment = re.sub(r"<br\\s*/?>", " ", fragment, flags=re.I)
    fragment = re.sub(r"<[^>]*>", " ", fragment)
    fragment = html.unescape(fragment)
    return re.sub(r"\\s+", " ", fragment).strip()[:limit]


def parse_telegram_page(channel, page):
    """Parse each Telegram widget message using its stable data-post identifier."""
    source = page.decode("utf-8", errors="replace")
    starts = list(re.finditer(
        r'<div\\b(?=[^>]*\\bdata-post="([^"]+)")(?=[^>]*\\bclass="[^"]*tgme_widget_message)',
        source,
        flags=re.I,
    ))
    posts = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(source)
        block = source[match.start():end]
        post_path = html.unescape(match.group(1))
        path_match = re.fullmatch(r"([A-Za-z0-9_]+)/([0-9]+)", post_path)
        if not path_match:
            continue

        body_match = re.search(
            r'<div\\b[^>]*class="[^"]*tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
            block,
            flags=re.I | re.S,
        )
        if not body_match:
            continue
        description = plain_text(body_match.group(1), 5000)
        if not description:
            continue

        date_match = re.search(
            r'<time\\b[^>]*datetime="([^"]+)"',
            block,
            flags=re.I,
        )
        if not date_match:
            # pubDate must be the post's own timestamp; do not substitute run time.
            continue
        try:
            published = datetime.fromisoformat(
                date_match.group(1).replace("Z", "+00:00")
            )
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            published = published.astimezone(timezone.utc)
        except ValueError:
            continue

        pdf_url = None
        for href in re.findall(r'<a\\b[^>]*href="([^"]+)"', block, flags=re.I):
            href = urllib.parse.urljoin("https://t.me/", html.unescape(href))
            if urllib.parse.urlparse(href).path.lower().endswith(".pdf"):
                pdf_url = href
                break

        link = f"https://t.me/{path_match.group(1)}/{path_match.group(2)}"
        posts.append({
            "title": description[:500],
            "description": description,
            "link": link,
            "pubDate": email.utils.format_datetime(published),
            "pdf": pdf_url,
            "_published": published,
        })

    if not posts:
        raise RuntimeError(f"no usable posts found for @{channel}")
    return posts


def fetch_channel(channel):
    url = f"https://t.me/s/{urllib.parse.quote(channel)}"
    return parse_telegram_page(channel, fetch(url))


def valid_pdf(url):
    """Keep only direct, public PDF URLs whose body is at most 20 MB."""
    if not url:
        return None
    try:
        data = fetch(url, limit=MAX_PDF_BYTES)
        if not data.startswith(b"%PDF"):
            return None
        return url
    except Exception as exc:
        print(f"WARNING: PDF omitted ({url}): {exc}", file=sys.stderr)
        return None


def parse_pubdate(value):
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def read_previous():
    if not OUTPUT.exists():
        return []
    try:
        root = ET.parse(OUTPUT).getroot()
        result = []
        for node in root.findall("./channel/item"):
            link = (node.findtext("link") or "").strip()
            if not link.startswith("https://t.me/"):
                continue
            pubdate = node.findtext("pubDate")
            published = parse_pubdate(pubdate)
            if published is None:
                continue
            enclosure = node.find("enclosure")
            pdf = enclosure.get("url") if enclosure is not None else None
            result.append({
                "title": (node.findtext("title") or "Telegram post")[:500],
                "description": (node.findtext("description") or "")[:5000],
                "link": link,
                "pubDate": email.utils.format_datetime(published),
                "pdf": pdf,
                "_published": published,
            })
        return result
    except Exception as exc:
        # Never replace a potentially recoverable previous feed after a parse error.
        raise RuntimeError(f"existing feed is invalid; refusing to overwrite: {exc}")


def content_signature(xml_bytes):
    root = ET.fromstring(xml_bytes)
    channel = root.find("channel")
    if channel is None:
        raise ValueError("RSS channel element is missing")
    build_date = channel.find("lastBuildDate")
    if build_date is not None:
        channel.remove(build_date)
    return ET.tostring(root, encoding="utf-8")


def render(items):
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Customs Circulars"
    ET.SubElement(channel, "link").text = (
        "https://github.com/Alsafirco/qavanin-rss"
    )
    ET.SubElement(channel, "description").text = (
        "Customs and commercial notices from selected public Telegram channels"
    )
    ET.SubElement(channel, "lastBuildDate").text = email.utils.format_datetime(
        datetime.now(timezone.utc)
    )

    for item in items[:MAX_ITEMS]:
        node = ET.SubElement(channel, "item")
        ET.SubElement(node, "title").text = item["title"][:500]
        ET.SubElement(node, "link").text = item["link"]
        ET.SubElement(node, "guid", {"isPermaLink": "true"}).text = item["link"]
        ET.SubElement(node, "pubDate").text = item["pubDate"]
        ET.SubElement(node, "description").text = item["description"][:5000]
        if item.get("pdf"):
            ET.SubElement(node, "enclosure", {
                "url": item["pdf"],
                "type": "application/pdf",
                "length": "0",
            })

    data = ET.tostring(rss, encoding="utf-8", xml_declaration=True)
    data = data.replace(
        b"<?xml version='1.0' encoding='utf-8'?>",
        b'<?xml version="1.0" encoding="UTF-8"?>',
        1,
    )
    if len(data) >= MAX_FEED_BYTES:
        raise ValueError(f"RSS exceeds 1 MB ({len(data)} bytes)")
    ET.fromstring(data)  # Parse/validate before writing anything.
    return data


def main():
    try:
        previous = read_previous()
    except Exception as exc:
        print(exc, file=sys.stderr)
        return 1

    fresh = []
    successes = 0
    for channel in CHANNELS:
        try:
            posts = fetch_channel(channel)
            successes += 1
            for post in posts:
                post["pdf"] = valid_pdf(post.get("pdf"))
            fresh.extend(posts)
            print(f"OK @{channel}: {len(posts)} posts")
        except Exception as exc:
            # A failed channel must not prevent the other sources from running.
            print(f"ERROR @{channel}: {exc}", file=sys.stderr)

    if successes == 0:
        print("All sources failed; existing RSS left untouched.", file=sys.stderr)
        return 1

    merged = {}
    for item in previous + fresh:
        link = item["link"]
        # The Telegram post URL is the sole stable deduplication key.
        if link not in merged or item in fresh:
            merged[link] = item

    items = sorted(
        merged.values(),
        key=lambda item: item["_published"],
        reverse=True,
    )[:MAX_ITEMS]

    if not items:
        print("No usable items; existing RSS left untouched.", file=sys.stderr)
        return 1

    for item in items:
        item.pop("_published", None)

    try:
        new_data = render(items)
        # Validate a second time immediately before any file operation.
        ET.fromstring(new_data)
        if OUTPUT.exists():
            old_data = OUTPUT.read_bytes()
            try:
                if content_signature(old_data) == content_signature(new_data):
                    print("No content changes; RSS file not rewritten.")
                    return 0
            except ET.ParseError:
                # A malformed previous file is not overwritten.
                print("Existing RSS is malformed; refusing to overwrite.", file=sys.stderr)
                return 1
    except Exception as exc:
        print(f"RSS generation/validation failed; old file preserved: {exc}", file=sys.stderr)
        return 1

    fd, temp_name = tempfile.mkstemp(
        prefix="customs-rss-", suffix=".xml", dir=str(OUTPUT.parent)
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(new_data)
            handle.flush()
            os.fsync(handle.fileno())
        ET.parse(temp_name)
        os.replace(temp_name, OUTPUT)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)

    print(f"Updated {OUTPUT}: {len(items)} items, {len(new_data)} bytes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
