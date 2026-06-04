from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Comment, NavigableString, Tag


@dataclass(frozen=True)
class PostMetadata:
    title: str
    subtitle: str | None
    author: str | None
    date: str | None
    canonical_url: str | None
    hero_image: str | None


@dataclass(frozen=True)
class ParsedPost:
    metadata: PostMetadata
    markdown: str


def parse_substack_html(html: str, source_url: str | None = None) -> ParsedPost:
    soup = BeautifulSoup(html, "html.parser")
    metadata = _extract_metadata(soup, source_url)
    body = _find_body(soup)
    footnotes = _extract_footnotes(body)
    renderer = MarkdownRenderer(metadata.canonical_url or source_url, footnotes)

    body_markdown = renderer.render_blocks(body)
    parts = [_render_frontmatter(metadata), f"# {metadata.title}", ""]
    if metadata.subtitle:
        parts.extend([f"*{metadata.subtitle}*", ""])
    parts.append(body_markdown)

    note_markdown = renderer.render_footnote_definitions()
    if note_markdown:
        parts.extend(["", note_markdown])

    markdown = "\n".join(part for part in parts if part is not None).strip() + "\n"
    return ParsedPost(metadata=metadata, markdown=markdown)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug or "substack-post"


def _extract_metadata(soup: BeautifulSoup, source_url: str | None) -> PostMetadata:
    article_data = _find_news_article_json_ld(soup)
    canonical_url = _text(article_data.get("url")) or _attr(soup, 'link[rel="canonical"]', "href") or source_url
    title = (
        _text(article_data.get("headline"))
        or _select_text(soup, "article.newsletter-post h1.post-title")
        or _meta(soup, "property", "og:title")
        or "Untitled Substack Post"
    )
    subtitle = (
        _select_text(soup, "article.newsletter-post h3.subtitle")
        or _text(article_data.get("description"))
        or _meta(soup, "name", "description")
    )
    author = _author_name(article_data.get("author")) or _meta(soup, "name", "author")
    date = _date_only(_text(article_data.get("datePublished")) or _meta(soup, "property", "article:published_time"))
    hero_image = _image_url(article_data.get("image")) or _meta(soup, "property", "og:image")
    return PostMetadata(
        title=title,
        subtitle=subtitle,
        author=author,
        date=date,
        canonical_url=canonical_url,
        hero_image=hero_image,
    )


def _find_news_article_json_ld(soup: BeautifulSoup) -> dict[str, Any]:
    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except json.JSONDecodeError:
            continue
        entries = data if isinstance(data, list) else [data]
        for entry in entries:
            if isinstance(entry, dict) and entry.get("@type") in {"NewsArticle", "Article", "BlogPosting"}:
                return entry
    return {}


def _find_body(soup: BeautifulSoup) -> Tag:
    body = soup.select_one("article.newsletter-post div.body.markup")
    if body:
        return body
    body = soup.select_one("div.available-content div.body.markup")
    if body:
        return body
    raise ValueError("Could not find Substack article body")


def _extract_footnotes(body: Tag) -> dict[str, Tag]:
    footnotes: dict[str, Tag] = {}
    for footnote in body.select('div.footnote[data-component-name="FootnoteToDOM"], div.footnote'):
        number_node = footnote.select_one("a.footnote-number")
        content = footnote.select_one(".footnote-content")
        if not number_node or not content:
            continue
        number = number_node.get_text(strip=True)
        if number:
            footnotes[number] = content
    return footnotes


def _render_frontmatter(metadata: PostMetadata) -> str:
    fields = [
        ("title", metadata.title),
        ("subtitle", metadata.subtitle),
        ("author", metadata.author),
        ("date", metadata.date),
        ("canonical_url", metadata.canonical_url),
        ("source", "substack"),
        ("hero_image", metadata.hero_image),
    ]
    lines = ["---"]
    for key, value in fields:
        if value:
            lines.append(f"{key}: {_yaml_string(value)}")
    lines.append("---")
    return "\n".join(lines)


def _yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


