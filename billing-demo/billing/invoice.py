"""Invoice totals for the billing demo."""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def line_total(unit_price, quantity):
    return (Decimal(unit_price) * quantity).quantize(CENT, ROUND_HALF_UP)


def subtotal(lines):
    return sum((line_total(line["unit_price"], line["quantity"]) for line in lines), Decimal("0"))


def apply_discount(amount, percent):
    """Takes percent off amount, e.g. 10 for 10%."""
    return (amount - Decimal(percent)).quantize(CENT, ROUND_HALF_UP)


def total(lines, discount_percent=0, tax_rate="0.10"):
    discounted = apply_discount(subtotal(lines), discount_percent)
    return (discounted * (1 + Decimal(tax_rate))).quantize(CENT, ROUND_HALF_UP)
