from rest_framework import viewsets, generics
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from users.models import User, Payment
from users.paginators import PaymentPaginator
from users.serializers import (
    UserProfileSerializer,
    UserDetailSerializer,
    UserRegistrationSerializer,
    PaymentSerializer,
)
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.conf import settings

from lms.models import Course
from users.services import process_payment, create_payment_intent


@extend_schema_view(
    list=extend_schema(
        summary="Список пользователей",
        description="Возвращает список всех пользователей (ограниченная информация).",
        tags=["Пользователи"],
    ),
    create=extend_schema(
        summary="Регистрация пользователя",
        description="Создает нового пользователя. Доступно без авторизации.",
        tags=["Пользователи"],
        request=UserRegistrationSerializer,
        responses={
            201: UserDetailSerializer,
            400: OpenApiResponse(description="Ошибка валидации"),
        },
    ),
    retrieve=extend_schema(
        summary="Получить профиль пользователя",
        description="Возвращает информацию о пользователе. "
                    "Для своего профиля — полная информация (с историей платежей), "
                    "для чужого — только основные данные.",
        tags=["Пользователи"],
    ),
    update=extend_schema(
        summary="Обновить профиль",
        description="Обновляет профиль пользователя. Доступно только для своего профиля.",
        tags=["Пользователи"],
    ),
    partial_update=extend_schema(
        summary="Частично обновить профиль",
        description="Частичное обновление профиля. Доступно только для своего профиля.",
        tags=["Пользователи"],
    ),
)
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return UserRegistrationSerializer
        if self.action == "retrieve":
            # При просмотре чужого профиля возвращаем ограниченные данные
            if self.get_object() != self.request.user:
                return UserProfileSerializer
            return UserDetailSerializer
        if self.action == "update" or self.action == "partial_update":
            # Редактировать можно только свой профиль
            if self.get_object() != self.request.user:
                self.permission_denied(
                    self.request, message="Вы можете редактировать только свой профиль"
                )
            return UserDetailSerializer
        return UserProfileSerializer

    def get_permissions(self):
        if self.action == "create":
            self.permission_classes = [AllowAny]
        return super().get_permissions()


@extend_schema(
    summary="Список платежей",
    description="Возвращает список платежей с возможностью фильтрации и сортировки. "
                "Модераторы видят все платежи, обычные пользователи — только свои.",
    tags=["Платежи"],
    parameters=[
        {"name": "paid_course", "in": "query", "type": "integer", "description": "Фильтр по ID курса"},
        {"name": "paid_lesson", "in": "query", "type": "integer", "description": "Фильтр по ID урока"},
        {"name": "type", "in": "query", "type": "string", "description": "Фильтр по способу оплаты (cash/bank)"},
        {"name": "ordering", "in": "query", "type": "string", "description": "Сортировка по payment_date или amount"},
    ],
)
class PaymentListView(generics.ListAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["paid_lesson", "paid_course", "type"]
    ordering_fields = ["payment_date", "amount"]
    pagination_class = PaymentPaginator

    def get_queryset(self):
        user = self.request.user
        if user.groups.filter(name="moderators").exists():
            return Payment.objects.all()
        return Payment.objects.filter(payer=user)


class CreatePaymentView(APIView):
    """Эндпоинт для создания платежа через Stripe"""
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        course_id = request.data.get("course_id")
        if not course_id:
            return Response(
                {"error": "Необходимо указать course_id"},
                status=400,
            )

        course = get_object_or_404(Course, id=course_id)

        # Цена курса (можно добавить поле price в модель Course)
        # Для примера используем фиксированную цену
        amount = 1000.00

        # Формируем URL для успешной оплаты и отмены
        success_url = request.build_absolute_uri("/payment/success/")
        cancel_url = request.build_absolute_uri("/payment/cancel/")

        try:
            payment_data = process_payment(
                user=request.user,
                course=course,
                amount=amount,
                success_url=success_url,
                cancel_url=cancel_url,
            )
            return Response(payment_data, status=200)

        except Exception as e:
            return Response(
                {"error": f"Ошибка создания платежа: {str(e)}"},
                status=500,
            )


class PaymentIntentView(APIView):
    """Альтернативный эндпоинт с использованием PaymentIntent"""
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        course_id = request.data.get("course_id")
        if not course_id:
            return Response(
                {"error": "Необходимо указать course_id"},
                status=400,
            )

        course = get_object_or_404(Course, id=course_id)
        amount = 1000.00

        try:
            intent_data = create_payment_intent(amount, course.name)
            return Response(intent_data, status=200)
        except Exception as e:
            return Response(
                {"error": f"Ошибка создания PaymentIntent: {str(e)}"},
                status=500,
            )
