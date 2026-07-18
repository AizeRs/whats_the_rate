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

def get_portfolio_details(portfolio_data, all_assets_cache, pref_symbol_tuple):
    """
    Calculates the total value and detailed asset list of a portfolio based on current asset prices.
    Returns a dictionary with 'assets' (formatted lists for UI) and 'sums' (totals).
    """
    sign, rate = pref_symbol_tuple
    
    details = {
        'assets': {'stocks': [], 'crypto': [], 'fiat': []},
        'sums': {
            'stocks_val': 0.0, 'stocks_str': f"0{sign}",
            'crypto_val': 0.0, 'crypto_str': f"0{sign}",
            'fiat_val': 0.0, 'fiat_str': f"0{sign}",
            'total_val': 0.0, 'total_str': f"0{sign}"
        }
    }
    
    def process_category(cat_name):
        category_sum = 0.0
        for current_asset, amount in portfolio_data.get(cat_name, {}).items():
            if current_asset in all_assets_cache[cat_name]:
                try:
                    name, price = all_assets_cache[cat_name][current_asset]
                    if price != "No price data":
                        item_price = float(price) * amount / rate
                        category_sum += item_price
                        details['assets'][cat_name].append({
                            'symbol': current_asset,
                            'name': name,
                            'number': f"x{amount}",
                            'price': f"{format_price(item_price)}{sign}",
                            'price_float': item_price
                        })
                except ValueError:
                    pass
        details['sums'][f'{cat_name}_val'] = category_sum
        details['sums'][f'{cat_name}_str'] = f"{format_price(category_sum)}{sign}"
        return category_sum
        
    stocks_sum = process_category('stocks')
    crypto_sum = process_category('crypto')
    fiat_sum = process_category('fiat')
    
    total = stocks_sum + crypto_sum + fiat_sum
    details['sums']['total_val'] = total
    details['sums']['total_str'] = f"{format_price(total)}{sign}"
    
    return details
