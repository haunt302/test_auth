from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class AccessLevel(models.TextChoices):
    VIEW = "view", _("View")
    EDIT = "edit", _("Edit")
    DELETE = "delete", _("Delete")
    MANAGE = "manage", _("Manage")


class Role(models.Model):
    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["slug"]

    def __str__(self):
        return self.name


class Resource(models.Model):
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.name


class RolePermission(models.Model):
    role = models.ForeignKey(Role, related_name="permissions", on_delete=models.CASCADE)
    resource = models.ForeignKey(Resource, related_name="permissions", on_delete=models.CASCADE)
    action = models.CharField(max_length=20, choices=AccessLevel.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["role", "resource", "action"], name="unique_role_permission"),
        ]

    def __str__(self):
        return f"{self.role.slug}:{self.resource.code}:{self.action}"


class User(AbstractUser):
    email = models.EmailField(
        _('email address'),
        unique=True,
    )

    email_verify = models.BooleanField(default=False)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def assign_role(self, role):
        return UserRole.objects.get_or_create(user=self, role=role)

    def revoke_role(self, role):
        UserRole.objects.filter(user=self, role=role).delete()

    def has_role(self, role_slug):
        return self.role_assignments.filter(role__slug=role_slug).exists()

    @property
    def is_administrator(self):
        return self.is_superuser or self.has_role("admin")

    def has_permission(self, resource_code, action):
        if not self.is_active:
            return False
        if self.is_superuser:
            return True
        return self.role_assignments.filter(
            role__permissions__resource__code=resource_code,
            role__permissions__action=action,
        ).exists()


class UserRole(models.Model):
    user = models.ForeignKey(User, related_name="role_assignments", on_delete=models.CASCADE)
    role = models.ForeignKey(Role, related_name="user_assignments", on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "role"], name="unique_user_role"),
        ]

    def __str__(self):
        return f"{self.user.email} -> {self.role.slug}"
