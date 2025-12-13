import inflect, json
from datetime import date, timedelta, datetime

from django.contrib import admin
from django import forms
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.shortcuts import render
from django.contrib import messages
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.html import format_html
from core.utils import format_currency, to_link, pluralize_uom

from unfold.decorators import action
from unfold.admin import ModelAdmin
from unfold.admin import StackedInline, TabularInline
from unfold.contrib.inlines.admin import NonrelatedTabularInline
from unfold.widgets import (
    UnfoldAdminTextInputWidget, UnfoldAdminIntegerFieldWidget, 
    UnfoldAdminSelectWidget, UnfoldAdminSelect2Widget,
    UnfoldBooleanSwitchWidget, UnfoldAdminTextareaWidget,
    UnfoldAdminSplitDateTimeWidget, UnfoldRelatedFieldWidgetWrapper
)
from unfold.contrib.forms.widgets import ArrayWidget
from unfold.components import BaseComponent, register_component


from core.admin import KeyValueFieldWidget
from .models import Item, ItemCategory, StockMovement, Supplier, StockMovementPurpose

p = inflect.engine()

class WithdrawForm(forms.Form):
    timestamp = forms.SplitDateTimeField(required=False, initial=timezone.now, widget=UnfoldAdminSplitDateTimeWidget)
    quantity = forms.IntegerField(min_value=1, widget=UnfoldAdminIntegerFieldWidget)
    current_quantity = forms.CharField(disabled=True, required=False)
    unit_of_measure = forms.ChoiceField(widget=UnfoldAdminSelectWidget)
    purpose = forms.ModelChoiceField(
        queryset=StockMovementPurpose.objects.filter(is_active=True),
        required=False, widget=UnfoldAdminSelectWidget
    )
    remarks = forms.CharField(required=False, widget=UnfoldAdminTextareaWidget)

    def __init__(self, *args, item=None, **kwargs):
        super().__init__(*args, **kwargs)
        if item:
            uom_choices = [
                (item.individual_uom, item.individual_uom),
            ]
            if item.pack_uom:
                uom_choices.append((item.pack_uom, item.pack_uom))
            self.fields['unit_of_measure'].choices = uom_choices
            self.fields['current_quantity'].initial = pluralize_uom(item.current_quantity or 0, item.individual_uom)

class DepositForm(WithdrawForm):
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.all(),
        required=False, widget=UnfoldAdminSelect2Widget
    )
    unit_price = forms.DecimalField(decimal_places=2, required=False,
                                    widget=UnfoldAdminIntegerFieldWidget)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supplier'].widget = UnfoldRelatedFieldWidgetWrapper(
            self.fields['supplier'].widget,
            StockMovement._meta.get_field('supplier').remote_field,
            admin_site=admin.site,
            can_add_related=True,
        )


class StockMovementInline(TabularInline):
    verbose_name = "Stock History"
    verbose_name_plural = "Stock History"
    model = StockMovement
    tab = True
    hide_title = True
    fields = ('timestamp', 'movement_type_display', 'quantity_display', 'unit_price_display', 'user', 'supplier', 'purpose_display', 'remarks')
    readonly_fields = ('movement_type_display', 'quantity_display', 'unit_price_display', 'timestamp', 'user', 'supplier', 'purpose_display', 'remarks')
    can_delete = False
    ordering = ('-timestamp',)
    per_page = 10
    extra = 0
    min_num = 0
    max_num = 0

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
            quantity = pluralize_uom(obj.quantity, unit_of_measure)
            return format_html('<span style="{};">{}</span>', style, quantity)
        else:
            return "-"
    quantity_display.short_description = "Quantity"

    def purpose_display(self, obj):
        return obj.purpose.name


class ItemSupplierInline(NonrelatedTabularInline):
    model = Supplier
    tab = True
    template = 'item/suppliers_inline.html'
    
    def get_form_queryset(self, obj):
        return Supplier.objects.none()
    
    def save_new_instance(self, parent, instance):
        pass

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)

        # Attach extra context as a property of the formset class
        formset.custom_context_data = {
            'supplier_summary': {
                "headers": ["Supplier", f"Total Quantity Supplied ({p.plural(obj.individual_uom)})", f"Latest price per {obj.individual_uom}"],
                "rows": [
                    [to_link('admin:inventory_supplier_change', x['supplier__id'], x["supplier__name"]), x["total"], format_currency(x['latest_price']) if x['latest_price'] else ""] for x in obj.suppliers_summary()
                ]
            },
        } if obj else {}
        return formset


class ItemAdminForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        instance = kwargs.get('instance')

        # We dont want to allow these actions in this form
        self.fields['category'].widget.can_add_related = False
        self.fields['category'].widget.can_change_related = False
        self.fields['category'].widget.can_delete_related = False
        self.fields['category'].widget.can_view_related = False
        
        self.fields['category'].required = True

        # Populate the attributes based on the selected category
        category_pk = instance.category.pk if instance and instance.category else None
        self.attribute_keys = {x['pk']: x['attributes'] for x in list(ItemCategory.objects.all().values("pk", "attributes"))}
        default_keys = self.attribute_keys.get(category_pk, [])
        self.fields['attributes'].widget = KeyValueFieldWidget(default_keys=default_keys)

    def _create_kv_widget(self, default_keys):
        return KeyValueFieldWidget(default_keys=default_keys)

    def clean_attributes(self):
        category = self.cleaned_data.get('category', None)
        attributes = self.cleaned_data.get('attributes', None)

        if category is None:
            raise ValidationError("Please select a category first.")

        required_attributes = self.attribute_keys.get(category.pk)
        if category and required_attributes:
            self.cleaned_data['attributes'] = required_attributes
            self.fields['attributes'].widget.default_keys = required_attributes
            if not attributes:
                raise ValidationError("Please enter applicable attributes.")
            if list(attributes.keys()) != required_attributes:
                raise ValidationError("Mismatching attributes. Re-enter values if applicable.")
        
        return attributes


