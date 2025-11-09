import inflect

from django.contrib import admin
from django import forms
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.shortcuts import render
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.html import format_html
from core.utils import format_currency

from unfold.decorators import action
from unfold.admin import ModelAdmin
from unfold.admin import StackedInline, TabularInline
from unfold.contrib.inlines.admin import NonrelatedTabularInline
from unfold.widgets import (
    UnfoldAdminTextInputWidget, UnfoldAdminIntegerFieldWidget, 
    UnfoldAdminSelectWidget, UnfoldAdminSelect2Widget,
    UnfoldBooleanSwitchWidget, UnfoldAdminTextareaWidget,
    UnfoldAdminSplitDateTimeWidget, 
)

from .models import Item, ItemCategory, StockMovement, Supplier, StockMovementPurpose

p = inflect.engine()

class WithdrawForm(forms.Form):
    timestamp = forms.SplitDateTimeField(required=False, initial=timezone.now, widget=UnfoldAdminSplitDateTimeWidget)
    quantity = forms.IntegerField(min_value=1, widget=UnfoldAdminIntegerFieldWidget)
    unit_of_measure = forms.ChoiceField(widget=UnfoldAdminSelectWidget)
    purpose = forms.ModelChoiceField(
        queryset=StockMovementPurpose.objects.filter(is_active=True),
        required=False, widget=UnfoldAdminSelectWidget
    )
    remarks = forms.CharField(required=False, widget=UnfoldAdminTextareaWidget)

    def __init__(self, *args, item=None, **kwargs):
        super().__init__(*args, **kwargs)
        if item:
            self.fields['unit_of_measure'].choices = [
                (item.individual_uom, item.individual_uom),
                (item.pack_uom, item.pack_uom)
            ]

class DepositForm(WithdrawForm):
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.all(),
        required=False, widget=UnfoldAdminSelect2Widget
    )
    unit_price = forms.DecimalField(decimal_places=2, required=False,
                                    widget=UnfoldAdminIntegerFieldWidget)


class StockMovementInline(TabularInline):
    verbose_name = "Stock History"
    verbose_name_plural = "Stock History"
    model = StockMovement
    tab = True
    hide_title = True
    fields = ('timestamp', 'movement_type_display', 'quantity_display', 'unit_price_display', 'user', 'supplier', 'purpose', 'remarks')
    readonly_fields = ('movement_type_display', 'quantity_display', 'unit_price_display', 'timestamp', 'user', 'supplier', 'purpose', 'remarks')
    can_delete = False
    ordering = ('-timestamp',)
    per_page = 10

    def unit_price_display(self, obj):
        return format_currency(obj.unit_price) if obj.unit_price else ""
    unit_price_display.short_description = "Unit Price"

    def movement_type_display(self, obj):
        style = "color: var(--color-green-400)" if obj.movement_type == StockMovement.DEPOSIT else "color: var(--color-red-400)"
        return format_html('<span style="{};">{}</span>', style, obj.movement_type)

    def quantity_display(self, obj):
        style = "color: var(--color-green-400)" if obj.movement_type == StockMovement.DEPOSIT else "color: var(--color-red-400)"
        unit_of_measure = obj.item.pack_uom if obj.is_packed else obj.item.individual_uom
        if obj.quantity:
            quantity = f"{obj.quantity} {p.plural(unit_of_measure, obj.quantity)}"
            return format_html('<span style="{};">{}</span>', style, quantity)
        else:
            return "-"
    quantity_display.short_description = "Quantity"


class ItemSupplierInline(NonrelatedTabularInline):
    model = Supplier
    tab = True
    template = 'item/suppliers_inline.html'
    
    def get_form_queryset(self, obj):
        return Supplier.objects.none()
    
    def save_new_instance(self, parent, instance):
        pass

    def get_formset(self, request, obj=None, **kwargs):

        def to_link(supplier_id, supplier_name):
            url = reverse_lazy(
                'admin:inventory_supplier_change',
                args=[supplier_id]
            )
            return format_html('<a href="{}" class="hover:text-primary-600 dark:hover:text-primary-500 text-primary-600 dark:text-primary-500">{}</a>', url, supplier_name)

        formset = super().get_formset(request, obj, **kwargs)

        table_data = {
            "headers": ["Supplier", f"Total Provided ({p.plural(obj.individual_uom)})", f"Price per {obj.individual_uom}"],
            "rows": [
                [to_link(x['supplier__id'], x["supplier__name"]), x["total"], format_currency(x['average_price']) if x['average_price'] else ""] for x in obj.suppliers_summary()
            ]
        }

        # Attach extra context as a property of the formset class
        formset.custom_context_data = {
            'supplier_summary': table_data,
        }
        return formset


