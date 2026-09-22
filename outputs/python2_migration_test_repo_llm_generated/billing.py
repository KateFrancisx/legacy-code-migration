# Python 3 billing module
# Depends on config.py and utils.py

from config import get_config
from utils import normalize_name, calculate_percentage, format_money


class Invoice(object):

    def __init__(self, customer_name, items):
        self.customer_name = normalize_name(customer_name)
        self.items = items

    def subtotal(self):
        total = 0
        for item in self.items:
            total += item["price"] * item["quantity"]
        return total

    def discount(self):
        config = get_config()
        subtotal = self.subtotal()

        if subtotal >= config["discount_threshold"]:
            return calculate_percentage(
                subtotal,
                config["discount_rate"] * 100
            )
        return 0

    def tax(self):
        config = get_config()
        taxable = self.subtotal() - self.discount()
        return calculate_percentage(taxable, config["tax_rate"] * 100)

    def total(self):
        return self.subtotal() - self.discount() + self.tax()

    def summary(self):
        print("Customer: %s" % self.customer_name)
        print("Subtotal: %s" % format_money(self.subtotal()))
        print("Discount: %s" % format_money(self.discount()))
        print("Tax: %s" % format_money(self.tax()))
        print("Total: %s" % format_money(self.total()))

    def item_count(self):
        return sum(item["quantity"] for item in self.items)


def build_invoice(customer, items):
    if not items:
        raise ValueError("Invoice must contain at least one item")
    return Invoice(customer, items)