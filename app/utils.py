def format_price(value):
    try:
        val = float(value)
    except (ValueError, TypeError):
        return str(value)
        
    if val == 0:
        return "0"
        
    abs_val = abs(val)
    if abs_val >= 1.0:
        formatted = f"{val:.2f}"
    elif abs_val >= 0.01:
        formatted = f"{val:.4f}"
    elif abs_val >= 0.000001:
        formatted = f"{val:.6f}"
    else:
        formatted = f"{val:.10f}"
        
    # Remove trailing zeros after decimal point
    if '.' in formatted:
        formatted = formatted.rstrip('0').rstrip('.')
        
    return formatted if formatted else "0"
