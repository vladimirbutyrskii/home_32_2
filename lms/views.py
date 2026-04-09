from rest_framework import viewsets, generics
from rest_framework.permissions import IsAuthenticated

from lms.models import Course, Lesson, Subscription
from lms.serializers import CourseSerializer, LessonSerializer, SubscriptionSerializer
from lms.permissions import IsModerator, IsOwner, IsOwnerOrReadOnly

from rest_framework.views import APIView
from rest_framework.response import Response

from django.shortcuts import get_object_or_404
from lms.serializers import SubscriptionSerializer

from lms.paginators import CoursePaginator, LessonPaginator
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse
from drf_spectacular.types import OpenApiTypes


@extend_schema_view(
    list=extend_schema(
        summary="Получить список курсов",
        description="Возвращает список всех курсов с пагинацией. "
                    "Для каждого курса показывает количество уроков, "
                    "список уроков и признак подписки текущего пользователя.",
        tags=["Курсы"],
    ),
    retrieve=extend_schema(
        summary="Получить курс",
        description="Возвращает подробную информацию о курсе по ID.",
        tags=["Курсы"],
    ),
    create=extend_schema(
        summary="Создать курс",
        description="Создает новый курс. Доступно только для авторизованных пользователей, "
                    "не являющихся модераторами.",
        tags=["Курсы"],
    ),
    update=extend_schema(
        summary="Обновить курс",
        description="Полное обновление курса. Доступно модераторам или владельцу курса.",
        tags=["Курсы"],
    ),
    partial_update=extend_schema(
        summary="Частично обновить курс",
        description="Частичное обновление курса. Доступно модераторам или владельцу курса.",
        tags=["Курсы"],
    ),
    destroy=extend_schema(
        summary="Удалить курс",
        description="Удаляет курс. Доступно только владельцу курса. Модераторы не могут удалять.",
        tags=["Курсы"],
    ),
)
class CourseViewSet(viewsets.ModelViewSet):
    serializer_class = CourseSerializer
    queryset = Course.objects.all()
    pagination_class = CoursePaginator  # добавлено

    def get_permissions(self):
        if self.action == "create":
            self.permission_classes = [IsAuthenticated, ~IsModerator]
        elif self.action in ["update", "partial_update"]:
            self.permission_classes = [IsAuthenticated, IsModerator | IsOwner]
        elif self.action == "destroy":
            self.permission_classes = [IsAuthenticated, IsOwner]
        else:
            self.permission_classes = [IsAuthenticated]
        return [permission() for permission in self.permission_classes]

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


@extend_schema(
    summary="Создать урок",
    description="Создает новый урок в указанном курсе. "
                "Доступно только для авторизованных пользователей, не являющихся модераторами. "
                "Ссылка на видео должна вести на youtube.com.",
    tags=["Уроки"],
    request=LessonSerializer,
    responses={
        201: LessonSerializer,
        400: OpenApiResponse(description="Ошибка валидации (неверные данные или ссылка не youtube)"),
        403: OpenApiResponse(description="Доступ запрещен (модераторы не могут создавать уроки)"),
    },
)
class LessonCreateAPIView(generics.CreateAPIView):
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated, ~IsModerator]

    def get_queryset(self):
        return Lesson.objects.all()

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


@extend_schema(
    summary="Список уроков",
    description="Возвращает список уроков с пагинацией. "
                "Модераторы видят все уроки, обычные пользователи — только свои.",
    tags=["Уроки"],
)
class LessonListAPIView(generics.ListAPIView):
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LessonPaginator  # добавлено

    def get_queryset(self):
        user = self.request.user
        if user.groups.filter(name="moderators").exists():
            return Lesson.objects.all()
        return Lesson.objects.filter(owner=user)


@extend_schema(
    summary="Получить урок",
    description="Возвращает подробную информацию об уроке по ID.",
    tags=["Уроки"],
)
class LessonRetrieveAPIView(generics.RetrieveAPIView):
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.groups.filter(name="moderators").exists():
            return Lesson.objects.all()
        return Lesson.objects.filter(owner=user)


@extend_schema(
    summary="Обновить урок",
    description="Обновляет информацию об уроке. Доступно модераторам или владельцу урока.",
    tags=["Уроки"],
)
class LessonUpdateAPIView(generics.UpdateAPIView):
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated, IsModerator | IsOwner]

    def get_queryset(self):
        return Lesson.objects.all()


@extend_schema(
    summary="Удалить урок",
    description="Удаляет урок. Доступно только владельцу урока. Модераторы не могут удалять.",
    tags=["Уроки"],
)
class LessonDeleteAPIView(generics.DestroyAPIView):
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated, IsOwner]

    def get_queryset(self):
        return Lesson.objects.all()


@extend_schema(
    summary="Управление подпиской",
    description="Добавляет или удаляет подписку пользователя на курс. "
                "Если подписка существует — удаляет, если нет — создает.",
    tags=["Подписки"],
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "course_id": {"type": "integer", "description": "ID курса"}
            },
            "required": ["course_id"]
        }
    },
    responses={
        200: OpenApiResponse(
            description="Успешная операция",
            response={
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "is_subscribed": {"type": "boolean"},
                    "course_id": {"type": "integer"},
                    "course_name": {"type": "string"},
                }
            }
        ),
        400: OpenApiResponse(description="Не указан course_id"),
        404: OpenApiResponse(description="Курс не найден"),
    },
)
class SubscriptionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        course_id = request.data.get("course_id")

        if not course_id:
            return Response(
                {"error": "Необходимо указать course_id"},
                status=400
            )

        course = get_object_or_404(Course, id=course_id)

        subscription = Subscription.objects.filter(
            user=user,
            course=course
        )

        if subscription.exists():
            subscription.delete()
            message = "Подписка удалена"
            is_subscribed = False
        else:
            Subscription.objects.create(user=user, course=course)
            message = "Подписка добавлена"
            is_subscribed = True

        return Response({
            "message": message,
            "is_subscribed": is_subscribed,
            "course_id": course.id,
            "course_name": course.name
        })

    def get(self, request, *args, **kwargs):
        subscriptions = Subscription.objects.filter(user=request.user)
        serializer = SubscriptionSerializer(subscriptions, many=True)
        return Response(serializer.data)
