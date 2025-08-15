#!/usr/bin/env python3
"""Markdown to HTML helper tools."""
from pathlib import Path

import markdown


def markdown_to_html(markdown_file: Path) -> str:
    """Return the content of the provided file formatted as HTML.

    Args:
        markdown_file (Path): The file to process

    """
    return markdown.markdown(markdown_file.read_text())
