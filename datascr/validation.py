import math
import re
import unicodedata

from .contracts import Document, Field
from .numbers import NUMBER, evidence_numbers, parse_number, word_numbers

# Explicit dimensional conversions only. Unknown units are rejected, never guessed.
UNITS = {
    "m": ("length", 1), "metres": ("length", 1), "meters": ("length", 1),
    "ft": ("length", 0.3048), "km": ("length", 1000), "mm": ("length", 0.001),
    "t": ("mass", 1), "tonnes": ("mass", 1), "kg": ("mass", 0.001),
    "long tons": ("mass", 1.0160469088), "short tons": ("mass", 0.90718474),
    "ps": ("power", 735.49875), "w": ("power", 1), "kw": ("power", 1000),
    "mw": ("power", 1000000), "hp": ("power", 745.6998715822702),
    "shp": ("power", 745.6998715822702),
    "days": ("duration", 86400), "h": ("duration", 3600),
    "kn": ("speed", 1), "knots": ("speed", 1), "km/h": ("speed", 1 / 1.852),
    "m/s": ("speed", 3.6 / 1.852), "nmi": ("length", 1852),
    "": ("count", 1), "persons": ("count", 1),
}

ALIASES = {'metre': 'm', 'meter': 'm', 'mét': 'm', 'mètres': 'm', 'cm': 'cm',
           'feet': 'ft', 'foot': 'ft', 'tonne': 't', 'tấn': 't', 'knot': 'kn',
           'kts': 'kn', 'kt': 'kn', 'day': 'days', 'người': 'persons', 'people': 'persons',
           'person': 'persons', 'kilograms': 'kg', 'kilogram': 'kg',
           'hours': 'h', 'hour': 'h', '日': 'days', '名': 'persons',
           '人': 'persons', '海里': 'nmi', 'ノット': 'kn',
           'トン': 't', 'メートル': 'm', 'ミリ': 'mm', 'inch': 'in', 'inches': 'in', 'インチ': 'in'}
UNITS['cm'] = ('length', 0.01)
UNITS['in'] = ('length', 0.0254)


def quote_quantities(quote, language):
    text = unicodedata.normalize('NFKC', quote)
    text = re.sub(r'(?<=\d)[x×](?=\d)', ' × ', text)
    for match in re.finditer(rf'(?<![A-Za-z0-9_]){NUMBER}', text):
        try:
            yield parse_number(match[0], language), match, text
        except ValueError:
            continue
    for value, match in word_numbers(text, language):
        yield value, match, text


def qualifier_for(number, quote, language):
    found = set()
    for value, match, text in quote_quantities(quote, language):
        if not math.isclose(number, value, rel_tol=1e-12, abs_tol=0):
            continue
        left, right = text[:match.start()], text[match.end():]
        qualifier = 'exact'
        for pattern, result in [
            (r'(?:approximately|about|around|circa|khoảng|約|およそ|[~≈])\s*$', 'approx'),
            (r'(?:at least|>=|≥|ít nhất)\s*$', 'gte'),
            (r'(?:at most|<=|≤|tối đa)\s*$', 'lte'),
            (r'(?:more than|over|hơn|trên|>)\s*$', 'gt'),
            (r'(?:less than|under|dưới|<)\s*$', 'lt')]:
            if re.search(pattern, left, re.I):
                qualifier = result
                break
        # Japanese quantity suffixes and the common "30+" notation.
        suffix = re.match(r'^\s*(?:名|人|ノット|kt|knots|kn|t|m)?\s*(以上|以下|未満|超|\+)', right)
        if suffix:
            qualifier = {'以上': 'gte', '以下': 'lte', '未満': 'lt', '超': 'gt', '+': 'gte'}[suffix[1]]
        found.add(qualifier)
    if len(found) != 1:
        raise ValueError('Ambiguous quantity qualifier')
    return found.pop()


