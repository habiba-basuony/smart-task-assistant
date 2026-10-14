"""Parse common Arabic/Saudi date and time expressions deterministically.

Time parsing is intentionally conservative: known expressions are normalized and
parsed by rules. If a user explicitly mentions a clock time that cannot be parsed,
the caller can ask for clarification instead of silently dropping the time.
"""
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.config import APP_TIMEZONE
from app.services.text_utils import normalize_ar

FRIDAY = 4  # Python: Monday = 0 ... Sunday = 6
WEEKDAYS_AR = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]

# All patterns operate on normalized text (ة -> ه, أ -> ا, Arabic digits -> ASCII).
AFTER_TOMORROW = re.compile(r"(?<!\w)[لب]?بعد\s+(?:بكر[ها]|غد)(?!\w)")
TOMORROW = re.compile(r"(?<!\w)[لب]?(?:بكر[ها]|غدا?)(?!\w)")
TODAY = re.compile(r"(?<!\w)(?:اليوم|الليله)(?!\w)")

_WEEKDAY_WORDS = [
    (r"(?:ال|لل)احد", 6),
    (r"(?:ال|لل)?(?:اثنين|اتنين|ثنين)", 0),
    (r"(?:ال|لل)?ثلاثاء", 1),
    (r"(?:ال|لل)?اربعاء", 2),
    (r"(?:ال|لل)?خميس", 3),
    (r"(?:ال|لل)?جمعه", 4),
    (r"(?:ال|لل)?سبت", 5),
]
WEEKDAYS = [
    (re.compile(rf"(?<!\w){pattern}(?!\w)"), weekday)
    for pattern, weekday in _WEEKDAY_WORDS
]

# Common period names.
MORNING = ("الصبح", "صباحا", "الصباح", "صباح", "الفجر")
NOON = ("الظهر", "الضهر")
AFTERNOON = ("العصر",)
SUNSET = ("المغرب",)
EVENING = ("العشاء", "المساء", "مساء", "مساءا")
NIGHT = ("بالليل", "بليل", "الليل", "ليل", "ليلا")

_PERIOD_WORDS = tuple(
    sorted(
        set(MORNING + NOON + AFTERNOON + SUNSET + EVENING + NIGHT),
        key=len,
        reverse=True,
    )
)
_PERIOD_PATTERN = "(?:" + "|".join(
    re.escape(word) for word in _PERIOD_WORDS
) + ")"
_PERIOD_TOKEN = rf"(?<!\w){_PERIOD_PATTERN}(?!\w)"

