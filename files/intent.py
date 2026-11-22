"""Interaction / intent agent logic: language, intent, location and time extraction."""
from __future__ import annotations
import datetime as dt
import re

from config import LOCATIONS
from language import detect_language
from models import Location, ParsedQuery, Session

INTENT_KEYWORDS = {
    "PFZ": ["pfz", "potential fishing", "fishing zone", "where to fish", "where can i fish", "best place to fish",
            "पीएफजेड", "संभावित मछली", "मछली कहाँ", "मछली कहां", "मछली पकड़ने का क्षेत्र", "मछली पकड़ने के क्षेत्र",
            "மீன்பிடி மண்டல", "மீன்பிடி பகுதி", "மீன் எங்கே", "చేపల వేట ప్రాంతం", "చేపలు ఎక్కడ"],
    "SAFETY": ["safe", "safety", "venture", "go to sea", "go fishing", "सुरक्षित", "समुद्र में जा", "बाहर जा",
               "பாதுகாப்ப", "கடலுக்குச்", "సురక్షిత", "భద్రత", "సముద్రంలోకి"],
    "CONDITIONS": ["tide", "weather", "wave", "swell", "wind", "sea condition", "ज्वार", "मौसम", "लहर", "हवा",
                   "வானிலை", "அலை", "காற்று", "ஓதம்", "వాతావరణ", "అల", "గాలి", "ఆటుపోట్లు"],
    "ALERTS": ["alert", "cyclone", "lightning", "warning", "storm", "चक्रवात", "बिजली", "चेतावनी",
               "புயல்", "மின்னல்", "எச்சரிக்கை", "తుఫాను", "పిడుగు", "హెచ్చరిక"],
    "OCEAN": ["chlorophyll", "sst", "sea surface temperature", "क्लोरोफिल", "तापमान", "குளோரோபில்", "క్లోరోఫిల్"],
    "GEOFENCE": ["boundary", "border", "restricted", "geofenc", "protected", "avoid", "सीमा", "प्रतिबंधित",
                 "எல்லை", "సరిహద్దు"],
    "ROUTE": ["route", "navigat", "मार्ग", "रास्ता", "பாதை", "வழித்தட", "మార్గం"],
}
DECLINE_WORDS = ["declin", "decreas", "drop", "reduced", "कम हु", "घट", "குறைந்த", "తగ్గ"]
WHY_WORDS = ["why", "क्यों", "ஏன்", "ఎందుకు"]

TOMORROW = ["tomorrow", "tmrw", "நாளை", "రేపు"]
TODAY = ["today", "tonight", "आज", "இன்று", "ఈరోజు", "ఈ రోజు"]
PARTS = {
    "morning": ["morning", "सुबह", "காலை", "ఉదయం"],
    "afternoon": ["afternoon", "दोपहर", "மதியம்", "మధ్యాహ్నం"],
    "evening": ["evening", "शाम", "மாலை", "సాయంత్రం"],
    "night": ["night", "रात", "இரவு", "రాత్రి"],
}
PART_HOURS = {"morning": (5, 11), "afternoon": (12, 16), "evening": (16, 20), "night": (20, 24)}

_COORD_RE = re.compile(r"(-?\d{1,2}\.\d+)\s*°?\s*[NnSs]?\s*[,;]?\s*(-?\d{1,3}\.\d+)")


def detect_intents(low: str) -> list:
    intents = []
    if any(w in low for w in WHY_WORDS) and any(w in low for w in DECLINE_WORDS):
        return ["EXPLAIN"]
    for name, words in INTENT_KEYWORDS.items():
        if any(w in low for w in words):
            intents.append(name)
    return intents


def find_location(text: str, low: str):
    m = _COORD_RE.search(text)
    if m:
        lat, lon = float(m.group(1)), float(m.group(2))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return Location(f"{lat:.2f}N, {lon:.2f}E", lat, lon)
    for info in LOCATIONS.values():
        for alias in info["aliases"]:
            if alias.isascii():
                if re.search(rf"\b{re.escape(alias)}\b", low):
                    return Location(info["name"], info["lat"], info["lon"])
            elif alias in text:
                return Location(info["name"], info["lat"], info["lon"])
    return None


def find_time(low: str):
    tokens = [x for x in re.split(r"[\s?.,!।;:]+", low) if x]
    day = None
    if any(w in low for w in TOMORROW) or "कल" in tokens:
        day = 1
    elif any(w in low for w in TODAY):
        day = 0
    part = next((p for p, ws in PARTS.items() if any(w in low for w in ws)), None)
    return day, part


def _fmt_end(end: dt.datetime, start: dt.datetime) -> str:
    return "24:00" if end.hour == 0 and end.date() > start.date() else f"{end:%H:%M}"


def compute_window(day_offset, part, now):
    base = dt.datetime.combine(now.date() + dt.timedelta(days=day_offset), dt.time(0))
    if part:
        s, e = PART_HOURS[part]
        start, end = base + dt.timedelta(hours=s), base + dt.timedelta(hours=e)
    elif day_offset == 0:
        start = now.replace(minute=0, second=0, microsecond=0)
        end = start + dt.timedelta(hours=12)
    else:
        start, end = base + dt.timedelta(hours=5), base + dt.timedelta(hours=18)
    return start, end, f"{start:%d %b %H:%M}–{_fmt_end(end, start)}"


def parse_query(text: str, session: Session, now: dt.datetime | None = None) -> ParsedQuery:
    now = now or dt.datetime.now()
    low = text.lower()
    lang = detect_language(text)
    intents = detect_intents(low)
    loc = find_location(text, low)
    day, part = find_time(low)

    follow_up = False
    if not intents and session.intents and (loc or day is not None or part):
        intents, follow_up = list(session.intents), True        # multi-turn refinement
    if loc is None:
        loc = session.location
    if day is None:
        day = session.day_offset if follow_up else 0
    if part is None and follow_up and day == session.day_offset:
        part = session.part
    start, end, label = compute_window(day, part, now)
    return ParsedQuery(text=text, language=lang, intents=intents, location=loc, day_offset=day,
                       part=part, window=(start, end), window_label=label, follow_up=follow_up)
