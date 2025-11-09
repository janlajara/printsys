from unfold.admin import ModelAdmin
from unfold.mixins import (
    BaseModelAdminMixin,
)

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Role
from django.contrib.auth import get_user_model

User = get_user_model()


@admin.register(User)
class UserAdmin(BaseModelAdminMixin, BaseUserAdmin):
    pass

@admin.register(Role)
class RoleAdmin(ModelAdmin):
    list_display = ['name']
