"""Conservative locale-aware numbers; ambiguous formats are never guessed."""
import math
import re
import unicodedata

NUMBER = r"[+\-−]?\d+(?:[.,]\d+|[ \u00a0\u202f]\d{3}(?!\d))*(?:[eE][+\-]?\d+)?"
COMMA_DECIMAL = {'vi', 'de', 'fr', 'es', 'it', 'pt', 'ru', 'pl', 'nl', 'tr', 'uk'}
DOT_DECIMAL = {'en', 'zh', 'ja', 'ko'}


def parse_number(value, language='und'):
    if type(value) in (int, float):
        try:
            if math.isfinite(value):
                return value
        except OverflowError:
            pass
        raise ValueError('Expected finite number')
    if not isinstance(value, str):
        raise ValueError('Expected number or numeric string')
    text = unicodedata.normalize('NFKC', value).strip().replace('−', '-')
    if not re.fullmatch(NUMBER, text):
        raise ValueError('Invalid numeric syntax')
    mantissa, *exponent = re.split('[eE]', text)
    language = language.split('-')[0].lower()
    decimal = ',' if language in COMMA_DECIMAL else '.' if language in DOT_DECIMAL else None
    if decimal is None:
        separators = [c for c in '.,' if c in mantissa]
        if len(separators) == 2:
            raise ValueError('Numeric locale required for mixed separators')
        if separators:
            sep = separators[0]
            if mantissa.count(sep) != 1 or len(mantissa.split(sep)[1]) == 3:
                raise ValueError('Ambiguous number requires language')
            decimal = sep
        else:
            decimal = '.'
    grouping = ',' if decimal == '.' else '.'
    pieces = mantissa.split(decimal)
    if len(pieces) > 2:
        raise ValueError('Multiple decimal separators')
    integer = pieces[0]
    fraction = pieces[1] if len(pieces) == 2 else None
    if fraction is not None and not fraction.isdigit():
        raise ValueError('Invalid fractional part')
    if grouping in integer or ' ' in integer:
        separator = grouping if grouping in integer else ' '
        if not re.fullmatch(r'[+\-]?\d{1,3}(?:' + re.escape(separator) + r'\d{3})+', integer):
            raise ValueError('Invalid thousands grouping')
        integer = integer.replace(separator, '')
    normalized = integer + ('.' + fraction if fraction is not None else '')
    if exponent:
        normalized += 'e' + exponent[0]
    number = float(normalized)
    if not math.isfinite(number):
        raise ValueError('Expected finite number')
    return number


def parse_quantity(text, language):
    match = re.fullmatch(rf'\s*({NUMBER})(?:\s*[–—-]\s*({NUMBER}))?\s*([^\d]*)', text)
    if not match:
        raise ValueError('Unsupported quantity syntax')
    value = parse_number(match[1], language)
    if match[2] is not None:
        value = {'min': value, 'max': parse_number(match[2], language)}
        if value['min'] > value['max']:
            raise ValueError('Reversed range')
    return value, match[3].strip()


def evidence_numbers(quote, language):
    # Replace range dashes only when separating numbers; keep unary minus signs.
    text = unicodedata.normalize('NFKC', quote)
    text = re.sub(r'(?<=\d)\s*[–—-]\s*(?=[+\-−]?\d)', ' | ', text)
    values = []
    for match in re.finditer(rf'(?<![\w.,]){NUMBER}(?!\d|[.,]\d)', text):
        try:
            values.append(parse_number(match[0], language))
        except ValueError:
            continue
    return values
