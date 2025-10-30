from django.urls import path, include
from .views import (
    AccountDeactivateView,
    EmailVerify,
    MyLoginView,
    ProfileView,
    ProjectListView,
    Register,
    ReportEditView,
    RoleAssignmentView,
    RolePermissionManagementView,
)
from django.views.generic import TemplateView

urlpatterns = [
    path('login/', MyLoginView.as_view(), name='login'),

    path('', include('django.contrib.auth.urls')),

    path(
        'invalid_verify/',
        TemplateView.as_view(template_name='registration/invalid_verify.html'),
        name='invalid_verify'
    ),

    path(
        'verify_email/<uidb64>/<token>/',
        EmailVerify.as_view(),
        name='verify_email'
    ),

    path(
        'confirm_email/',
        TemplateView.as_view(template_name='registration/confirm_email.html'),
        name='confirm_email'
    ),
    path('register/', Register.as_view(), name='register'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/deactivate/', AccountDeactivateView.as_view(), name='deactivate_account'),
    path('api/permissions/', RolePermissionManagementView.as_view(), name='api_permissions'),
    path('api/roles/assign/', RoleAssignmentView.as_view(), name='api_role_assignment'),
    path('mock/projects/', ProjectListView.as_view(), name='projects'),
    path('mock/reports/', ReportEditView.as_view(), name='reports_edit'),
]
