# Python 3 utility module

def normalize_name(name):
    if isinstance(name, bytes):
        name = name.decode('utf-8')
    return name.strip().lower()


def calculate_percentage(value, percentage):
    return value * percentage / 100


def format_money(amount, currency="INR"):
    return f"{currency} {amount:.2f}"


def chunk_items(items, size):
    chunks = []
    for start in range(0, len(items), size):
        chunks.append(items[start:start + size])
    return chunks