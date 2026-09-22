# Python 2 legacy configuration

TAX_RATE = 0.18
DISCOUNT_THRESHOLD = 1000
DISCOUNT_RATE = 0.10
CURRENCY = "INR"

def get_config():
    return {
        "tax_rate": TAX_RATE,
        "discount_threshold": DISCOUNT_THRESHOLD,
        "discount_rate": DISCOUNT_RATE,
        "currency": CURRENCY
    }