class MarkdownRenderer:
    def __init__(self, base_url: str | None, footnotes: dict[str, Tag]):
        self.base_url = base_url
        self.footnotes = footnotes

    def render_blocks(self, parent: Tag) -> str:
        blocks: list[str] = []
        for child in parent.children:
            block = self.render_block(child)
            if block:
                blocks.append(block)
        return "\n\n".join(blocks).strip()

    def render_footnote_definitions(self) -> str:
        definitions: list[str] = []
        for number in sorted(self.footnotes, key=_footnote_sort_key):
            content = self.render_blocks(self.footnotes[number])
            content = " ".join(content.splitlines()).strip()
            if content:
                definitions.append(f"[^{number}]: {content}")
        return "\n".join(definitions)

    def render_block(self, node: Tag | NavigableString) -> str:
        if isinstance(node, Comment):
            return ""
        if isinstance(node, NavigableString):
            return self._clean_text(str(node))
        if self._should_drop(node):
            return ""

        name = node.name.lower()
        if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(name[1])
            return f"{'#' * level} {self.render_inline_children(node).strip()}"
        if name == "p":
            return self.render_inline_children(node).strip()
        if name == "blockquote":
            text = self.render_blocks(node) or self.render_inline_children(node)
            return "\n".join(f"> {line}" if line else ">" for line in text.splitlines())
        if name in {"ul", "ol"}:
            return self._render_list(node, ordered=name == "ol")
        if name == "pre":
            code = node.get_text("\n").strip("\n")
            return f"```\n{code}\n```"
        if name == "figure" or self._is_image_container(node):
            return self._render_image_block(node)
        if name in {"hr"}:
            return "---"
        if name in {"div", "section", "article"}:
            return self.render_blocks(node)
        if name in {"img", "picture"}:
            return self._render_image_block(node)
        return self.render_inline_children(node).strip()

    def render_inline_children(self, parent: Tag) -> str:
        return self._collapse_inline("".join(self.render_inline(child) for child in parent.children))

    def render_inline(self, node: Tag | NavigableString) -> str:
        if isinstance(node, Comment):
            return ""
        if isinstance(node, NavigableString):
            return self._clean_text(str(node))
        if self._should_drop(node):
            return ""

        name = node.name.lower()
        if name == "br":
            return "\n"
        if name in {"em", "i"}:
            text = self.render_inline_children(node).strip()
            return f"*{text}*" if text else ""
        if name in {"strong", "b"}:
            text = self.render_inline_children(node).strip()
            return f"**{text}**" if text else ""
        if name == "code":
            return f"`{node.get_text(strip=True)}`"
        if name == "a":
            footnote = self._footnote_number(node)
            if footnote:
                return f"[^{footnote}]"
            text = self.render_inline_children(node).strip() or node.get("href", "").strip()
            href = self._absolute_url(node.get("href"))
            return f"[{text}]({href})" if href and text else text
        if name in {"img", "picture"}:
            return self._render_image_block(node)
        if name in {"span", "sup", "sub"}:
            return self.render_inline_children(node)
        return self.render_inline_children(node)

    def _render_list(self, node: Tag, ordered: bool) -> str:
        items: list[str] = []
        for index, item in enumerate(node.find_all("li", recursive=False), start=1):
            text = self.render_blocks(item) or self.render_inline_children(item)
            text = text.strip()
            if not text:
                continue
            marker = f"{index}." if ordered else "-"
            lines = text.splitlines()
            items.append("\n".join([f"{marker} {lines[0]}", *[f"  {line}" for line in lines[1:]]]))
        return "\n".join(items)

    def _render_image_block(self, node: Tag) -> str:
        img = node if node.name == "img" else node.find("img")
        if not img:
            return self.render_blocks(node)
        src = self._image_src(img, node)
        if not src:
            return ""
        alt = self._clean_text(img.get("alt") or "")
        markdown = f"![{alt}]({self._absolute_url(src)})"
        caption_node = node.select_one("figcaption, .caption, .image-caption")
        if caption_node:
            caption = self.render_inline_children(caption_node).strip()
            if caption:
                markdown = f"{markdown}\n\n*{caption}*"
        return markdown

    def _image_src(self, img: Tag, container: Tag) -> str | None:
        attrs = img.get("data-attrs")
        if attrs:
            try:
                data = json.loads(attrs)
            except json.JSONDecodeError:
                data = {}
            src = data.get("srcNoWatermark") or data.get("src")
            if src:
                return str(src)
        image_link = container.select_one('a[data-component-name="Image2ToDOM"], a.image-link')
        if image_link and image_link.get("href"):
            return str(image_link["href"])
        return str(img.get("src") or "")

    def _footnote_number(self, node: Tag) -> str | None:
        classes = set(node.get("class") or [])
        component_name = node.get("data-component-name")
        href = node.get("href") or ""
        if component_name != "FootnoteAnchorToDOM" and "footnote-anchor" not in classes:
            return None
        match = re.search(r"footnote-(\d+)", href) or re.search(r"(\d+)", node.get_text(strip=True))
        return match.group(1) if match else None

    def _is_image_container(self, node: Tag) -> bool:
        classes = set(node.get("class") or [])
        return "captioned-image-container" in classes or bool(node.select_one('a[data-component-name="Image2ToDOM"], a.image-link'))

    def _should_drop(self, node: Tag) -> bool:
        if isinstance(node, Comment):
            return True
        classes = set(node.get("class") or [])
        component_name = node.get("data-component-name")
        if node.name in {"script", "style", "svg", "button"}:
            return True
        if component_name in {"FootnoteToDOM", "ButtonCreateButton"}:
            return True
        drop_classes = {
            "footnote",
            "button-wrapper",
            "header-anchor-parent",
            "header-anchor",
            "image-link-expand",
        }
        return bool(classes & drop_classes)

    def _absolute_url(self, url: str | None) -> str:
        if not url:
            return ""
        if not self.base_url:
            return url
        return urljoin(self.base_url, url)

    def _clean_text(self, text: str) -> str:
        return text.replace("\xa0", " ")

    def _collapse_inline(self, text: str) -> str:
        text = re.sub(r"[ \t\r\f\v]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        return text


def _footnote_sort_key(value: str) -> tuple[int, str]:
    return (int(value), value) if value.isdigit() else (10**9, value)


def _select_text(soup: BeautifulSoup, selector: str) -> str | None:
    node = soup.select_one(selector)
    return node.get_text(" ", strip=True) if node else None


def _attr(soup: BeautifulSoup, selector: str, attr: str) -> str | None:
    node = soup.select_one(selector)
    return str(node.get(attr)) if node and node.get(attr) else None


def _meta(soup: BeautifulSoup, attr: str, name: str) -> str | None:
    node = soup.find("meta", attrs={attr: name})
    return str(node.get("content")) if node and node.get("content") else None


def _text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _author_name(author: Any) -> str | None:
    if isinstance(author, list) and author:
        return _author_name(author[0])
    if isinstance(author, dict):
        return _text(author.get("name"))
    return _text(author)


def _image_url(image: Any) -> str | None:
    if isinstance(image, list) and image:
        return _image_url(image[0])
    if isinstance(image, dict):
        return _text(image.get("url") or image.get("contentUrl"))
    return _text(image)


def _date_only(value: str | None) -> str | None:
    if not value:
        return None
    return value.split("T", 1)[0]


def convert_file(path: str | Path) -> ParsedPost:
    return parse_substack_html(Path(path).read_text(encoding="utf-8"))
