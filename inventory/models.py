from django.db import models
from django.db.models import (
    Sum, F, Case, When, IntegerField, DecimalField, 
    CharField, Avg, Count, Q, Subquery, OuterRef
)
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.postgres.fields import ArrayField
from django.contrib.auth import get_user_model

User = get_user_model()


class Supplier(models.Model):
    """
    Represents a supplier from whom items are procured.
    """
    name = models.CharField(max_length=255, unique=True)
    contact_person = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.name
    
    def total_supplied_items(self):
        """
        Returns total supplied quantities per item (in individual units).
        """
        movements = self.movements.filter(movement_type='DEPOSIT')
        summary = (
            movements
            .values('item__name', 'item__individual_uom')
            .annotate(total=Sum(
                Case(
                    When(is_packed=True, then=F('quantity') * F('pack_quantity')),
                    default=F('quantity'),
                    output_field=IntegerField(),
                )
            ))
            .order_by('item__name')
        )
        return summary

    def total_supplied_for_item(self, item):
        """
        Returns the total supplied quantity (in individual units) for a specific item.
        """
        return (
            self.movements
            .filter(movement_type='DEPOSIT', item=item)
            .aggregate(total=Sum(
                Case(
                    When(is_packed=True, then=F('quantity') * F('pack_quantity')),
                    default=F('quantity'),
                    output_field=IntegerField(),
                )
            ))['total']
            or 0
        )

    def supplied_between(self, start_date, end_date):
        """
        Returns all movements supplied by this supplier between two dates.
        """
        return self.movements.filter(
            movement_type='DEPOSIT',
            timestamp__range=(start_date, end_date),
        )
    
    def items_summary(self):
        """
        Returns all items provided by the supplier
        """        
        summary = (
            self.movements.filter(movement_type='DEPOSIT', supplier__id=self.pk)
            .values('item__name', 'item__id')
            .annotate(
                total=Sum(
                    Case(
                        When(is_packed=True, then=F('quantity') * F('pack_quantity')),
                        default=F('quantity'),
                        output_field=IntegerField(),
                    )
                ),
                latest_price=Subquery(StockMovement.Query.latest_price(self.movements))
            )
            .order_by('item__name')
        )
        return summary
    

