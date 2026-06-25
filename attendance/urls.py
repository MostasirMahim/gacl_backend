from django.urls import path
from . import views

urlpatterns = [
    path("v1/attendance/staff/", views.StaffProfileView.as_view(),
         name="attendance_staff"),
    path("v1/attendance/staff/<int:staff_id>/guest-toggle/",
         views.StaffGuestToggleView.as_view(), name="attendance_staff_guest_toggle"),

    # RFID cards: list/create, detail (assign/deactivate), history
    path("v1/attendance/cards/", views.RFIDCardView.as_view(),
         name="attendance_cards"),
    path("v1/attendance/cards/<int:pk>/", views.RFIDCardDetailView.as_view(),
         name="attendance_card_detail"),
    path("v1/attendance/cards/<int:pk>/history/",
         views.RFIDCardHistoryView.as_view(), name="attendance_card_history"),

    # guests: list/create, detail (assign temp card / remove)
    path("v1/attendance/guests/", views.GuestView.as_view(),
         name="attendance_guests"),
    path("v1/attendance/guests/<int:pk>/", views.GuestDetailView.as_view(),
         name="attendance_guest_detail"),

    # records + CSV export
    path("v1/attendance/records/", views.AttendanceRecordView.as_view(),
         name="attendance_records"),
    path("v1/attendance/records/export/",
         views.AttendanceRecordExportView.as_view(),
         name="attendance_records_export"),

    path("v1/attendance/scan/", views.CardScanView.as_view(),
         name="attendance_card_scan"),
]
