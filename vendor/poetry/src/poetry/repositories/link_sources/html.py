from __future__ import annotations

import urllib.parse
import warnings

from html import unescape
from typing import TYPE_CHECKING

from poetry.core.packages.utils.link import Link

from poetry.repositories.link_sources.base import LinkSource


if TYPE_CHECKING:
    from collections.abc import Iterator

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import html5lib


class HTMLPage(LinkSource):
    def __init__(self, url: str, content: str) -> None:
        super().__init__(url=url)

        self._parsed = html5lib.parse(content, namespaceHTMLElements=False)

    @property
    def links(self) -> Iterator[Link]:
        for anchor in self._parsed.findall(".//a"):
            if anchor.get("href"):
                href = anchor.get("href")
                url = self.clean_link(urllib.parse.urljoin(self._url, href))
                pyrequire = anchor.get("data-requires-python")
                pyrequire = unescape(pyrequire) if pyrequire else None
                yanked_value = anchor.get("data-yanked")
                yanked: str | bool
                if yanked_value:
                    yanked = unescape(yanked_value)
                else:
                    yanked = "data-yanked" in anchor.attrib
                link = Link(url, requires_python=pyrequire, yanked=yanked)

                if link.ext not in self.SUPPORTED_FORMATS:
                    continue

                yield link


class SimpleRepositoryPage(HTMLPage):
    def __init__(self, url: str, content: str) -> None:
        if not url.endswith("/"):
            url += "/"
        super().__init__(url=url, content=content)
