from django.contrib.auth.models import AbstractUser, Permission
from django.db import models


class Role(models.Model):
    """
    A Role groups permissions together.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(
        Permission,
        related_name="roles",
        blank=True,
        help_text="Permissions granted to users with this role."
    )

    def __str__(self):
        return self.name
    

class User(AbstractUser):
    roles = models.ManyToManyField(
        Role,
        related_name="users",
        blank=True,
        help_text="Roles assigned to this user."
    )

    def __str__(self):
        return self.get_full_name() or self.username
    
    @property
    def role_names(self):
        return [role.name for role in self.roles.all()]

    def get_all_permissions(self, obj=None):
        """
        Override to combine the user's own permissions
        and permissions from assigned roles.
        """
        # Start with default Django permissions
        base_perms = super().get_all_permissions(obj)

        # Add permissions from roles
        role_perms = Permission.objects.filter(roles__users=self).values_list(
            "content_type__app_label", "codename"
        )
        role_perms = {f"{ct}.{code}" for ct, code in role_perms}

        return base_perms.union(role_perms)

    def has_perm(self, perm, obj=None):
        """
        Check both direct and role-based permissions.
        """
        if super().has_perm(perm, obj):
            return True
        return perm in self.get_all_permissions(obj)

    def save(self, *args, **kwargs):
        self.is_staff = True
        super().save(*args, **kwargs)

