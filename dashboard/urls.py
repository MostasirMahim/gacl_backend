from django.urls import path
from . import views

urlpatterns = [
    # ── New consolidated endpoints ────────────────────────────────────────
    # Single summary: all sections the user is allowed to see in ONE request
    path("v1/summary/", views.DashboardSummaryView.as_view(),
         name="dashboard_summary"),

    # Live feed: polled every 30s — operational real-time data only
    path("v1/live/", views.DashboardLiveView.as_view(),
         name="dashboard_live"),

    # ── Legacy endpoints — kept for backward compatibility ─────────────────
    path("v1/dashboard_cards/", views.DashboardCardView.as_view(),
         name="dashboard_card_view"),
    path("v1/dashboard_cards/kpi/", views.DashBoardKPICard.as_view(),
         name="dashboard_card_kpi_view"),
    path("v1/membership_chart/", views.DashboardChartView.as_view(),
         name="dashboard_chart_view"),
    path("v1/membership_chart/pie_chart/", views.DashboardPieChartView.as_view(),
         name="dashboard_chart_pie_view"),
]
