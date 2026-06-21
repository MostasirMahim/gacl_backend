from django.db import models
from django.conf import settings
from member_financial_management.utils.managers import ActiveManager


class VendorBaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


class Vendor(VendorBaseModel):
    name = models.CharField(max_length=255, unique=True)
    contact_person = models.CharField(max_length=255, blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    address = models.TextField(blank=True, default="")
    note = models.TextField(blank=True, default="")

    objects = models.Manager()
    active_objects = ActiveManager()

    def __str__(self):
        return self.name


# ------------------------------------------------------------
# A service category the club needs (e.g. "Laundry", "Security",
# "Catering"). Multiple vendors quote for it; exactly one is selected
# and the rest of that category's offers are deactivated.
# ------------------------------------------------------------
class VendorServiceCategory(VendorBaseModel):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default="")

    objects = models.Manager()
    active_objects = ActiveManager()

    def __str__(self):
        return self.name


class VendorServiceOffer(VendorBaseModel):
    """A vendor's price offer for a service category."""
    STATUS_CHOICES = [
        ("offered", "offered"),     # quoted, under consideration
        ("selected", "selected"),   # chosen — the active vendor for this category
        ("rejected", "rejected"),   # not chosen / disabled
    ]
    vendor = models.ForeignKey(
        Vendor, on_delete=models.CASCADE, related_name="offers")
    category = models.ForeignKey(
        VendorServiceCategory, on_delete=models.CASCADE, related_name="offers")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    price = models.DecimalField(max_digits=12, decimal_places=2)
    billing_cycle = models.CharField(
        max_length=20,
        choices=[("one_time", "one_time"), ("monthly", "monthly"),
                 ("yearly", "yearly")],
        default="one_time")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="offered")

    objects = models.Manager()
    active_objects = ActiveManager()

    class Meta:
        unique_together = ("vendor", "category", "title")

    def __str__(self):
        return f"{self.vendor.name} - {self.category.name}: {self.price} [{self.status}]"


class VendorPayment(VendorBaseModel):
    """Payments made to a selected vendor (recorded as a central expense)."""
    offer = models.ForeignKey(
        VendorServiceOffer, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_on = models.DateField(auto_now_add=True)
    note = models.CharField(max_length=255, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True,
        default=None, related_name="vendor_payments")

    def __str__(self):
        return f"{self.offer.vendor.name}: {self.amount}"