@admin.register(Item)
class ItemAdmin(ModelAdmin):
    form = ItemAdminForm
    change_form_template = "item/change_form.html"

    actions_detail = ["deposit", "withdraw"]
    list_display_links = ["category", "description_display"]
    list_display = ["category", "description_display", "uom_display", "current_stock"]
    list_filter = ["category"]
    ordering = ["category", "name"]
    search_fields = ['description']
    list_per_page = 20

    def get_inlines(self, request, obj):
        if obj:
            return [StockMovementInline, ItemSupplierInline]
        return []

    def get_fieldsets(self, request, obj=None):
        fieldsets = [
            (
                None, { "fields": ["name", "category", "attributes", "individual_uom", "pack_uom", "pack_quantity"] }
            )
        ]
        if obj:
            fieldsets.insert(0, (
                None, { "fields": ["current_stock"] },
            ))
        return fieldsets

    def description_display(self, obj):
        return obj.description or obj.name
    description_display.short_description = "Item"

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
                        f"{reverse_lazy('admin:inventory_item_change', args=[object_id])}#movements"
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
                "current_individual_quantity": item.current_quantity,
                "current_pack_quantity": item.current_quantity / item.pack_quantity if item.pack_quantity > 0 else item.current_quantity,
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
    formfield_overrides = {
        ArrayField: {
            "widget": ArrayWidget,
        }
    }
    
    list_display = ["name", "description"]


@admin.register(StockMovementPurpose)
class StockMovementPurposeAdmin(ModelAdmin):
    list_display = ["name", "description", "is_active"]


@register_component
class InventoryDashboard(BaseComponent):

    def get_stock_movement_per_day_bar_chart(self, start_date, end_date):
        stock_movement_per_day = StockMovement.get_movement_by_day(start_date, end_date)
        current = start_date
        labels = []
        raw_data_dict = {item['day']: {**item} for item in stock_movement_per_day }

        withdrawal_dataset = {
            "data": [],
            "backgroundColor": "var(--color-red-400)"
        }
        deposit_dataset = {
            "data": [],
            "backgroundColor": "var(--color-green-400)"
        }

        while current <= end_date:
            x = raw_data_dict.get(current, {})
            deposit_dataset["data"].append(x.get('total_deposit', 0))
            withdrawal_dataset["data"].append(x.get('total_withdraw', 0) * -1)
            labels.append(str(current))
            current += timedelta(days=1)

        return {
            "labels": labels,
            "datasets": [withdrawal_dataset, deposit_dataset]
        }

    def get_stock_movement_summary_table(self, start_date, end_date):
        stock_movement_summary = StockMovement.objects.none()
        if start_date and end_date:
            stock_movement_summary = StockMovement.get_summary(start_date, end_date)

        table_data = {
            "headers": ["Item", "Total Deposited", "Total Withdrawn", "Net Quantity"],
            "rows": [
                [to_link("admin:inventory_item_change", x["item__id"], x["item__name"]), 
                 pluralize_uom(x['total_deposit'], x['item__individual_uom']), 
                 pluralize_uom(x['total_withdraw'], x['item__individual_uom']), 
                 pluralize_uom(x['net_quantity'], x['item__individual_uom'])] for x in stock_movement_summary
            ]
        } 
        return table_data
    
    def get_stock_movement_history_table(self, start_date, end_date):
        stock_movement_history = StockMovement.objects.none()
        if start_date and end_date:
            stock_movement_history = StockMovement.get_movement_history(start_date, end_date)
        
        table_data = {
            "headers": ["Timestamp", "Item", "Quantity", "Purpose", "Remarks"],
            "rows": [
                [
                    x['timestamp'],
                    to_link("admin:inventory_item_change", x["item__id"], x["item__name"]),
                    pluralize_uom(x['quantity'], x['uom'] or "pack"),
                    x['purpose__name'] or "",
                    x['remarks']
                ] for x in stock_movement_history
            ]
        }
        return table_data

    def get_context_data(self, **kwargs):
        request = self.request
        start_date = request.session.get('dashboard_start_date', None)
        end_date = request.session.get('dashboard_end_date', None)

        d1 = datetime.fromisoformat(start_date).date() if start_date else date.today() - timedelta(days=30)
        d2 = datetime.fromisoformat(end_date).date() if end_date else date.today()

        stock_movement_per_day_bar_chart_data = self.get_stock_movement_per_day_bar_chart(d1, d2)
        stock_movement_summary_table_data = self.get_stock_movement_summary_table(d1, d2)
        stock_movement_history_table_data = self.get_stock_movement_history_table(d1, d2)

        context = super().get_context_data(**kwargs)
        context.update({
            "stock_movement_summary_table_data": stock_movement_summary_table_data,
            "stock_movement_history_table_data": stock_movement_history_table_data,
            "stock_movement_per_day_bar_chart_data": json.dumps(stock_movement_per_day_bar_chart_data)
        })
        return context