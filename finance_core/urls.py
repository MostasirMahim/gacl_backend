from django.urls import path
from . import views

urlpatterns = [
    path("v1/finance/expenses/", views.ExpenseView.as_view(), name="finance_expenses"),
    path("v1/finance/reports/profit-loss/", views.ProfitLossView.as_view(), name="finance_pl"),
    path("v1/finance/reports/income-breakdown/", views.IncomeBreakdownView.as_view(), name="finance_income_breakdown"),
    path("v1/finance/reports/expense-breakdown/", views.ExpenseBreakdownView.as_view(), name="finance_expense_breakdown"),
    path("v1/finance/reports/member-statement/<int:member_id>/", views.MemberStatementView.as_view(), name="finance_member_statement"),
]