# Recognized Arabic expressions for clock hours.
_HOUR_WORDS = {
    # 1
    "واحد": 1, "واحده": 1, "الواحده": 1,
    "اولي": 1, "الاولي": 1,

    # 2
    "اثنين": 2, "اتنين": 2, "ثنين": 2,
    "اثنتين": 2, "ثنتين": 2,
    "ثانيه": 2, "الثانيه": 2,
    "تانيه": 2, "التانيه": 2,

    # 3
    "ثلاث": 3, "ثلاثه": 3, "الثلاثه": 3,
    "ثالثه": 3, "الثالثه": 3,
    "تلاته": 3, "تالتة": 3, "تالته": 3,
    "التالته": 3,

    # 4
    "اربع": 4, "اربعه": 4,
    "الرابعه": 4, "رابعه": 4,

    # 5
    "خمس": 5, "خمسه": 5,
    "الخمسه": 5, "خامسه": 5, "الخامسه": 5,

    # 6
    "ست": 6, "سته": 6,
    "السته": 6, "سادسه": 6, "السادسه": 6,

    # 7
    "سبع": 7, "سبعه": 7,
    "السبعه": 7, "سابعه": 7, "السابعه": 7,

    # 8
    "ثمان": 8, "ثمانيه": 8, "تمانيه": 8,
    "التامنه": 8, "الثامنه": 8,
    "تامنه": 8, "ثامنه": 8,

    # 9
    "تسع": 9, "تسعه": 9, "التسعه": 9,
    "تاسعه": 9, "التاسعه": 9,

    # 10
    "عشر": 10, "عشره": 10,
    "العشره": 10, "عاشره": 10, "العاشره": 10,

    # 11
    "حداشر": 11, "حدعشر": 11,
    "احدعشر": 11, "احد عشر": 11,
    "احد عشره": 11, "احدي عشر": 11,
    "احدي عشره": 11, "الحادي عشر": 11,
    "الحادي عشره": 11, "الحاديه عشر": 11,
    "الحاديه عشره": 11,

    # 12
    "اتناشر": 12, "اثناشر": 12, "اثنعش": 12,
    "اثني عشر": 12, "اثنا عشر": 12,
    "اثني عشره": 12, "اثنا عشره": 12,
    "الثاني عشر": 12, "الثاني عشره": 12,
    "الثانيه عشر": 12, "الثانيه عشره": 12,

    # 13-24
    "تلتاشر": 13, "ثلاثه عشر": 13,
    "ثلاثه عشره": 13, "ثلاثه عشرون": 13,

    "اربعتاشر": 14, "اربعه عشر": 14,
    "اربعه عشره": 14,

    "خمستاشر": 15, "خمسه عشر": 15,
    "خمسه عشره": 15,

    "ستاشر": 16, "سته عشر": 16,
    "سته عشره": 16,

    "سبعتاشر": 17, "سبعه عشر": 17,
    "سبعه عشره": 17,

    "تمنتاشر": 18, "تمانيه عشر": 18,
    "ثمانيه عشر": 18, "ثمانيه عشره": 18,

    "تسعتاشر": 19, "تسعه عشر": 19,
    "تسعه عشره": 19,

    "عشرين": 20,
    "واحد وعشرين": 21, "واحد وعشرون": 21,
    "اثنين وعشرين": 22, "اتنين وعشرين": 22,
    "ثلاثه وعشرين": 23, "تلاته وعشرين": 23,
    "اربعه وعشرين": 24, "اربعة وعشرين": 24,
    "خمسه وعشرين": 25, "خمسة وعشرين": 25,
}

_HOUR_WORD_PATTERN = "(?:" + "|".join(
    re.escape(word)
    for word in sorted(_HOUR_WORDS, key=len, reverse=True)
) + ")"

_HOUR_TOKEN = (
    rf"(?:\d{{1,2}}(?!\d)|"
    rf"(?<!\w){_HOUR_WORD_PATTERN}(?!\w))"
)

# Minute expressions such as :30, ونص, وربع, إلا ربع, و15 دقيقة.
_MINUTE_WORDS = {
    "واحد": 1, "واحده": 1,
    "اثنين": 2, "اتنين": 2,
    "ثلاث": 3, "ثلاثه": 3,
    "اربع": 4, "اربعه": 4,
    "خمس": 5, "خمسه": 5,
    "ست": 6, "سته": 6,
    "سبع": 7, "سبعه": 7,
    "ثمان": 8, "ثمانيه": 8,
    "تسع": 9, "تسعه": 9,
    "عشر": 10, "عشره": 10,
    "احد عشر": 11, "احدي عشر": 11,
    "اثنا عشر": 12, "اثني عشر": 12,
    "ربع": 15, "عشرين": 20, "ثلاثين": 30,
}

_MINUTE_WORD_PATTERN = "(?:" + "|".join(
    re.escape(word)
    for word in sorted(_MINUTE_WORDS, key=len, reverse=True)
) + ")"

_MINUTE_SUFFIX = (
    r"(?:\s*:\s*\d{1,2}"
    r"|\s*(?:و\s*)?(?:النصف|نصف|نص|الربع|ربع)(?:\s+ساعه)?"
    r"|\s*الا\s*(?:الربع|ربع|15|خمس(?:ه)?|5|عشر(?:ه)?|10)"
    r"(?:\s*(?:دقيقه|دقايق))?(?:\s+ساعه)?"
    rf"|\s*و\s*(?:\d{{1,2}}|{_MINUTE_WORD_PATTERN})"
    r"\s*(?:دقيقه|دقايق|دقائق)"
    r"|\s*و\s*\d{2}(?!\d)"
    r")"
)

