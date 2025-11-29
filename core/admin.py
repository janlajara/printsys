from unfold.admin import ModelAdmin
from unfold.mixins import (
    BaseModelAdminMixin,
)
from unfold.widgets import INPUT_CLASSES

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.forms.widgets import Input
from .models import Role
from django.contrib.auth import get_user_model

User = get_user_model()


@admin.register(User)
class UserAdmin(BaseModelAdminMixin, BaseUserAdmin):
    pass

@admin.register(Role)
class RoleAdmin(ModelAdmin):
    list_display = ['name']


class KeyValueFieldWidget(Input):
    input_type = "text"
    template_name = "forms/widgets/key_value_pair.html"

    def __init__(self, default_keys=[], keys_map={}, attrs: dict | None = None) -> None:
        super().__init__(
            attrs={
                **(attrs or {}),
                "class": " ".join(
                    [*INPUT_CLASSES, attrs.get("class", "") if attrs else ""]
                ),
            }
        )
        self.default_keys = default_keys
        self.keys_map = keys_map

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        import json
        parsed_value = json.loads(value)
        final_value = {key: parsed_value.get(key, "") for key in self.default_keys}
        context['widget_items'] = final_value.items()
        return context
    
    def value_from_datadict(self, data, files, name):
        final_value = {}
        for key, value in data.items():
            if key.startswith(f"kvfield-{name}_"):
                final_value[key.replace(f"kvfield-{name}_", "")] = value
        return final_value