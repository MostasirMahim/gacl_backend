from django.urls import path
from . import views

urlpatterns = [
    path("v1/attendance/staff/", views.StaffProfileView.as_view(),
         name="attendance_staff"),
    path("v1/attendance/staff/<int:staff_id>/guest-toggle/",
         views.StaffGuestToggleView.as_view(), name="attendance_staff_guest_toggle"),
    path("v1/attendance/cards/", views.RFIDCardView.as_view(),
         name="attendance_cards"),
    path("v1/attendance/guests/", views.GuestView.as_view(),
         name="attendance_guests"),
    path("v1/attendance/records/", views.AttendanceRecordView.as_view(),
         name="attendance_records"),
    path("v1/attendance/scan/", views.CardScanView.as_view(),
         name="attendance_card_scan"),
]