def quantity_unit_supported(number, raw_unit, quote, language):
    if not raw_unit.strip():
        return True
    expected = UNITS.get(unit_key(raw_unit))
    for value, match, text in quote_quantities(quote, language):
        if not math.isclose(value, number, rel_tol=1e-12, abs_tol=0):
            continue
        tail = text[match.end():].lower()
        head = text[:match.start()].lower()
        tail = re.sub(rf'^\s*[–—-]\s*{NUMBER}\s*', '', tail)
        for spelling in {*UNITS, *ALIASES} - {''}:
            if UNITS.get(unit_key(spelling)) == expected and re.search(
                    r'(?:^|[,（(])\s*' + re.escape(spelling) + r'\s*[)）]?\s*[:：]\s*$', head):
                return True
            if UNITS.get(unit_key(spelling)) == expected and re.match(
                    r'^\s*' + re.escape(spelling) + r'(?![a-z_])', tail):
                return True
    return False


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
                r'(?<![A-Za-z_])' + re.escape(spelling) + r'(?![A-Za-z_])', text):
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
    if field.kind == 'records':
        return validate_records(claim, field, document)
    quote = claim.get("quote")
    if not isinstance(quote, str) or not quote.strip() or quote not in document.text:
        raise ValueError("Evidence quote is absent from the source")
    value = claim.get("value")
    raw_unit = claim.get("unit", "")
    if not isinstance(raw_unit, str):
        raise ValueError("Unit must be a string")
    if field.kind == "number":
        # Bounds/approximations need a richer claim type; do not silently flatten them.
        if not field.allow_qualified and (re.search(r'(?:[<>≤≥~≈]|\b(?:over|under|more than|less than|at least|at most|'
                     r'approximately|about|hơn|trên|dưới|ít nhất|tối đa|khoảng)\s+)\s*[+\-−]?\d', quote, re.I) or re.search(
                         rf'{NUMBER}\s*\+', quote)):
            raise ValueError('Qualified quantity cannot be represented as an exact value/range')
        if isinstance(value, dict):
            if set(value) != {"min", "max"}:
                raise ValueError("Invalid numeric range")
            parsed = {k: parse_number(v, document.language) for k, v in value.items()}
            if parsed['min'] > parsed['max']:
                raise ValueError('Invalid numeric range')
            range_text = unicodedata.normalize('NFKC', quote)
            explicit = False
            for match in re.finditer(rf'({NUMBER})\s*(?:[–—-]|\bto\b)\s*({NUMBER})', range_text, re.I):
                try:
                    explicit |= (parse_number(match[1], document.language) == parsed['min']
                                 and parse_number(match[2], document.language) == parsed['max'])
                except ValueError:
                    pass
            if not explicit:
                raise ValueError('Numeric range requires an explicit contiguous range in evidence')
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
        for number in (parsed.values() if isinstance(parsed, dict) else [parsed]):
            if not quantity_unit_supported(number, raw_unit, quote, document.language):
                raise ValueError('Unit is not attached to the claimed quantity')
        qualifier = 'exact'
        if not isinstance(parsed, dict):
            qualifier = qualifier_for(parsed, quote, document.language)
            if qualifier != 'exact' and not field.allow_qualified:
                raise ValueError('Qualified quantity requires allow_qualified')
            if claim.get('qualifier', 'exact') != qualifier:
                raise ValueError('Quantity qualifier does not match source')
        elif claim.get('qualifier', 'exact') != 'exact':
            raise ValueError('Qualified ranges are not supported yet')
        factor = source[1] / target[1]
        normalized = {k: v * factor for k, v in parsed.items()} if isinstance(parsed, dict) else parsed * factor
        if not all(finite(v) for v in (normalized.values() if isinstance(normalized, dict) else [normalized])):
            raise ValueError("Numeric conversion overflow")
        if qualifier != 'exact':
            normalized = {'amount': normalized, 'qualifier': qualifier}
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
    context = claim.get('context', {})
    if not isinstance(context, dict) or any(
            k not in {'subject', 'date', 'condition'} or not isinstance(v, str)
            or not v.strip() or v not in document.text for k, v in context.items()):
        raise ValueError('Context must quote source subject/date/condition')
    if context:
        accepted['context'] = context
    if field.kind == 'string' and excluded:
        accepted['excluded_segments'] = excluded
    return accepted