TIME_WITH_CLOCK_MARKER = re.compile(
    rf"(?<!\w)(?:(?P<p0>{_PERIOD_TOKEN})\s+)?الساعه\s*"
    rf"(?P<h>{_HOUR_TOKEN})(?P<minute_expr>{_MINUTE_SUFFIX})?"
    rf"(?:\s*(?P<p1>{_PERIOD_TOKEN}))?"
)

TIME_WITH_PERIOD = re.compile(
    rf"(?<!\w)(?P<h>{_HOUR_TOKEN})"
    rf"(?P<minute_expr>{_MINUTE_SUFFIX})?\s*"
    rf"(?P<p1>{_PERIOD_TOKEN})"
)

TIME_WITH_MINUTES = re.compile(
    rf"(?<!\w)(?P<h>{_HOUR_TOKEN})"
    rf"(?P<minute_expr>{_MINUTE_SUFFIX})(?!\w)"
)

CLOCK_MARKER = re.compile(r"(?<!\w)الساعه(?!\w)")

# Preserve the task's existing defaults for these two period-only expressions.
DEFAULT_TIMES = {
    "العصر": time(15, 0),
    "الظهر": time(12, 0),
}

MIDNIGHT_PHRASE = re.compile(
    r"(?<!\w)(?:منتصف الليل|نص الليل)(?!\w)"
)
MIDDAY_PHRASE = re.compile(
    r"(?<!\w)(?:منتصف النهار)(?!\w)"
)


@dataclass
class Due:
    due_date: date | None = None
    due_time: time | None = None
    moved_from_friday: bool = False
    time_mentioned: bool = False
    time_ambiguous: bool = False


def local_now() -> datetime:
    return datetime.now(ZoneInfo(APP_TIMEZONE))


def _resolve_date(text: str, today: date) -> date | None:
    if AFTER_TOMORROW.search(text):
        return today + timedelta(days=2)

    if TOMORROW.search(text):
        return today + timedelta(days=1)

    if TODAY.search(text):
        return today

    for pattern, weekday in WEEKDAYS:
        if pattern.search(text):
            days = (weekday - today.weekday()) % 7 or 7
            return today + timedelta(days=days)

    return None


def _hour_value(hour_text: str) -> int | None:
    if hour_text.isdigit():
        return int(hour_text)

    return _HOUR_WORDS.get(normalize_ar(hour_text))


def _parse_minute_expression(
    expression: str | None,
) -> tuple[int, int] | None:
    """Return (minute, hours_to_subtract), or None if invalid."""
    if not expression:
        return 0, 0

    suffix = normalize_ar(expression).strip()

    colon = re.fullmatch(r":\s*(\d{1,2})", suffix)
    if colon:
        minute = int(colon.group(1))
        return (minute, 0) if 0 <= minute <= 59 else None

    if "الا" in suffix:
        amount_match = re.search(
            r"(ربع|الربع|15|خمس|خمسه|5|عشر|عشره|10)",
            suffix,
        )
        if not amount_match:
            return None

        token = amount_match.group(1)
        delta = (
            15 if token in {"ربع", "الربع", "15"}
            else 5 if token in {"خمس", "خمسه", "5"}
            else 10
        )
        return 60 - delta, 1

    if any(token in suffix for token in ("النصف", "نصف", "نص")):
        return 30, 0

    if any(token in suffix for token in ("الربع", "ربع")):
        return 15, 0

    numeric_minutes = re.search(
        r"و\s*(\d{1,2})\s*(?:دقيقه|دقايق|دقائق)",
        suffix,
    )
    if numeric_minutes:
        minute = int(numeric_minutes.group(1))
        return (minute, 0) if 0 <= minute <= 59 else None

    shorthand_minutes = re.search(
        r"و\s*(\d{2})(?!\d)",
        suffix,
    )
    if shorthand_minutes:
        minute = int(shorthand_minutes.group(1))
        return (minute, 0) if 0 <= minute <= 59 else None

    for word, minute in _MINUTE_WORDS.items():
        if re.search(
            rf"و\s*{re.escape(word)}\s*(?:دقيقه|دقايق|دقائق)",
            suffix,
        ):
            return (minute, 0) if 0 <= minute <= 59 else None

    return None


