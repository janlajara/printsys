from unfold.admin import ModelAdmin
from unfold.mixins import (
    BaseModelAdminMixin,
)
from unfold.widgets import (
    INPUT_CLASSES, UnfoldAdminPasswordInput, UnfoldAdminSelectMultipleWidget
)
from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm, AdminPasswordChangeForm
from django.forms.widgets import Input
from .models import Role
from django.contrib.auth import get_user_model
User = get_user_model()


# Customize the default AdminSite instance
app_name = settings.APP_NAME
#admin.site.site_header = f"{app_name}"
#admin.site.site_title = f"{app_name}"
admin.site.index_title = f"Welcome to {app_name}"


class BaseAdmin(ModelAdmin):

    def has_view_permission(self, request, obj=None):
        return request.user.is_active


class CustomAdminPasswordChangeForm(AdminPasswordChangeForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget = UnfoldAdminPasswordInput()
        self.fields["password2"].widget = UnfoldAdminPasswordInput()


class UserCreateForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2", "roles")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget = UnfoldAdminPasswordInput()
        self.fields["password2"].widget = UnfoldAdminPasswordInput()


class UserForm(UserChangeForm):
    password = forms.CharField(disabled=True, widget=UnfoldAdminPasswordInput)

    class Meta:
        model = User
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        from django.urls import reverse
        from django.utils.html import format_html
        if self.instance.pk:
            change_password_url = reverse(
                f"admin:auth_user_password_change",
                kwargs={"id": self.instance.pk},
            )
            self.fields["password"].help_text = format_html(
                '<div class="pt-1"><a href="{}" class="bg-primary-600 border border-transparent cursor-pointer font-medium px-3 py-2 rounded-default text-white">Change password</a></div>',
                change_password_url,
            )
            self.fields['password'].widget.attrs.update({"placeholder": "******************"})


@admin.register(User)
class UserAdmin(BaseModelAdminMixin, BaseUserAdmin):
    form = UserForm
    add_form = UserCreateForm
    change_password_form = CustomAdminPasswordChangeForm
    filter_horizontal = ('roles',)

    add_fieldsets = (
        (
            None,
            {
                "fields": ("username", "email", "password1", "password2", "roles"),
            },
        ),
    )

    def get_fieldsets(self, request, obj=None):
        if not obj:
            return self.add_fieldsets
        fieldsets = (
            ("Account Settings", {"classes": ["tab"], "fields": ["username", "password", "email", "roles", "is_active", "is_superuser"]}),
            ("Personal info", {"classes": ["tab"], "fields": ("first_name", "last_name")}),
        )
        return fieldsets


class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ['name', 'description', 'permissions']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['permissions'].widget.attrs['size'] = 100


@admin.register(Role)
class RoleAdmin(BaseAdmin):
    form = RoleForm
    list_display = ['name', 'description']
    filter_horizontal = ('permissions',)


class KeyValueFieldWidget(Input):
    input_type = "text"
    template_name = "forms/widgets/key_value_pair.html"

    def __init__(self, default_keys=[], attrs: dict | None = None) -> None:
        super().__init__(
            attrs={
                **(attrs or {}),
                "class": " ".join(
                    [*INPUT_CLASSES, attrs.get("class", "") if attrs else ""]
                ),
            }
        )
        self.default_keys = default_keys

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        import json
        parsed_value = json.loads(value) or {}
        final_value = {key: parsed_value.get(key, "") or "" for key in self.default_keys}
        context['widget_items'] = final_value.items()
        return context
    
    def value_from_datadict(self, data, files, name):
        final_value = {}
        for key, value in data.items():
            if key.startswith(f"kvfield-{name}_"):
                final_value[key.replace(f"kvfield-{name}_", "")] = value
        import json
        return json.dumps(final_value) if final_value else super().value_from_datadict(data, files, name)
