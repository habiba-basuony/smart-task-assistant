import re

# Tashkeel (short vowels) and tatweel.
_MARKS = re.compile("[\u064B-\u065F\u0670\u0640]")
# Arabic-Indic and Persian digits -> normal digits.
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
# Letters that people write in different ways.
_LETTERS = {"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه"}


def normalize_ar(text: str) -> str:
    """Make Arabic text easy to compare: بكرة/بكره, الأحد/الاحد, ١٠/10 all become the same."""
    text = _MARKS.sub("", text).translate(_DIGITS)
    for old, new in _LETTERS.items():
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text).strip().lower()
