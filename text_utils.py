from __future__ import annotations

import re
from typing import List, Set

from pypinyin import Style, lazy_pinyin


_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]+")
_FUZZY_PINYIN_PAIRS = [
    ("zh", "z"),
    ("ch", "c"),
    ("sh", "s"),
    ("ang", "an"),
    ("eng", "en"),
    ("ing", "in"),
    ("iang", "ian"),
    ("uang", "uan"),
    ("l", "n"),
    ("f", "h"),
]


def expand_text_for_search(text: str) -> str:
    """Add full and fuzzy pinyin variants for Chinese text."""
    text = str(text or "")
    parts = [text]

    for match in _CJK_PATTERN.findall(text):
        syllables = lazy_pinyin(match, style=Style.NORMAL, errors="ignore")
        if not syllables:
            continue

        joined = "".join(syllables)
        spaced = " ".join(syllables)
        parts.extend([joined, spaced])

        fuzzy_syllables = _fuzzy_pinyin_syllables(syllables)
        parts.extend(fuzzy_syllables)
        parts.extend(_joined_fuzzy_phrases(syllables))

    return " ".join(part for part in parts if part)


def _fuzzy_pinyin_syllables(syllables: List[str]) -> List[str]:
    variants: List[str] = []
    seen: Set[str] = set(syllables)
    for syllable in syllables:
        for variant in _fuzzy_pinyin_syllable_variants(syllable):
            if variant not in seen:
                seen.add(variant)
                variants.append(variant)
    return variants


def _fuzzy_pinyin_syllable_variants(syllable: str) -> List[str]:
    variants: List[str] = []
    for first, second in _FUZZY_PINYIN_PAIRS:
        if syllable.startswith(first):
            variants.append(second + syllable[len(first):])
        if syllable.startswith(second):
            variants.append(first + syllable[len(second):])
    for first, second in _FUZZY_PINYIN_PAIRS:
        if syllable.endswith(first):
            variants.append(syllable[:-len(first)] + second)
        if syllable.endswith(second):
            variants.append(syllable[:-len(second)] + first)
    return [variant for variant in variants if variant and variant != syllable]


def _joined_fuzzy_phrases(syllables: List[str]) -> List[str]:
    phrases: List[str] = []
    for index, syllable in enumerate(syllables):
        variants = _fuzzy_pinyin_syllable_variants(syllable)[:2]
        for variant in variants:
            fuzzy = list(syllables)
            fuzzy[index] = variant
            phrases.extend(["".join(fuzzy), " ".join(fuzzy)])
    return phrases