def _period_kind(period: str | None) -> str | None:
    if period is None:
        return None

    period = normalize_ar(period)

    if period in MORNING:
        return "morning"
    if period in NOON:
        return "noon"
    if period in AFTERNOON:
        return "afternoon"
    if period in SUNSET:
        return "sunset"
    if period in EVENING:
        return "evening"
    if period in NIGHT:
        return "night"

    return None


def _to_24h(hour: int, period: str | None) -> int | None:
    """Convert a clock hour and Arabic period to 24-hour time."""
    if not 0 <= hour <= 23:
        return None

    kind = _period_kind(period)

    if kind is None:
        return hour

    # Avoid adding 12 twice for already-24-hour values.
    if hour > 12:
        return hour

    if kind == "morning":
        return 0 if hour == 12 else hour

    if kind == "noon":
        if hour == 12:
            return 12
        return hour + 12 if 1 <= hour <= 6 else hour

    if kind in {"evening", "night"} and hour == 12:
        return 0

    if kind == "night":
        if 1 <= hour <= 5:
            return hour
        return hour + 12 if 6 <= hour <= 11 else hour

    if hour == 12:
        return 12

    return hour + 12 if 1 <= hour <= 11 else hour


def _time_matches(text: str):
    """Collect time candidates and remove overlapping matches."""
    candidates = {}

    for pattern in (
        TIME_WITH_CLOCK_MARKER,
        TIME_WITH_PERIOD,
        TIME_WITH_MINUTES,
    ):
        for match in pattern.finditer(text):
            candidates.setdefault(match.span("h"), match)

    return [
        candidates[key]
        for key in sorted(candidates)
    ]


def _extract_time_match(text: str):
    matches = _time_matches(text)
    return matches[0] if matches else None


def _resolve_time(text: str) -> time | None:
    if MIDNIGHT_PHRASE.search(text):
        return time(0, 0)

    if MIDDAY_PHRASE.search(text):
        return time(12, 0)

    match = _extract_time_match(text)

    if match:
        hour = _hour_value(match.group("h"))
        if hour is None:
            return None

        parsed_minutes = _parse_minute_expression(
            match.groupdict().get("minute_expr")
        )
        if parsed_minutes is None:
            return None

        minute, hours_to_subtract = parsed_minutes
        period = (
            match.groupdict().get("p0")
            or match.groupdict().get("p1")
        )

        if hours_to_subtract:
            if hour <= 12:
                hour = ((hour - 2) % 12) + 1
            else:
                hour = (hour - hours_to_subtract) % 24

        converted_hour = _to_24h(hour, period)

        if converted_hour is None or not 0 <= minute <= 59:
            return None

        return time(converted_hour, minute)

    if CLOCK_MARKER.search(text):
        return None

    for word, default in DEFAULT_TIMES.items():
        if re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text):
            return default

    return None


def _time_was_mentioned(text: str) -> bool:
    if _time_matches(text) or CLOCK_MARKER.search(text):
        return True

    if MIDNIGHT_PHRASE.search(text) or MIDDAY_PHRASE.search(text):
        return True

    return any(
        re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text)
        for word in _PERIOD_WORDS
    )


def parse_due(message: str, today: date | None = None) -> Due:
    text = normalize_ar(message)
    today = today or local_now().date()

    due_date = _resolve_date(text, today)
    time_matches = _time_matches(text)

    # Detect alternatives such as "10 أو 11" and "10 ولا 11".
    alternative_after_time = bool(
        time_matches
        and re.search(
            rf"(?<!\w)(?:او|ولا)\s*(?:الساعه\s*)?(?P<h>{_HOUR_TOKEN})",
            text[time_matches[0].end():],
        )
    )

    time_ambiguous = (
        len(time_matches) > 1
        or alternative_after_time
    )

    due_time = None if time_ambiguous else _resolve_time(text)
    time_mentioned = _time_was_mentioned(text)

    moved = False

    if due_date and due_date.weekday() == FRIDAY:
        due_date += timedelta(days=1)
        moved = True

    return Due(
        due_date,
        due_time,
        moved,
        time_mentioned,
        time_ambiguous,
    )