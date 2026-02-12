import logging

logger = logging.getLogger(__name__)

# Approximate exchange rates to USD (updated periodically).
# Prices are stored in USD cents.
RATES_TO_USD: dict[str, float] = {
    "USD": 1.0,
    "EUR": 1.08,
    "GBP": 1.27,
    "CHF": 1.13,
    "JPY": 0.0067,
    "AUD": 0.65,
    "CAD": 0.74,
    "SGD": 0.75,
    "HKD": 0.128,
    "CNY": 0.14,
}

CURRENCY_SYMBOLS: dict[str, str] = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "CHF": "CHF",
    "A$": "AUD",
    "C$": "CAD",
    "S$": "SGD",
    "HK$": "HKD",
}


def convert_to_usd_cents(amount: float, currency: str = "USD") -> int:
    """Convert a price in the given currency to USD cents.

    Args:
        amount: Price in the original currency (dollars, not cents).
        currency: ISO 4217 currency code (default USD).

    Returns:
        Price in USD cents.
    """
    currency = currency.upper()
    rate = RATES_TO_USD.get(currency)
    if rate is None:
        logger.warning("Unknown currency '%s', treating as USD", currency)
        rate = 1.0
    return int(amount * rate * 100)


def detect_currency(price_text: str) -> tuple[float, str]:
    """Try to detect currency and extract numeric value from price text.

    Returns:
        (amount, currency_code) tuple.
    """
    text = price_text.strip()

    # Check symbol prefixes/suffixes
    for symbol, code in sorted(
        CURRENCY_SYMBOLS.items(), key=lambda x: len(x[0]), reverse=True
    ):
        if text.startswith(symbol) or text.endswith(symbol):
            numeric = text.replace(symbol, "").replace(",", "").strip()
            try:
                return float(numeric), code
            except ValueError:
                continue

    # Fallback: just parse number, assume USD
    cleaned = text.replace(",", "").replace("$", "").strip()
    try:
        return float(cleaned), "USD"
    except ValueError:
        raise ValueError(f"Cannot parse price from '{price_text}'")
