from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .fetch import fetch_html
from .parser import parse_substack_html, slugify


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="substack2md",
        description="Convert a public Substack post URL or local HTML file to Markdown.",
    )
    parser.add_argument("source", help="Substack URL, or a local .html file with --from-file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output Markdown file. Defaults to <post-slug>.md.",
    )
    parser.add_argument(
        "--from-file",
        action="store_true",
        help="Read source as a local HTML file instead of fetching it as a URL.",
    )
    args = parser.parse_args(argv)

    source_path = Path(args.source)
    if args.from_file or source_path.exists():
        html = source_path.read_text(encoding="utf-8")
        source_url = None
    else:
        html = fetch_html(args.source)
        source_url = args.source

    post = parse_substack_html(html, source_url=source_url)
    output = args.output or Path(f"{slugify(post.metadata.title)}.md")
    output.write_text(post.markdown, encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
