from django.urls import path
from . import views

urlpatterns = [
    path("v1/vendors/", views.VendorView.as_view(), name="vendors"),
    path("v1/vendors/categories/", views.VendorServiceCategoryView.as_view(), name="vendor_categories"),
    path("v1/vendors/offers/", views.VendorServiceOfferView.as_view(), name="vendor_offers"),
    path("v1/vendors/offers/<int:offer_id>/", views.VendorOfferDetailView.as_view(), name="vendor_offer_detail"),
    path("v1/vendors/offers/<int:offer_id>/select/", views.VendorOfferSelectView.as_view(), name="vendor_offer_select"),
    path("v1/vendors/offers/<int:offer_id>/pay/", views.VendorPaymentView.as_view(), name="vendor_offer_pay"),
    path("v1/vendors/payments/", views.VendorPaymentListView.as_view(), name="vendor_payments"),
]
