from django.contrib import admin
from .models import StaffProfile, RFIDCard, Guest, AttendanceRecord


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ("staff_ID", "user", "designation", "guest_allowed", "is_active")
    list_filter = ("guest_allowed", "is_active")
    search_fields = ("staff_ID", "user__username", "designation")


@admin.register(RFIDCard)
class RFIDCardAdmin(admin.ModelAdmin):
    list_display = ("card_uid", "card_type", "is_assigned", "is_active")
    list_filter = ("card_type", "is_assigned", "is_active")
    search_fields = ("card_uid",)


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "guest_relation", "host_type", "is_active")
    list_filter = ("guest_relation", "host_type", "is_active")
    search_fields = ("name", "phone")


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("subject_type", "check_in", "check_out", "is_active")
    list_filter = ("subject_type", "is_active")
