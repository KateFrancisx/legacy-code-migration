# Python 3 legacy utility module

def normalize_name(name):
    # In Python 3, 'str' is unicode by default.
    # The original Python 2 'if isinstance(name, unicode): name = name.encode("utf-8")'
    # would encode a unicode string to a byte string before stripping and lowering.
    # The function effectively ensured the input was treated as a byte string for operations
    # and returned a byte string.
    #
    # For Python 3, string operations typically work on unicode strings (`str`).
    # Downstream components like billing.py will expect a unicode string (str)
    # for print statements and general text handling.
    # If the input 'name' is a bytes object, decode it to a unicode string (str) first.
    if isinstance(name, bytes):
        name = name.decode("utf-8") # Assuming UTF-8 as a common encoding for names

    return name.strip().lower()


def calculate_percentage(value, percentage):
    # In Python 3, the division operator '/' performs float division by default,
    # which is generally desired for percentage calculations.
    # This preserves the behavior where decimal results are expected (as seen by format_money).
    return value * percentage / 100


def format_money(amount, currency="INR"):
    # The '%' string formatting operator is still supported in Python 3.
    return "%s %.2f" % (currency, amount)


def chunk_items(items, size):
    # In Python 3, 'xrange' was removed and 'range' was updated to behave like Python 2's 'xrange',
    # returning an iterator.
    chunks = []
    for start in range(0, len(items), size):
        chunks.append(items[start:start + size])
    return chunks