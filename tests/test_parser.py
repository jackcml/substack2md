from pathlib import Path

from substack2md.parser import parse_substack_html, slugify

FIXTURE = Path(__file__).resolve().parents[0] / "example-post.html"


def test_parses_fixture_metadata() -> None:
    post = parse_substack_html(FIXTURE.read_text(encoding="utf-8"))

    assert post.metadata.title == "The internet is already over"
    assert (
        post.metadata.subtitle
        == "Our God is a devourer, who makes things only for the swallowing."
    )
    assert post.metadata.author == "Sam Kriss"
    assert post.metadata.date == "2022-09-18"
    assert (
        post.metadata.canonical_url
        == "https://samkriss.substack.com/p/the-internet-is-already-over"
    )
    assert post.metadata.hero_image and post.metadata.hero_image.startswith(
        "https://substackcdn.com/"
    )


def test_renders_markdown_article_structure() -> None:
    post = parse_substack_html(FIXTURE.read_text(encoding="utf-8"))
    markdown = post.markdown

    assert markdown.startswith("---\n")
    assert 'title: "The internet is already over"' in markdown
    assert "# The internet is already over" in markdown
    assert "### A sort of preface" in markdown
    assert "![)" not in markdown
    assert "Subscribe now" not in markdown
    assert "FootnoteToDOM" not in markdown


def test_renders_substack_footnotes_as_pandoc_footnotes() -> None:
    post = parse_substack_html(FIXTURE.read_text(encoding="utf-8"))
    markdown = post.markdown

    assert "goddess of night and death.[^1]" in markdown
    assert (
        "[^1]: I am *very disappointed* that this scene never appears in Disney’s *Moana*."
        in markdown
    )
    assert "[^11]: The ‘cancelled’ always participate" in markdown
    assert markdown.index("goddess of night and death.[^1]") < markdown.index("[^1]:")


def test_preserves_space_nested_inside_emphasis_tags() -> None:
    post = parse_substack_html(FIXTURE.read_text(encoding="utf-8"))
    # The fixture has `smart.</span><em> You</em>` — the boundary space lives
    # inside the <em> and must be re-emitted outside the emphasis markers.
    assert "because you’re smart. *You* know" in post.markdown

    html = '<div class="available-content"><div class="body markup"><p>a<em> b </em>c <strong>d </strong>e</p></div></div>'
    assert "a *b* c **d** e" in parse_substack_html(html).markdown


def test_slugify_title() -> None:
    assert slugify("The internet is already over") == "the-internet-is-already-over"
