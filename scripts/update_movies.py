"""Refresh the "Recently watched" section of README.md from a Letterboxd RSS feed.

The Letterboxd username comes from the LETTERBOXD_USER environment variable so it never
lives in the repo. Nothing user-identifying from the feed is written to the README: films
link to Letterboxd's public film pages, and posters come from its image CDN.
"""

from __future__ import annotations

import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"
START, END = "<!-- LETTERBOXD:START -->", "<!-- LETTERBOXD:END -->"
COUNT = 4
NS = {"letterboxd": "https://letterboxd.com"}


def fetch_feed(user: str) -> bytes:
    req = urllib.request.Request(
        f"https://letterboxd.com/{user}/rss/",
        headers={"User-Agent": "Mozilla/5.0 (profile-readme-updater)"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def stars(rating: str | None) -> str:
    if not rating:
        return ""
    value = float(rating)
    return "★" * int(value) + ("½" if value % 1 else "")


def parse_films(feed: bytes) -> list[dict]:
    films = []
    for item in ET.fromstring(feed).iter("item"):
        title = item.findtext("letterboxd:filmTitle", namespaces=NS)
        if not title:
            continue  # lists and other non-film entries
        slug = re.search(r"/film/([^/]+)/", item.findtext("link", ""))
        poster = re.search(r'<img src="([^"]+)"', item.findtext("description", ""))
        if not slug or not poster:
            continue
        films.append(
            {
                "title": title,
                "year": item.findtext("letterboxd:filmYear", "", NS),
                "url": f"https://letterboxd.com/film/{slug.group(1)}/",
                "poster": poster.group(1).replace("0-600-0-900", "0-300-0-450"),
                "stars": stars(item.findtext("letterboxd:memberRating", namespaces=NS)),
                "liked": item.findtext("letterboxd:memberLike", namespaces=NS) == "Yes",
            }
        )
        if len(films) == COUNT:
            break
    return films


def render(films: list[dict]) -> str:
    cells = []
    for f in films:
        label = escape(f"{f['title']} ({f['year']})")
        rating = f["stars"] + (" ♥" if f["liked"] else "")
        cells.append(
            f'    <td align="center" width="25%">\n'
            f'      <a href="{f["url"]}"><img src="{f["poster"]}" alt="{label}" width="120"></a><br>\n'
            f"      <sub>{label}</sub><br>\n"
            f"      <sub>{rating}</sub>\n"
            f"    </td>"
        )
    return "<table>\n  <tr>\n" + "\n".join(cells) + "\n  </tr>\n</table>"


def main() -> None:
    user = os.environ.get("LETTERBOXD_USER")
    if not user:
        sys.exit("LETTERBOXD_USER is not set")

    films = parse_films(fetch_feed(user))
    if not films:
        sys.exit("No films found in feed; leaving README unchanged")

    text = README.read_text()
    pattern = re.compile(re.escape(START) + ".*?" + re.escape(END), re.S)
    updated = pattern.sub(f"{START}\n{render(films)}\n{END}", text)
    README.write_text(updated)
    print("README updated" if updated != text else "No changes")


if __name__ == "__main__":
    main()