@admin.register(Item)
class ItemAdmin(ModelAdmin):
    change_form_template = "item/change_form.html"

    inlines = [StockMovementInline, ItemSupplierInline]
    actions_detail = ["deposit", "withdraw"]
    list_display_links = ["category", "name", "description"]
    list_display = ["category", "name", "description", "uom_display", "current_stock"]
    list_filter = ["category"]
    ordering = ["category", "name"]
    search_fields = ['name', 'description']

    fieldsets = (
        (
            None, { "fields": ["current_stock"] },
        ),
        (
            None, { "fields": ["name", "description", "category", "individual_uom", "pack_uom", "pack_quantity"] }
        )
    )

    def uom_display(self, obj):
        if obj:
            uom = obj.individual_uom
            if obj.pack_quantity > 1 and obj.pack_uom:
                uom = f"{obj.pack_quantity} {p.plural(obj.individual_uom, obj.pack_quantity)} per {obj.pack_uom}"
            return uom
    uom_display.short_description = "Unit of Measure"

    def current_stock(self, obj):
        if obj and obj.pk:
            current_quantity = obj.current_quantity
            return f"{current_quantity} {p.plural(obj.individual_uom, current_quantity)}"

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ["current_stock"]
        else:
            return []

    @action(
        description="Deposit",
        url_path="deposit",
        attrs={"target": "_self", "style": "color: var(--color-green-400)"},
        #permissions=["deposit_stock"]
    )
    def deposit(self, request, object_id):
        user = request.user
        item = Item.objects.get(pk=object_id)
        form = DepositForm(request.POST or None, item=item)
        
        if request.method == "POST":
            if form.is_valid():
                try:
                    quantity = form.cleaned_data.get("quantity")
                    unit_of_measure = form.cleaned_data.get("unit_of_measure")
                    is_packed = unit_of_measure == item.pack_uom
                    unit_price = form.cleaned_data.get("unit_price", None)
                    purpose = form.cleaned_data.get("purpose", None)
                    supplier = form.cleaned_data.get("supplier", None)
                    remarks = form.cleaned_data.get("remarks", None)

                    item.deposit(quantity, user, is_packed, supplier, remarks, purpose, unit_price)
                    
                    messages.success(request, f"'{item.name}' deposited successfully")
                    return redirect(
                        f"{reverse_lazy("admin:inventory_item_change", args=[object_id])}#movements"
                    )
                except ValidationError as e:
                    messages.error(request, f"{e}")
            else:
                messages.error(request, form.errors)

        return render(
            request,
            "item/stock_action.html",
            {
                "form": form,
                "object": item,
                "title": "Deposit",
                **self.admin_site.each_context(request),
            },
        )
    
    @action(
        description="Withdraw",
        url_path="withdraw",
        attrs={"target": "_self", "style": "color: var(--color-red-400)"},
        #permissions=["withdraw_stock"]
    )
    def withdraw(self, request, object_id):
        user = request.user
        item = Item.objects.get(pk=object_id)
        form = WithdrawForm(request.POST or None, item=item)
        
        if request.method == "POST":
            if form.is_valid():
                try:
                    quantity = form.cleaned_data.get("quantity")
                    unit_of_measure = form.cleaned_data.get("unit_of_measure")
                    is_packed = unit_of_measure == item.pack_uom
                    purpose = form.cleaned_data.get("purpose", None)
                    remarks = form.cleaned_data.get("remarks", None)

                    item.withdraw(quantity, user, is_packed, remarks, purpose)
                    
                    messages.success(request, f"'{item.name}' withdrawn successfully")
                    return redirect(
                        f"{reverse_lazy("admin:inventory_item_change", args=[object_id])}#movements"
                    )
                except ValidationError as e:
                    messages.error(request, f"{e}")
            else:
                messages.error(request, form.errors)

        return render(
            request,
            "item/stock_action.html",
            {
                "form": form,
                "object": item,
                "title": "Withdraw",
                **self.admin_site.each_context(request),
            },
        )

    def has_withdraw_stock_permission(self, request, object_id):
        True


@admin.register(Supplier)
class SupplierAdmin(ModelAdmin):
    list_display = ["name", "contact_person", "email"]


@admin.register(ItemCategory)
class ItemCategoryAdmin(ModelAdmin):
    list_display = ["name", "description"]


@admin.register(StockMovementPurpose)
class StockMovementPurposeAdmin(ModelAdmin):
    list_display = ["name", "description", "is_active"]