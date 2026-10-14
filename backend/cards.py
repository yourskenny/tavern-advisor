import hashlib
import json
import os
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import httpx

DATA_DIR = Path(os.environ.get("TAVERN_DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
CATALOG_FILE = DATA_DIR / "cards.json"


class Catalog:
    def __init__(self, path: Path = CATALOG_FILE):
        self.path = path
        self.cards: dict[str, dict] = {}
        self.metadata: dict = {}
        self.reload()

    def reload(self):
        if self.path.exists():
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self.metadata = payload["metadata"]
            self.cards = {card["id"]: card for card in payload["cards"]}

    def get(self, card_id: str) -> dict:
        return self.cards.get(card_id, {})


def sync_catalog(build: str = "latest", path: Path = CATALOG_FILE) -> dict:
    if build != "latest" and not build.isdecimal():
        raise ValueError("build must be latest or a numeric client build")
    requested_build = build
    with httpx.Client(follow_redirects=True, timeout=120) as client:
        if build == "latest":
            index = client.get("https://api.hearthstonejson.com/v1/latest/")
            index.raise_for_status()
            class BuildLinks(HTMLParser):
                builds: set[str]
                def __init__(self):
                    super().__init__()
                    self.builds = set()
                def handle_starttag(self, tag, attrs):
                    if tag != "a":
                        return
                    href = dict(attrs).get("href", "")
                    parts = urlparse(href).path.strip("/").split("/")
                    if len(parts) >= 2 and parts[0] == "v1" and parts[1].isdecimal():
                        self.builds.add(parts[1])
            links = BuildLinks()
            links.feed(index.text)
            if len(links.builds) != 1:
                raise ValueError("Could not resolve latest build; provide --build explicitly")
            build = links.builds.pop()
        url = f"https://api.hearthstonejson.com/v1/{build}/zhCN/cards.json"
        response = client.get(url)
        response.raise_for_status()
    cards = response.json()
    if not isinstance(cards, list) or not cards or not all("id" in c for c in cards):
        raise ValueError("Invalid card catalog")
    resolved = response.url.path.split("/")[2]
    metadata = {"url": str(response.url), "requested_build": requested_build, "build": resolved,
                "sha256": hashlib.sha256(response.content).hexdigest(), "locale": "zhCN",
                "count": len(cards), "pool_verified": False}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"metadata": metadata, "cards": cards}, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
    return metadata
