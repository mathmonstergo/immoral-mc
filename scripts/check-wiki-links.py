#!/usr/bin/env python3
"""Validate language, discoverability, and local links in the public Wiki."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT / "docs" / "wiki"
INDEX = WIKI / "index.md"
LINK_PATTERN = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
HEADING_PATTERN = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$")
CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
CHECKED_READMES = (
    ROOT / "README.md",
    ROOT / "game-service" / "README.md",
    ROOT / "minecraft-nodes" / "main-plugin" / "README.md",
    ROOT / "minecraft-nodes" / "main-server" / "README.md",
)


def markdown_links(path: Path) -> tuple[str, ...]:
    links: list[str] = []
    for raw_target in LINK_PATTERN.findall(path.read_text(encoding="utf-8")):
        target = raw_target.strip()
        if target.startswith("<") and target.endswith(">"):
            target = target[1:-1]
        if " " in target:
            target = target.split(" ", 1)[0]
        links.append(target)
    return tuple(links)


def markdown_headings(path: Path) -> tuple[tuple[int, str], ...]:
    headings: list[tuple[int, str]] = []
    fence_marker: str | None = None
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        stripped = line.lstrip()
        marker = (
            "```"
            if stripped.startswith("```")
            else "~~~"
            if stripped.startswith("~~~")
            else None
        )
        if marker is not None:
            if fence_marker == marker:
                fence_marker = None
            elif fence_marker is None:
                fence_marker = marker
            continue
        if fence_marker is not None:
            continue
        if match := HEADING_PATTERN.match(line):
            headings.append((line_number, match.group(1)))
    return tuple(headings)


def local_target(source: Path, target: str) -> Path | None:
    if target.startswith("#"):
        return source
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return None
    path = unquote(parsed.path)
    if not path:
        return source
    if path.startswith("/"):
        return ROOT / path.removeprefix("/")
    return (source.parent / path).resolve()


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    errors: list[str] = []
    wiki_pages = tuple(sorted(WIKI.rglob("*.md")))
    required_files = (INDEX, *CHECKED_READMES)
    for required in required_files:
        if not required.is_file():
            errors.append(f"missing required documentation entry: {display(required)}")

    sources = tuple(page for page in (*wiki_pages, *CHECKED_READMES) if page.is_file())
    for source in sources:
        for target in markdown_links(source):
            resolved = local_target(source, target)
            if resolved is not None and not resolved.exists():
                errors.append(
                    f"broken local link in {display(source)}: {target} -> {display(resolved)}"
                )

    for page in wiki_pages:
        for line_number, heading in markdown_headings(page):
            if not CJK_PATTERN.search(heading):
                errors.append(
                    "public Wiki heading must contain Chinese text: "
                    f"{display(page)}:{line_number}: {heading}"
                )

    index_targets = (
        {
            resolved
            for target in markdown_links(INDEX)
            if (resolved := local_target(INDEX, target)) is not None
        }
        if INDEX.is_file()
        else set()
    )
    for page in wiki_pages:
        if page != INDEX and page.resolve() not in index_targets:
            errors.append(
                f"Wiki page is not linked directly from docs/wiki/index.md: {display(page)}"
            )

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        f"Wiki check passed: {len(wiki_pages)} pages, Chinese headings, "
        "index coverage, and local links verified."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