def validate_records(claim, field, document):
    raw = claim.get('value')
    if not isinstance(raw, list) or not raw:
        raise ValueError('Record value must be a nonempty list')
    values, evidence, rejected = [], [], []
    for index, record in enumerate(raw):
        try:
            if not isinstance(record, dict) or not isinstance(record.get('quote'), str):
                raise ValueError('Record requires a quote')
            quote = record['quote']
            if not quote.strip() or quote not in document.text:
                raise ValueError('Record quote absent from source')
            context = record.get('context', claim.get('context', {}))
            leaves = record.get('properties')
            if not isinstance(leaves, dict) or 'name' not in leaves:
                raise ValueError('Record requires properties.name')
            accepted, leaf_evidence = {}, {}
            for key, leaf in leaves.items():
                try:
                    if key not in field.properties or not isinstance(leaf, dict):
                        raise ValueError('Unknown property or malformed evidence')
                    spec = field.properties[key]
                    if not isinstance(leaf.get('quote'), str) or leaf['quote'] not in quote:
                        raise ValueError('Property quote must belong to this record')
                    property_field = Field(key, spec.get('description', ''), kind=spec.get('kind', 'string'),
                                           unit=spec.get('unit', ''), allow_qualified=spec.get('allow_qualified', False))
                    checked = validate({**leaf, 'field': key, 'context': context},
                                       [property_field], document)
                    accepted[key] = checked['value']
                    leaf_evidence[key] = checked
                except ValueError as exc:
                    rejected.append({'record': index, 'property': key, 'message': str(exc), 'raw': leaf})
            if 'name' not in accepted:
                raise ValueError('Record name not supported')
            if context:
                accepted['context'] = context
            values.append(accepted)
            evidence.append({'quote': quote, 'properties': leaf_evidence})
        except ValueError as exc:
            rejected.append({'record': index, 'message': str(exc), 'raw': record})
    if not values:
        raise ValueError('No supported records')
    return {'field': field.name, 'value': values, 'unit': '', 'raw_value': raw,
            'raw_unit': '', 'quote': '', 'record_evidence': evidence, 'rejected_properties': rejected}


def resolve(claims: list[dict], fields: list[Field]) -> dict:
    """Agreement is descriptive, not confidence; conflicts never get averaged away."""
    result = {}
    for field in fields:
        candidates = [c for c in claims if c["field"] == field.name]
        distinct = []
        if field.kind == 'records':
            values = []
            for candidate in candidates:
                for item in candidate['value']:
                    scoped = {**item, 'source_scope': candidate.get('source_scope', '')}
                    if scoped not in values:
                        values.append(scoped)
            conflicts = []
            for i, left in enumerate(values):
                for right in values[i + 1:]:
                    if (left.get('name'), left.get('context'), left['source_scope']) != (
                            right.get('name'), right.get('context'), right['source_scope']):
                        continue
                    differing = [k for k in left.keys() & right.keys()
                                 if k not in {'context', 'source_scope'} and not equivalent(left[k], right[k])]
                    if differing:
                        conflicts.append({'name': left['name'], 'properties': differing,
                                          'candidates': [left, right]})
            result[field.name] = {'status': 'conflict' if conflicts else 'observed' if values else 'missing',
                                  'value': values or None, 'unit': '', 'candidates': candidates,
                                  'conflicts': conflicts}
            continue
        contexts = {(c.get('source_scope', ''), tuple(sorted(c.get('context', {}).items()))) for c in candidates}
        for candidate in candidates:
            if not any(equivalent(candidate['value'], other) for other in distinct):
                distinct.append(candidate["value"])
        scope_groups = []
        for scope, context in sorted(contexts):
            group_candidates = [c for c in candidates if c.get('source_scope', '') == scope
                                and tuple(sorted(c.get('context', {}).items())) == context]
            group_values = []
            for candidate in group_candidates:
                if not any(equivalent(candidate['value'], v) for v in group_values):
                    group_values.append(candidate['value'])
            scope_groups.append({'source_scope': scope, 'context': dict(context),
                                 'status': 'conflict' if len(group_values) > 1 else 'observed',
                                 'values': group_values, 'candidates': group_candidates})
        conflict = any(g['status'] == 'conflict' for g in scope_groups)
        scoped = len(contexts) > 1
        result[field.name] = {
            "status": "conflict" if conflict else "scoped" if scoped else "observed" if candidates else "missing",
            "value": distinct[0] if len(distinct) == 1 and not scoped else None,
            "unit": field.unit, "candidates": candidates, "scope_groups": scope_groups,
        }
    return result


def equivalent(left, right):
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(equivalent(left[k], right[k]) for k in left)
    if finite(left) and finite(right):
        return math.isclose(left, right, rel_tol=1e-12, abs_tol=0)
    return type(left) is type(right) and left == right
