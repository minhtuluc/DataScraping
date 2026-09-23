import math
import re
import unicodedata

from .contracts import Document, Field
from .numbers import NUMBER, evidence_numbers, parse_number

# Explicit dimensional conversions only. Unknown units are rejected, never guessed.
UNITS = {
    "m": ("length", 1), "metres": ("length", 1), "meters": ("length", 1),
    "ft": ("length", 0.3048), "km": ("length", 1000), "mm": ("length", 0.001),
    "t": ("mass", 1), "tonnes": ("mass", 1), "kg": ("mass", 0.001),
    "long tons": ("mass", 1.0160469088), "short tons": ("mass", 0.90718474),
    "kn": ("speed", 1), "knots": ("speed", 1), "km/h": ("speed", 1 / 1.852),
    "m/s": ("speed", 3.6 / 1.852), "nmi": ("length", 1852),
    "": ("count", 1), "persons": ("count", 1),
}

ALIASES = {'metre': 'm', 'meter': 'm', 'mét': 'm', 'mètres': 'm', 'cm': 'cm',
           'feet': 'ft', 'foot': 'ft', 'tonne': 't', 'tấn': 't', 'knot': 'kn',
           'kts': 'kn', 'kt': 'kn', 'người': 'persons', 'people': 'persons',
           'person': 'persons', 'kilograms': 'kg', 'kilogram': 'kg'}
UNITS['cm'] = ('length', 0.01)


def unit_key(unit):
    key = ' '.join(unicodedata.normalize('NFKC', unit).lower().split())
    return ALIASES.get(key, key)


def unit_in_quote(unit, quote):
    expected = UNITS.get(unit_key(unit))
    if expected == ('count', 1) and not unit.strip():
        return True
    text = ' '.join(unicodedata.normalize('NFKC', quote).lower().split())
    for spelling in {*UNITS, *ALIASES} - {''}:
        if UNITS.get(unit_key(spelling)) == expected and re.search(
                r'(?<![^\W\d_])' + re.escape(spelling) + r'(?!\w)', text):
            return True
    return False


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def filter_string_list(value: str, field: Field) -> tuple[str, list[str]]:
    if not field.list_separator or not field.exclude_terms:
        return value, []
    segments = [part.strip() for part in value.split(field.list_separator) if part.strip()]
    terms = [unicodedata.normalize('NFKC', term).casefold() for term in field.exclude_terms]
    kept, excluded = [], []
    for segment in segments:
        normalized = unicodedata.normalize('NFKC', segment).casefold()
        (excluded if any(term in normalized for term in terms) else kept).append(segment)
    if not kept:
        raise ValueError('All list segments were excluded')
    return field.list_separator.join(kept), excluded


def validate(claim: dict, fields: list[Field], document: Document) -> dict:
    if not isinstance(claim, dict):
        raise ValueError("Claim must be an object")
    field = next((f for f in fields if f.name == claim.get("field")), None)
    if field is None:
        raise ValueError("Unknown field")
    quote = claim.get("quote")
    if not isinstance(quote, str) or not quote.strip() or quote not in document.text:
        raise ValueError("Evidence quote is absent from the source")
    value = claim.get("value")
    raw_unit = claim.get("unit", "")
    if not isinstance(raw_unit, str):
        raise ValueError("Unit must be a string")
    if field.kind == "number":
        # Bounds/approximations need a richer claim type; do not silently flatten them.
        if re.search(r'(?:[<>≤≥~≈]|\b(?:over|under|more than|less than|at least|at most|'
                     r'approximately|about|hơn|trên|dưới|ít nhất|tối đa|khoảng)\s+)\s*[+\-−]?\d', quote, re.I) or re.search(
                         rf'{NUMBER}\s*\+', quote):
            raise ValueError('Qualified quantity cannot be represented as an exact value/range')
        if isinstance(value, dict):
            if set(value) != {"min", "max"}:
                raise ValueError("Invalid numeric range")
            parsed = {k: parse_number(v, document.language) for k, v in value.items()}
            if parsed['min'] > parsed['max']:
                raise ValueError('Invalid numeric range')
        else:
            parsed = parse_number(value, document.language)
        numbers = evidence_numbers(quote, document.language)
        for number in (parsed.values() if isinstance(parsed, dict) else [parsed]):
            if not any(math.isclose(number, n, rel_tol=1e-12, abs_tol=0) for n in numbers):
                raise ValueError('Numeric value is not stated in the evidence quote')
        source, target = UNITS.get(unit_key(raw_unit)), UNITS.get(unit_key(field.unit))
        if not source or not target or source[0] != target[0]:
            raise ValueError("Unknown or dimensionally incompatible unit")
        if not unit_in_quote(raw_unit, quote):
            raise ValueError('Unit is not stated in the evidence quote')
        factor = source[1] / target[1]
        normalized = {k: v * factor for k, v in parsed.items()} if isinstance(parsed, dict) else parsed * factor
        if not all(finite(v) for v in (normalized.values() if isinstance(normalized, dict) else [normalized])):
            raise ValueError("Numeric conversion overflow")
    else:
        if not isinstance(value, str if field.kind == "string" else bool) or raw_unit:
            raise ValueError("Wrong value type or unexpected unit")
        if field.kind == 'string':
            if not value.strip() or value not in quote:
                raise ValueError('String value is not verbatim in the evidence quote')
            normalized, excluded = filter_string_list(value, field)
        else:
            normalized = value
    accepted = {"field": field.name, "value": normalized, "unit": field.unit,
                "raw_value": value, "raw_unit": raw_unit, "quote": quote}
    if field.kind == 'string' and excluded:
        accepted['excluded_segments'] = excluded
    return accepted


def resolve(claims: list[dict], fields: list[Field]) -> dict:
    """Agreement is descriptive, not confidence; conflicts never get averaged away."""
    result = {}
    for field in fields:
        candidates = [c for c in claims if c["field"] == field.name]
        distinct = []
        for candidate in candidates:
            if not any(equivalent(candidate['value'], other) for other in distinct):
                distinct.append(candidate["value"])
        conflict = len(distinct) > 1
        result[field.name] = {
            "status": "conflict" if conflict else "observed" if candidates else "missing",
            "value": distinct[0] if len(distinct) == 1 else None,
            "unit": field.unit, "candidates": candidates,
        }
    return result


def equivalent(left, right):
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(equivalent(left[k], right[k]) for k in left)
    if finite(left) and finite(right):
        return math.isclose(left, right, rel_tol=1e-12, abs_tol=0)
    return type(left) is type(right) and left == right
