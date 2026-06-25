
from django.urls import path
from event.views import (
    EventVenueView,EventView,EventTicketView,EventMediaView,
    EventFeeView,EventDetailView,EventTicketBuyView,
    EventTicketDetailView,
    EventExpenseView, EventExpenseCategoryView, EventFoodItemView,
    EventProfitabilityView, CountryChoicesView,
)

urlpatterns = [
    path("v1/events/venues/", EventVenueView.as_view(), name="events_venues"),
    path("v1/events/countries/", CountryChoicesView.as_view(), name="events_countries"),
    path("v1/events/", EventView.as_view(), name="events"),
    path("v1/events/<int:event_id>/", EventDetailView.as_view(), name="event_details"),
    path("v1/events/tickets/", EventTicketView.as_view(), name="event_tickets"),
    path("v1/events/tickets/<int:ticket_id>/", EventTicketDetailView.as_view(), name="event_ticket_details"),
    path("v1/events/media/", EventMediaView.as_view(), name="event_media"),
    path("v1/events/fees/", EventFeeView.as_view(), name="event_fees"),
    path("v1/events/tickets/buy/", EventTicketBuyView.as_view(), name="event_ticket_buy"),

    path("v1/events/expenses/", EventExpenseView.as_view(), name="event_expenses"),
    path("v1/events/expenses/categories/", EventExpenseCategoryView.as_view(), name="event_expense_categories"),
    path("v1/events/food-items/", EventFoodItemView.as_view(), name="event_food_items"),
    path("v1/events/<int:event_id>/profitability/", EventProfitabilityView.as_view(), name="event_profitability"),

]


