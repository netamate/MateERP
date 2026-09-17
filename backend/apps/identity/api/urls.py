from django.urls import path

from .views import (
    ContextView,
    CsrfView,
    LegalEntityListView,
    LoginView,
    LogoutView,
    MembershipListView,
    MembershipRoleView,
    MembershipScopeView,
    SessionView,
)

urlpatterns = [
    path("auth/csrf/", CsrfView.as_view(), name="auth-csrf"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("session/", SessionView.as_view(), name="session"),
    path("session/context/", ContextView.as_view(), name="session-context"),
    path("legal-entities/", LegalEntityListView.as_view(), name="legal-entity-list"),
    path("memberships/", MembershipListView.as_view(), name="membership-list"),
    path(
        "memberships/<uuid:membership_id>/role/",
        MembershipRoleView.as_view(),
        name="membership-role",
    ),
    path(
        "memberships/<uuid:membership_id>/scope/",
        MembershipScopeView.as_view(),
        name="membership-scope",
    ),
]
