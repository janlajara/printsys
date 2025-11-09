from decimal import Decimal, InvalidOperation

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