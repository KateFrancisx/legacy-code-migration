# Python 2 legacy application entry point
# Depends on billing.py

from billing import build_invoice
from utils import chunk_items


def create_demo_invoice():
    items = [
        {"name": "Keyboard", "price": 1200, "quantity": 1},
        {"name": "Mouse", "price": 500, "quantity": 2},
        {"name": "USB Cable", "price": 150, "quantity": 3}
    ]

    invoice = build_invoice("Alice", items)

    print("=== Legacy Billing Demo ===")
    invoice.summary()

    # Demonstrates a dependency on a utility using xrange.
    batches = chunk_items(items, 2)
    print("Number of item batches: %d" % len(batches))

    return invoice


if __name__ == "__main__":
    create_demo_invoice()