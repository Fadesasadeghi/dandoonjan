"""Versioned dental ontology. Canonical identifiers must pass validation here.

LLM output strings can never become canonical identifiers directly; they must
normalize through this module.
"""
from __future__ import annotations

import re

ONTOLOGY_VERSION = "onto-v1.0.0"

# FDI permanent teeth 11-48 (excluding invalid x8/x9 endings)
_TEETH = set()
for quad in (1, 2, 3, 4):
    for pos in range(1, 9):
        _TEETH.add(quad * 10 + pos)

TOOTH_IDENTIFIERS = {f"TOOTH_{n}": n for n in sorted(_TEETH)}

TREATMENT_IDENTIFIERS = {
    "TREATMENT_ROOT_CANAL",
    "TREATMENT_EXTRACTION",
    "TREATMENT_CROWN",
    "TREATMENT_FILLING",
    "TREATMENT_SCALING",
    "TREATMENT_IMPLANT",
    "TREATMENT_BRIDGE",
    "TREATMENT_DENTURE",
    "TREATMENT_ORTHODONTICS",
    "TREATMENT_UNKNOWN",
}

CLINICAL_TEST_IDENTIFIERS = {
    "TEST_CLINICAL_EXAMINATION",
    "TEST_SYMPTOM_HISTORY",
    "TEST_PULP_VITALITY",
    "TEST_PERIAPICAL_RADIOGRAPH",
    "TEST_OPG",
    "TEST_CBCT",
    "TEST_BITEWING",
    "TEST_PROBING",
}

CLAIM_TYPE_IDENTIFIERS = {
    "TREATMENT",
    "TREATMENT_QUOTED",
    "OTHER",
}

# Persian/English surface forms -> canonical
_TOOTH_PATTERNS: list[tuple[re.Pattern, callable]] = []
_QUAD_FA = {"بالا راست": 1, "بالا چپ": 2, "پایین چپ": 3, "پایین راست": 4,
            "بالا سمت راست": 1, "بالا سمت چپ": 2, "پایین سمت چپ": 3, "پایین سمت راست": 4}
_POSITION_FA = {
    "1": ("یکم", "central"), "2": ("دوم", "lateral"), "3": ("سوم", "canine"),
}

_TREATMENT_SYNONYMS = {
    "TREATMENT_ROOT_CANAL": ["عصب کشی", "عصب‌کشی", "عصبکشی", "درمان ریشه", "root canal", "rct",
                             "endodontic treatment", "endodontics", " treatment rct"],
    "TREATMENT_EXTRACTION": ["کشیدن دندان", "کشیدگی", "ake کردن", "اکششن", "extraction", "extract",
                             "کشیدن", "اخذ", "pull tooth"],
    "TREATMENT_CROWN": ["روکش", "کراون", "crown", "capping"],
    "TREATMENT_FILLING": ["پر کردن دندان", "ترمیم", "filling", "ترمیمی"],
    "TREATMENT_SCALING": ["جرم گیری", "جرم‌گیری", "scaling"],
    "TREATMENT_IMPLANT": ["ایمپلنت", "implant"],
    "TREATMENT_BRIDGE": ["بریج", "bridge"],
    "TREATMENT_ORTHODONTICS": ["ارتودنسی", "orthodontics", "braces"],
}


class OntologyValidationError(ValueError):
    pass


def validate_tooth(identifier: str) -> str:
    if identifier not in TOOTH_IDENTIFIERS:
        raise OntologyValidationError(f"Invalid tooth identifier: {identifier!r}")
    return identifier


def validate_treatment(identifier: str) -> str:
    if identifier not in TREATMENT_IDENTIFIERS:
        raise OntologyValidationError(f"Invalid treatment identifier: {identifier!r}")
    return identifier


def validate_claim_type(identifier: str) -> str:
    if identifier not in CLAIM_TYPE_IDENTIFIERS:
        raise OntologyValidationError(f"Invalid claim type: {identifier!r}")
    return identifier


def normalize_tooth(text: str) -> str | None:
    """Normalize Persian/English tooth references to TOOTH_<FDI>."""
    t = text.strip().lower().replace("٫", ".").replace("۰", "0").replace("۱", "1") \
        .replace("۲", "2").replace("۳", "3").replace("۴", "4").replace("۵", "5") \
        .replace("۶", "6").replace("۷", "7").replace("۸", "8").replace("۹", "9")
    # direct FDI number
    m = re.search(r"\b([1-4])([1-8])\b", t)
    if m:
        return f"TOOTH_{m.group(1)}{m.group(2)}"
    # "دندان ۶ پایین راست" style: digit + quadrant words
    m = re.search(r"دندان\s*#?(\d)", t)
    if m:
        digit = m.group(1)
        for phrase, quad in _QUAD_FA.items():
            if phrase in t:
                # Persian convention: پایین راست = quadrant 4, پایین چپ = 3, بالا راست = 1, بالا چپ = 2
                return f"TOOTH_{quad}{digit}"
    # English words
    if re.search(r"lower\s+right\s+first\s+molar", t):
        return "TOOTH_46"
    if re.search(r"lower\s+left\s+first\s+molar", t):
        return "TOOTH_36"
    return None


def normalize_treatment(text: str) -> str | None:
    t = text.strip().lower()
    for canonical, synonyms in _TREATMENT_SYNONYMS.items():
        for s in synonyms:
            if s in t:
                return canonical
    return None


