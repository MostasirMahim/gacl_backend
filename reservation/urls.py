from django.urls import path
from . import views

urlpatterns = [
    path("v1/reservations/resources/", views.ReservableResourceView.as_view(),
         name="reservation_resources"),
    path("v1/reservations/resources/<int:resource_id>/",
         views.ReservableResourceDetailView.as_view(), name="reservation_resource_detail"),
    path("v1/reservations/availability/", views.AvailabilityView.as_view(),
         name="reservation_availability"),
    path("v1/reservations/", views.ReservationView.as_view(), name="reservations"),
    path("v1/reservations/<int:reservation_id>/pay-advance/",
         views.PayReservationAdvanceView.as_view(), name="reservation_pay_advance"),
    path("v1/reservations/<int:reservation_id>/cancel/",
         views.CancelReservationView.as_view(), name="reservation_cancel"),
]
