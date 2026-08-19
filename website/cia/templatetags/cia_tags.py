import re
from decimal import Decimal, InvalidOperation

from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
from pyvalem.formula import Formula, FormulaParseError

register = template.Library()

CHEMICAL_TOKEN = re.compile(
    r"(?<![A-Za-z0-9])(?:[A-Z][a-z]?\d*)+(?![A-Za-z0-9])"
)


@register.filter
def chemical_formula(value):
    """Render digits in a plain-text chemical formula as subscripts."""
    escaped = conditional_escape(value or "")
    return mark_safe(re.sub(r"(\d+)", r"<sub>\1</sub>", escaped))


@register.filter
def chemical_filename(value):
    """Subscript digits only in the chemical-system prefix of a filename."""
    escaped = str(conditional_escape(value or ""))
    system, separator, remainder = escaped.partition("_")
    formatted_system = re.sub(r"(\d+)", r"<sub>\1</sub>", system)
    return mark_safe(formatted_system + separator + remainder)


@register.filter
def reference_title(value):
    """Subscript digits in chemical formulae embedded in reference titles."""
    escaped = str(conditional_escape(value or ""))

    def format_token(match):
        token = match.group(0)
        if not any(character.isdigit() for character in token):
            return token
        try:
            return Formula(token).html
        except FormulaParseError:
            return token

    return mark_safe(CHEMICAL_TOKEN.sub(format_token, escaped))


@register.filter
def compact_number(value):
    """Display a JSON number without insignificant trailing zeroes."""
    try:
        rendered = format(Decimal(str(value)), "f")
    except (InvalidOperation, TypeError, ValueError):
        return value
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered
