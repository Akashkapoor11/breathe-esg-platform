import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser


class Organization(models.Model):
    """
    Top-level tenant. Every piece of data is scoped to an org.
    This ensures one client's data is never visible to another,
    and emission factors (e.g. electricity grid factor) can be
    configured per-org without touching global defaults.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    country = models.CharField(max_length=100, default='India')
    reporting_year = models.IntegerField(default=2024)

    # Market-based electricity emission factor (kg CO2e/kWh).
    # Defaults to India CEA grid average (0.716 kg CO2e/kWh, FY 2022-23).
    # Can be overridden with a utility-specific or renewable energy certificate factor.
    electricity_emission_factor = models.DecimalField(
        max_digits=10, decimal_places=6,
        default=0.716000,
        help_text="kg CO2e per kWh — India CEA FY22-23 default"
    )
    electricity_factor_source = models.CharField(
        max_length=300,
        default="CEA CO2 Baseline Database for Indian Power Sector, FY 2022-23"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class CustomUser(AbstractUser):
    """
    Extended user model. Scoped to an org; role controls what they can do.
    Analysts can review. Admins can lock records and manage the org.
    Viewers are read-only.
    """
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('analyst', 'Analyst'),
        ('viewer', 'Viewer'),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE,
        null=True, blank=True, related_name='users'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='analyst')

    def __str__(self):
        return f"{self.username} ({self.organization})"
