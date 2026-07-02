# substack2md
A Substack-to-Markdown scraper with YAML frontmatter and pandoc footnote support.

## Usage
```bash
substack2md "https://example.substack.com/p/post-slug"
```

### Further conversion
While broadly useful, my primary use case is to read articles on my Kindle, so some further conversion is necessary.
I use pandoc directly alongside the tool:
```bash
substack2md "https://example.substack.com/p/post-slug"
pandoc post-slug.md -o out.epub
```

Optionally, use the `hero_image` linked in the frontmatter as the EPUB cover with pandoc's `--epub-cover-image=file.png` option.
Hero images, however, are not typically well-suited to be covers either in aspect ratio or content. Share-images (support TBD) made available through the Substack mobile app work better here.

## Frontmatter schema
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

## Future
- Mass exporting blogs
- Support for subscriber-only posts
- Downloading/linking of additional share-images
- Automatic pandoc workflow
