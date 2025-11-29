import inflect
from decimal import Decimal, InvalidOperation
from django.urls import reverse_lazy
from django.utils.html import format_html

p = inflect.engine()

def format_currency(amount, currency="₱"):
    """
    Format a numeric value as Philippine Peso currency.
    
    Args:
        amount (Decimal, float, int, str, or None): The value to format.
        
    Returns:
        str: Formatted currency string, e.g., "₱1,234.56". Returns "₱0.00" for empty values.
    """
    if amount in (None, "", 0):
        return f"{currency} 0.00"
    
    try:
        # Convert to Decimal for consistent formatting
        value = Decimal(amount)
    except (InvalidOperation, ValueError, TypeError):
        return f"{currency} 0.00"
    
    # Format with thousands separator and 2 decimal places
    return f"{currency} {value:,.2f}"


def to_link(path_name, id, name):
    url = reverse_lazy(
        path_name,
        args=[id]
    )
    return format_html('<a href="{}" class="hover:text-primary-600 dark:hover:text-primary-500 text-primary-600 dark:text-primary-500">{}</a>', url, name)


def pluralize_uom(quantity, unit_of_measure):
    return f"{quantity} {p.plural(unit_of_measure, quantity)}"
