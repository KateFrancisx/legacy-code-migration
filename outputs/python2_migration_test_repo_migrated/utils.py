# Python 3 modernized utility module

def normalize_name(name):
    # In Python 3, all strings are unicode by default.
    # The explicit unicode check and encode are no longer necessary.
    return name.strip().lower()


def calculate_percentage(value, percentage):
    return value * percentage / 100


def format_money(amount, currency="INR"):
    return "%s %.2f" % (currency, amount)


def chunk_items(items, size):
    # xrange is replaced by range in Python 3.
    chunks = []
    for start in range(0, len(items), size):
        chunks.append(items[start:start + size])
    return chunks