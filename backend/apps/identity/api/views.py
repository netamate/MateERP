from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_audit_event
from apps.identity.models import Membership
from apps.identity.policy import Permission, has_permission
from apps.identity.selectors import accessible_legal_entities, memberships_for_user
from apps.identity.services import (
    change_membership_role,
    set_active_context,
    set_membership_legal_entity_scope,
)

from .serializers import (
    ContextSerializer,
    LegalEntitySerializer,
    LoginSerializer,
    MembershipRoleSerializer,
    MembershipScopeSerializer,
    MembershipSerializer,
    OrganizationSerializer,
    UserSerializer,
)


def _session_payload(request):
    memberships = list(memberships_for_user(request.user))
    active_org_id = request.session.get("active_organization_id")
    active_legal_entity_id = request.session.get("active_legal_entity_id")

    active_membership = next(
        (
            membership
            for membership in memberships
            if str(membership.organization_id) == active_org_id
        ),
        None,
    )

    return {
        "user": UserSerializer(request.user).data,
        "memberships": MembershipSerializer(memberships, many=True).data,
        "organizations": OrganizationSerializer(
            [membership.organization for membership in memberships], many=True
        ).data,
        "active_organization_id": active_org_id,
        "active_legal_entity_id": active_legal_entity_id,
        "active_legal_entities": LegalEntitySerializer(
            accessible_legal_entities(active_membership) if active_membership else [],
            many=True,
        ).data,
    }


class CsrfView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrf_token": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request,
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if user is None or not user.is_active:
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        login(request, user)
        memberships = list(memberships_for_user(user))
        if memberships and not request.session.get("active_organization_id"):
            membership = memberships[0]
            request.session["active_organization_id"] = str(membership.organization_id)
            entities = accessible_legal_entities(membership)
            first_entity = entities.first()
            if first_entity:
                request.session["active_legal_entity_id"] = str(first_entity.id)

        record_audit_event(
            actor=user,
            action="auth.login",
            object_type="User",
            object_id=user.id,
            request=request,
        )
        return Response(_session_payload(request))


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        record_audit_event(
            actor=user,
            action="auth.logout",
            object_type="User",
            object_id=user.id,
            request=request,
        )
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SessionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_session_payload(request))


class ContextView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ContextSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        context = set_active_context(user=request.user, **serializer.validated_data)

        request.session["active_organization_id"] = str(context.membership.organization_id)
        if context.legal_entity:
            request.session["active_legal_entity_id"] = str(context.legal_entity.id)
        else:
            request.session.pop("active_legal_entity_id", None)

        return Response(_session_payload(request))


class LegalEntityListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization_id = request.session.get("active_organization_id")
        context = set_active_context(
            user=request.user,
            organization_id=organization_id,
            legal_entity_id=None,
        )
        if not has_permission(context.membership, Permission.VIEW_LEGAL_ENTITY):
            return Response(status=status.HTTP_403_FORBIDDEN)
        return Response(
            LegalEntitySerializer(
                accessible_legal_entities(context.membership), many=True
            ).data
        )


class MembershipListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        organization_id = request.session.get("active_organization_id")
        context = set_active_context(
            user=request.user,
            organization_id=organization_id,
            legal_entity_id=None,
        )
        if not has_permission(context.membership, Permission.VIEW_MEMBERS):
            return Response(status=status.HTTP_403_FORBIDDEN)
        queryset = Membership.objects.filter(
            organization=context.membership.organization
        ).select_related("user").prefetch_related("legal_entities")
        return Response(MembershipSerializer(queryset, many=True).data)


class MembershipRoleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, membership_id):
        organization_id = request.session.get("active_organization_id")
        context = set_active_context(
            user=request.user,
            organization_id=organization_id,
            legal_entity_id=None,
        )
        target = Membership.objects.filter(
            id=membership_id,
            organization=context.membership.organization,
        ).select_related("user", "organization").first()
        if target is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = MembershipRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = change_membership_role(
            actor_membership=context.membership,
            membership=target,
            role=serializer.validated_data["role"],
        )
        return Response(MembershipSerializer(target).data)


class MembershipScopeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, membership_id):
        organization_id = request.session.get("active_organization_id")
        context = set_active_context(
            user=request.user,
            organization_id=organization_id,
            legal_entity_id=None,
        )
        target = Membership.objects.filter(
            id=membership_id,
            organization=context.membership.organization,
        ).select_related("organization", "user").first()
        if target is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = MembershipScopeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = set_membership_legal_entity_scope(
            actor_membership=context.membership,
            membership=target,
            **serializer.validated_data,
        )
        return Response(MembershipSerializer(target).data)
