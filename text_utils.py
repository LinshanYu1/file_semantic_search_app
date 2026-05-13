from __future__ import annotations

import re

from pypinyin import Style, lazy_pinyin


_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]+")


def expand_text_for_search(text: str) -> str:
    """Add pinyin variants for Chinese text so Chinese and pinyin queries can match."""
    text = str(text or "")
    parts = [text]

    for match in _CJK_PATTERN.findall(text):
        syllables = lazy_pinyin(match, style=Style.NORMAL, errors="ignore")
        if not syllables:
            continue

        joined = "".join(syllables)
        spaced = " ".join(syllables)
        initials = "".join(syllable[0] for syllable in syllables if syllable)
        parts.extend([joined, spaced, initials])

    return " ".join(part for part in parts if part)

