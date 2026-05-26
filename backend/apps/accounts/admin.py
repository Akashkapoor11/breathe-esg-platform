from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'country', 'reporting_year', 'created_at']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'organization', 'role', 'is_active']
    list_filter = ['organization', 'role']
    fieldsets = UserAdmin.fieldsets + (
        ('Breathe ESG', {'fields': ('organization', 'role')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Breathe ESG', {'fields': ('organization', 'role')}),
    )
