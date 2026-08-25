from django.urls import path

from apps.accounts import views

urlpatterns = [
    path("register", views.RegisterView.as_view(), name="auth-register"),
    path("login", views.LoginView.as_view(), name="auth-login"),
    path("refresh", views.RefreshView.as_view(), name="auth-refresh"),
    path("logout", views.LogoutView.as_view(), name="auth-logout"),
    path("password/reset", views.PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path(
        "password/reset/confirm",
        views.PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
    path(
        "email/verify/resend",
        views.EmailVerifyResendView.as_view(),
        name="auth-email-verify-resend",
    ),
    path(
        "email/verify/confirm",
        views.EmailVerifyConfirmView.as_view(),
        name="auth-email-verify-confirm",
    ),
    path("me", views.MeView.as_view(), name="auth-me"),
    path("mfa/verify", views.MfaVerifyView.as_view(), name="auth-mfa-verify"),
    path("mfa/enroll/start", views.MfaEnrollStartView.as_view(), name="auth-mfa-enroll-start"),
    path(
        "mfa/enroll/confirm",
        views.MfaEnrollConfirmView.as_view(),
        name="auth-mfa-enroll-confirm",
    ),
]