class ItemCategory(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    attributes = ArrayField(
        models.CharField(max_length=50),
        blank=True,
        default=list,
    )

    class Meta:
        verbose_name = "Item category"
        verbose_name_plural = "Item categories"

    def __str__(self):
        return self.name


class Item(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.ForeignKey(ItemCategory, on_delete=models.SET_NULL, 
                                 related_name='items', null=True, blank=True)
    attributes = models.JSONField(default=dict, null=True, blank=True)

    # Units of measure
    individual_uom = models.CharField(
        max_length=50,
        help_text="Unit of measure for individual items (e.g. piece, bottle)."
    )
    pack_uom = models.CharField(
        max_length=50,
        help_text="Unit of measure for packs (e.g. box, carton).",
        null=True, blank=True
    )

    # Conversion rate: number of individual units per pack
    pack_quantity = models.PositiveIntegerField(default=1, help_text="Number of individual units per pack")

    def __str__(self):
        attributes = " ".join(list(self.attributes.values()))
        return " ".join([self.name, attributes])

    def save(self, *args, **kwargs):
        self.description = " ".join([f"{self.name}", *self.attributes.values()])
        super().save(*args, **kwargs)

    @property
    def current_quantity(self):
        """
        Total available stock for this item in individual units.
        Movement quantities are normalized to individual units.
        """
        total = self.movements.aggregate(
            total=Sum(
                Case(
                    When(
                        movement_type='DEPOSIT',
                        then=F('quantity')
                        * Case(
                            When(is_packed=True, then=F('pack_quantity')),
                            default=1,
                            output_field=IntegerField(),
                        ),
                    ),
                    When(
                        movement_type='WITHDRAW',
                        then=-1
                        * F('quantity')
                        * Case(
                            When(is_packed=True, then=F('pack_quantity')),
                            default=1,
                            output_field=IntegerField(),
                        ),
                    ),
                    default=0,
                    output_field=IntegerField(),
                )
            )
        )['total']
        return total or 0
    
    def suppliers_summary(self):
        """
        Returns a breakdown of how much each supplier has provided for this item.
        """        
        summary = (
            self.movements.filter(movement_type='DEPOSIT', supplier__isnull=False)
            .values('supplier__name', 'supplier__id')
            .annotate(
                total=Sum(
                    Case(
                        When(is_packed=True, then=F('quantity') * F('pack_quantity')),
                        default=F('quantity'),
                        output_field=IntegerField(),
                    )
                ),
                latest_price=Subquery(StockMovement.Query.latest_price(self.movements))
            )
            .order_by('-total')
        )
        return summary

    def deposit(self, quantity, user, is_packed=False, supplier=None, remarks='', purpose=None, unit_price=None):
        """
        Add stock. If packed, quantity is multiplied by pack_quantity.
        """
        if quantity <= 0:
            raise ValidationError("Deposit quantity must be positive.")

        StockMovement.objects.create(
            item=self,
            user=user,
            movement_type=StockMovement.DEPOSIT,
            quantity=quantity,
            is_packed=is_packed,
            pack_quantity=self.pack_quantity if is_packed else 1,
            supplier=supplier,
            remarks=remarks,
            purpose=purpose,
            unit_price=unit_price
        )

    def withdraw(self, quantity, user, is_packed=False, remarks='', purpose=None):
        """
        Withdraw stock. If packed, quantity is multiplied by pack_quantity.
        """
        if quantity <= 0:
            raise ValidationError("Withdraw quantity must be positive.")

        units_to_withdraw = quantity * self.pack_quantity if is_packed else quantity
        if units_to_withdraw > self.current_quantity:
            raise ValidationError("Insufficient stock to withdraw.")

        StockMovement.objects.create(
            item=self,
            user=user,
            movement_type=StockMovement.WITHDRAW,
            quantity=quantity,
            is_packed=is_packed,
            pack_quantity=self.pack_quantity if is_packed else 1,
            remarks=remarks,
            purpose=purpose
        )


class StockMovementPurpose(models.Model):
    """
    Defines valid purposes for stock movements (dynamic, editable at runtime).
    Example: Purchase, Return, Production Use, Adjustment
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
    

class StockMovement(models.Model):

    class Query:
        TOTAL_WITHDRAW_MOVEMENT = Count("id", filter=Q(movement_type="WITHDRAW"))
        TOTAL_WITHDRAW_UNITS =(
            Sum(
                Case(
                    When(
                        movement_type="WITHDRAW",
                        then=F('quantity')
                        * Case(
                            When(is_packed=True, then=F('pack_quantity')),
                            default=1,
                            output_field=IntegerField(),
                        ),
                    ),
                    default=0,
                    output_field=IntegerField(),
                )
            )
        )
        TOTAL_DEPOSIT_MOVEMENT = Count("id", filter=Q(movement_type="DEPOSIT"))
        TOTAL_DEPOSIT_UNITS = (
            Sum(
                Case(
                    When(
                        movement_type='DEPOSIT',
                        then=F('quantity')
                        * Case(
                            When(is_packed=True, then=F('pack_quantity')),
                            default=1,
                            output_field=IntegerField(),
                        ),
                    ),
                    default=0,
                    output_field=IntegerField(),
                )
            )
        )

        def latest_price(movements):
            return (
                movements
                .filter(
                    movement_type='DEPOSIT',
                    supplier=OuterRef('supplier__id'), # match the supplier of the group
                    unit_price__isnull=False,          # ensure price exists
                )
                .annotate(
                    computed_unit_price=(
                        Case(
                            When(
                                is_packed=True,
                                then=F('unit_price') / F('pack_quantity')
                            ),
                            default=F('unit_price'),
                            output_field=DecimalField(),
                        )
                    )
                )
                .order_by('-timestamp')                # newest record first
                .values('computed_unit_price')[:1]
            )
            

    DEPOSIT = 'DEPOSIT'
    WITHDRAW = 'WITHDRAW'
    MOVEMENT_TYPES = [
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAW', 'Withdraw'),
    ]

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=10, choices=MOVEMENT_TYPES)
    quantity = models.PositiveIntegerField()
    is_packed = models.BooleanField(default=False)
    pack_quantity = models.PositiveIntegerField(default=1)
    timestamp = models.DateTimeField(default=timezone.now)
    remarks = models.TextField(blank=True)
    purpose = models.ForeignKey(
        StockMovementPurpose,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movements',
        help_text="Purpose of this stock movement (editable in admin)."
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movements',
        help_text="Supplier associated with this stock movement, if applicable."
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements',
        help_text="User who facilitated this stock movement."
    )
    unit_price = models.DecimalField(decimal_places=2, max_digits=12, null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        unit_type = self.item.pack_uom if self.is_packed else self.item.individual_uom
        supplier_info = f" from {self.supplier.name}" if self.supplier else ""
        return f"{self.movement_type} {self.quantity} {unit_type} of {self.item.name}{supplier_info}"

    @property
    def quantity_in_individual_units(self):
        """
        Converts to base (individual) units for stock calculations.
        """
        if self.is_packed:
            return self.quantity * self.pack_quantity
        return self.quantity
    
    @classmethod
    def get_movement_history(cls, start_date, end_date):
        movement_history = (
            StockMovement.objects
                .filter(timestamp__date__range=[start_date, end_date])
                .annotate(
                    uom=Case(
                        When(is_packed=True, then=F('item__pack_uom')),
                        default=F('item__individual_uom'),
                        output_field=CharField(),
                    )
                )
                .values( 'timestamp', 'item__id', 'item__name', 'quantity', 'uom', 'purpose__name', 'remarks')
        )
        return movement_history
    
    @classmethod
    def get_movement_by_day(cls, start_date, end_date):
        movement_by_day = (
            StockMovement.objects
                .filter(timestamp__date__range=[start_date, end_date])
                .annotate(
                    day=TruncDate('timestamp'), # truncate to date only
                )
                .values('day')
                .annotate(
                    total_deposit=StockMovement.Query.TOTAL_DEPOSIT_MOVEMENT,
                    total_withdraw=StockMovement.Query.TOTAL_WITHDRAW_MOVEMENT,)
                .order_by('day'),  # sort by day ascending
        )[0]
        return movement_by_day
    
    @classmethod
    def get_summary(cls, start_date, end_date):
        """
        Returns aggregated total deposits and withdrawals per item
        within the given date range.
        """
        return (
            cls.objects
            .filter(timestamp__date__range=[start_date, end_date])
            .values('item__id', 'item__name', 'item__individual_uom')
            .annotate(
                total_deposit=StockMovement.Query.TOTAL_DEPOSIT_UNITS,
                total_withdraw=StockMovement.Query.TOTAL_WITHDRAW_UNITS,
            )
            .annotate(
                net_quantity=F('total_deposit') - F('total_withdraw')
            )
            .order_by('item__name')
        )