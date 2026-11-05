import unittest
from decimal import Decimal

from billing.invoice import apply_discount, line_total, subtotal, total

LINES = [
    {"unit_price": "50.00", "quantity": 2},
    {"unit_price": "25.00", "quantity": 4},
]


class InvoiceTest(unittest.TestCase):
    def test_line_total(self):
        self.assertEqual(line_total("19.99", 3), Decimal("59.97"))

    def test_subtotal(self):
        self.assertEqual(subtotal(LINES), Decimal("200.00"))

    def test_discount_is_a_percentage(self):
        self.assertEqual(apply_discount(Decimal("200.00"), 10), Decimal("180.00"))

    def test_total_with_discount_and_tax(self):
        self.assertEqual(total(LINES, discount_percent=10), Decimal("198.00"))

    def test_total_without_discount(self):
        self.assertEqual(total(LINES), Decimal("220.00"))


if __name__ == "__main__":
    unittest.main()
