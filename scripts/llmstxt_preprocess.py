"""Remove browser-only controls from AI-readable documentation."""

from bs4 import BeautifulSoup


def preprocess(soup: BeautifulSoup, output: str) -> None:
    """Clean rendered documentation before Markdown conversion."""
    del output

    for selector in (
        ".anchor-link",
        ".clipboard-copy-txt",
        ".jp-InputPrompt",
        ".jp-OutputPrompt",
        "clipboard-copy",
    ):
        for element in soup.select(selector):
            element.decompose()

    for highlight in soup.select(".highlight-ipynb"):
        language = next(
            (
                css_class.removeprefix("hl-")
                for css_class in highlight.get("class", ())
                if css_class.startswith("hl-")
            ),
            None,
        )
        if language is not None:
            highlight["class"] = [*highlight.get("class", ()), f"language-{language}"]
