#!/usr/bin/env python3
"""Build an RSS feed from the latest published items on qavanin.ir."""
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.parse import urljoin
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
import os

SOURCE = "https://qavanin.ir/"
FEED_TITLE = "تازه‌ترین قوانین و مقررات | سامانه ملی قوانین و مقررات"
FEED_DESCRIPTION = "آخرین اسناد و مقررات منتشرشده در سامانه ملی قوانین و مقررات جمهوری اسلامی ایران"

class ListingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_row = False
        self.in_cell = False
        self.in_anchor = False
        self.row = []
        self.rows = []
        self.anchor_text = []
        self.anchor_href = None
        self.cell_text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr":
            self.in_row = True
            self.row = []
        elif self.in_row and tag in ("td", "th"):
            self.in_cell = True
            self.cell_text = []
        elif self.in_row and self.in_cell and tag == "a":
            self.in_anchor = True
            self.anchor_href = attrs.get("href")
            self.anchor_text = []

    def handle_data(self, data):
        if self.in_anchor:
            self.anchor_text.append(data)
        if self.in_row and self.in_cell:
            self.cell_text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.in_anchor:
            title = " ".join("".join(self.anchor_text).split())
            if title and self.anchor_href:
                self.row.append((title, self.anchor_href))
            self.in_anchor = False
        elif tag in ("td", "th") and self.in_cell:
            self.in_cell = False
        elif tag == "tr" and self.in_row:
            if self.row:
                self.rows.append(self.row)
            self.in_row = False

def main():
    req = Request(SOURCE, headers={"User-Agent": "QavaninRSS/1.0 (+https://github.com/Alsafirco/qavanin-rss)"})
    with urlopen(req, timeout=40) as response:
        html = response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")

    parser = ListingParser()
    parser.feed(html)
    seen, items = set(), []
    for row in parser.rows:
        # Listing pages contain a linked document title in each result row.
        title, href = max(row, key=lambda pair: len(pair[0]))
        link = urljoin(SOURCE, href)
        if not link.startswith(SOURCE) or link in seen:
            continue
        if len(title) < 8:
            continue
        seen.add(link)
        items.append((title, link))
        if len(items) >= 40:
            break

    if not items:
        raise RuntimeError("No document links found; the source page layout may have changed.")

    rss = ET.Element("rss", version="2.0", attrib={"xmlns:atom": "http://www.w3.org/2005/Atom"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = FEED_TITLE
    ET.SubElement(channel, "link").text = SOURCE
    ET.SubElement(channel, "description").text = FEED_DESCRIPTION
    ET.SubElement(channel, "language").text = "fa"
    ET.SubElement(channel, "lastBuildDate").text = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    ET.SubElement(channel, "{http://www.w3.org/2005/Atom}link", href="https://raw.githubusercontent.com/Alsafirco/qavanin-rss/main/feed.xml", rel="self", type="application/rss+xml")
    for title, link in items:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = title
        ET.SubElement(item, "link").text = link
        ET.SubElement(item, "guid", isPermaLink="true").text = link
        ET.SubElement(item, "description").text = title

    ET.indent(rss, space="  ")
    ET.ElementTree(rss).write("feed.xml", encoding="utf-8", xml_declaration=True)
    print(f"Wrote {len(items)} items to feed.xml")

if __name__ == "__main__":
    main()
