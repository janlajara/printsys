from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone

from inventory.models import (
    Item, Supplier, StockMovement, StockMovementPurpose
)

User = get_user_model()


class InventoryModelTests(TestCase):
    """
    Unit tests for inventory models with inline fixtures.
    Data is created once per class via setUpTestData().
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="tester", password="testpass123")

        cls.supplier = Supplier.objects.create(
            name="Acme Supplies",
            contact_person="John Doe",
            email="acme@example.com",
            phone="123456789",
            address="123 Warehouse Lane",
            notes="Preferred supplier",
        )

        cls.purpose = StockMovementPurpose.objects.create(
            name="Purchase",
            description="Stock purchased from supplier",
            is_active=True,
        )

        cls.item = Item.objects.create(
            name="Printer Ink",
            description="Black ink cartridge",
            individual_uom="piece",
            pack_uom="box",
            pack_quantity=10,
        )

    def test_initial_stock_is_zero(self):
        self.assertEqual(self.item.current_quantity, 0)

    def test_deposit_individual_units(self):
        self.item.deposit(quantity=5, user=self.user, purpose=self.purpose)
        self.assertEqual(self.item.current_quantity, 5)

    def test_deposit_packed_units(self):
        self.item.deposit(quantity=2, user=self.user, is_packed=True, supplier=self.supplier)
        self.assertEqual(self.item.current_quantity, 20)

    def test_withdraw_individual_units(self):
        self.item.deposit(quantity=10, user=self.user)
        self.item.withdraw(quantity=4, user=self.user)
        self.assertEqual(self.item.current_quantity, 6)

    def test_withdraw_packed_units(self):
        self.item.deposit(quantity=5, user=self.user, is_packed=True)
        self.item.withdraw(quantity=2, user=self.user, is_packed=True)
        self.assertEqual(self.item.current_quantity, 30)

    def test_withdraw_insufficient_stock_raises_error(self):
        self.item.deposit(quantity=3, user=self.user)
        with self.assertRaises(ValidationError):
            self.item.withdraw(quantity=5, user=self.user)

    def test_deposit_negative_quantity_raises_error(self):
        with self.assertRaises(ValidationError):
            self.item.deposit(quantity=-10, user=self.user)

    def test_withdraw_negative_quantity_raises_error(self):
        with self.assertRaises(ValidationError):
            self.item.withdraw(quantity=-2, user=self.user)

    def test_supplier_tracking_on_deposit(self):
        self.item.deposit(quantity=10, user=self.user, supplier=self.supplier)
        total = self.supplier.total_supplied_for_item(self.item)
        self.assertEqual(total, 10)

    def test_supplier_total_summary(self):
        self.item.deposit(quantity=10, user=self.user, supplier=self.supplier)
        self.item.deposit(quantity=1, user=self.user, is_packed=True, supplier=self.supplier)
        total = self.supplier.total_supplied_for_item(self.item)
        self.assertEqual(total, 20)

    def test_supplied_between_dates(self):
        now = timezone.now()
        earlier = now - timezone.timedelta(days=5)
        later = now + timezone.timedelta(days=5)
        self.item.deposit(quantity=10, user=self.user, supplier=self.supplier)
        results = self.supplier.supplied_between(earlier, later)
        self.assertEqual(results.count(), 1)

    def test_item_suppliers_summary(self):
        self.item.deposit(quantity=5, user=self.user, supplier=self.supplier)
        summary = list(self.item.suppliers_summary())
        self.assertEqual(summary[0]['supplier__name'], self.supplier.name)
        self.assertEqual(summary[0]['total'], 5)

    def test_movement_str_representation(self):
        self.item.deposit(quantity=2, user=self.user, is_packed=True, supplier=self.supplier)
        movement = StockMovement.objects.first()
        self.assertIn("DEPOSIT", str(movement))
        self.assertIn("box", str(movement))
        self.assertIn("Acme Supplies", str(movement))

    def test_quantity_in_individual_units_property(self):
        movement = StockMovement.objects.create(
            item=self.item,
            user=self.user,
            movement_type=StockMovement.DEPOSIT,
            quantity=3,
            is_packed=True,
        )
        self.assertEqual(movement.quantity_in_individual_units, 30)
