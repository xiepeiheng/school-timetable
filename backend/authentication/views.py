from typing import cast

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from authentication.serializers import UserSerializer
from common.enums import CodeEnum
from common.exceptions import AuthenticationException, BusinessException
from common.response import success_response


class IsSuperUser(BasePermission):
    """仅超级管理员。单管理员方案，不引入 Group RBAC。"""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_superuser)


class AuthViewSet(viewsets.ViewSet):
    permission_classes = []

    @action(detail=False, methods=["post"])
    def login(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            raise BusinessException(message="用户名和密码不能为空")

        user = cast(User, authenticate(username=username, password=password))

        if not user:
            raise AuthenticationException(message="用户名或密码错误")
        if not user.is_active:
            raise BusinessException(
                code_enum=CodeEnum.USER_DISABLED,
                message="账号已被停用",
            )

        refresh = RefreshToken.for_user(user)
        return success_response(
            data={
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user_id": user.id,
                "username": user.username,
                "is_superuser": user.is_superuser,
            }
        )

    @action(detail=False, methods=["post"])
    def refresh(self, request):
        refresh_token_str = request.data.get("refresh")
        if not refresh_token_str:
            raise BusinessException(message="refresh_token 不能为空")

        try:
            refresh = RefreshToken(refresh_token_str)
            return success_response(data={"access": str(refresh.access_token)})
        except Exception:
            raise AuthenticationException(message="Token 已过期，请重新登录")

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def me(self, request):
        user = cast(User, request.user)
        return success_response(
            data={
                "user_id": user.id,
                "username": user.username,
                "is_superuser": user.is_superuser,
            }
        )


class UserViewSet(viewsets.ModelViewSet):
    """超级管理员账号管理：建号、改密码、启用/停用。"""

    queryset = User.objects.all().order_by("id")
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsSuperUser]
    pagination_class = None

    def perform_create(self, serializer):
        password = self.request.data.get("password", "")
        user = serializer.save()
        if password:
            user.set_password(password)
            user.save(update_fields=["password"])

    def perform_update(self, serializer):
        password = self.request.data.get("password", "")
        user = serializer.save()
        if password:
            user.set_password(password)
            user.save(update_fields=["password"])
