"""Text normalization shared by the extraction steps."""

import re
import unicodedata

LIGATURES = {
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl",
    "ﬅ": "st", "ﬆ": "st",
}
SPACES = dict.fromkeys(map(ord, "\xa0       "
                                 "      　"), " ")
INVISIBLE_RE = re.compile("[­​‌‍⁠﻿]")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
BULLET_RE = re.compile(r"^\s*[•●▪■◦○►▸‣·]\s*")


SPACING_ACCENTS = {"´": "́", "˜": "̃", "¨": "̈", "ˆ": "̂"}
SPACING_ACCENT_RE = re.compile("([´˜¨ˆ])([A-Za-zı])")


def compose_spacing_accents(text):
    def compose(match):
        base = "i" if match.group(2) == "ı" else match.group(2)
        return unicodedata.normalize("NFC", base + SPACING_ACCENTS[match.group(1)])
    return SPACING_ACCENT_RE.sub(compose, text)


def map_symbol_font(text):
    def remap(match):
        char = chr(ord(match.group()) - 0xF000)
        return char if char.isprintable() else ""
    return re.sub("[-]", remap, text)


def normalize_text(text):
    if not text:
        return ""
    text = BULLET_RE.sub("- ", text)
    text = compose_spacing_accents(text)
    text = unicodedata.normalize("NFC", text)
    for ligature, plain in LIGATURES.items():
        text = text.replace(ligature, plain)
    text = text.translate(SPACES)
    text = INVISIBLE_RE.sub("", text)
    text = map_symbol_font(text)
    text = re.sub("[\ue000-\uf8ff\ufffd]", "", text)
    text = re.sub(r"(\d)\s?®", r"\1°", text)
    text = CONTROL_RE.sub("", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def join_lines(lines):
    out = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if not out:
            out = line
        elif out.endswith("-") and line[:1].islower() and "/" not in out.rsplit(" ", 1)[-1]:
            out = out[:-1] + line
        else:
            out = f"{out} {line}"
    return out
