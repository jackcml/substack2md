# substackscrape

We're building a **Substack-to-Markdown scraper**, with EPUB generation as an
optional downstream export step.

The ideal pipeline:
```text
Substack URL
        ↓
Fetch canonical post HTML + metadata
        ↓
Extract article body, title, author, date, hero image / share image
        ↓
Normalize Substack-specific HTML into a clean document structure
        ↓
Detect footnote references + footnote blocks
        ↓
Rewrite notes as Markdown footnotes
        ↓
Write a Markdown file with YAML frontmatter
        ↓
Optionally convert Markdown to EPUB with an existing tool
```

For footnotes, the converter should transform something like:

```html
<p>
  Some sentence
  <span style="min-width:0;" data-state="closed">
    <a data-component-name="FootnoteAnchorToDOM" id="footnote-anchor-1" href="#footnote-1" target="_self" class="footnote-anchor">1</a>
  </span>
</p>

<div data-component-name="FootnoteToDOM" class="footnote">
  <a id="footnote-1" href="#footnote-anchor-1" contenteditable="false" target="_self" class="footnote-number">1</a>
  <div class="footnote-content">The note text...</div>
</div>
```

into Markdown footnotes:

```markdown
Some sentence[^1]

[^1]: The note text...
```

For compatibility with common Markdown-to-EPUB tools, initially place all note
definitions at the **end of the article**, not inline immediately after the
paragraph. Pandoc-style Markdown footnotes are the target format because they
are human-readable and convert cleanly to EPUB footnotes.

The generated Markdown should start with YAML frontmatter so the scrape result is
useful on its own and easy to feed into later tooling:

```markdown
---
title: "Post title"
subtitle: "Optional subtitle"
author: "Author Name"
date: "2024-01-01"
canonical_url: "https://example.substack.com/p/post-slug"
source: "substack"
hero_image: "https://..."
---
```

## Tool structure

Our first version is a local CLI:

```bash
substack2md "https://example.substack.com/p/post-slug"
```

Internally:

**Fetcher**
Use `requests`. For now, we'll support only public posts, not subscriber-only.

**Extractor**
Use BeautifulSoup or `readability-lxml`, but with Substack-specific selectors.
Generic readability extractors often destroy footnote structure, captions, embeds, and heading hierarchy.

**Normalizer**
Convert the article body into a clean intermediate structure suitable for
Markdown output. Strip scripts, comments, buttons, share widgets, subscription
CTAs, header-anchor UI, and other interactive chrome. Preserve ordinary
`<a href>` links, headings, emphasis, blockquotes, lists, images, captions, and
other article content.

**Footnote rewriter**
This is the most valuable custom step. 
It should support the native Substack footnote pattern (described above, like
`a href="#footnote-..."` → target block), replace inline anchors with Markdown
footnote references, and append note definitions at the end of the Markdown
document.

**Cover acquisition**
We'll have to investigate how the mobile app fetches its "share images", which are essentially generated covers.
For now, record the best available image URL in frontmatter and leave image
downloading/cover generation for later.

**Markdown writer**
Write one `.md` file per post. Use a slug derived from the canonical URL or
title, and keep the output readable enough to inspect and edit manually.

**Optional EPUB export**
Do not build EPUB packaging in the first version. Later, add an optional command
or documented pipeline that passes the generated Markdown to an existing
converter such as Pandoc. One post = one book initially; leave room for mass
export where one post = one chapter in the future.
