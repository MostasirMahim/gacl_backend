from django.urls import path
from . import views

urlpatterns = [
    path("v1/payroll/components/", views.SalaryComponentView.as_view(), name="payroll_components"),
    path("v1/payroll/structures/", views.SalaryStructureView.as_view(), name="payroll_structures"),
    path("v1/payroll/structures/<int:pk>/", views.SalaryStructureDetailView.as_view(), name="payroll_structure_detail"),
    path("v1/payroll/structures/<int:pk>/", views.SalaryStructureDetailView.as_view(), name="payroll_structure_detail"),
    path("v1/payroll/structures/lines/", views.SalaryStructureLineView.as_view(), name="payroll_structure_lines"),
    path("v1/payroll/runs/", views.PayrollRunView.as_view(), name="payroll_runs"),
    path("v1/payroll/payslips/", views.PayslipView.as_view(), name="payroll_payslips"),
    path("v1/payroll/payslips/<int:payslip_id>/pay/", views.PayslipPayView.as_view(), name="payroll_payslip_pay"),
    path("v1/payroll/payslips/<int:payslip_id>/adjust/", views.PayslipAdjustView.as_view(), name="payroll_payslip_adjust"),
    path("v1/payroll/loans/", views.StaffLoanView.as_view(), name="payroll_loans"),
]
