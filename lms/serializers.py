from rest_framework import serializers
from lms.models import Course, Lesson, Subscription
from lms.validators import validate_youtube_link
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample


class LessonSerializer(serializers.ModelSerializer):
    link_video = serializers.URLField(
        validators=[validate_youtube_link],
        required=False,
        allow_blank=True,
        allow_null=True
    )

    class Meta:
        model = Lesson
        fields = "__all__"
        read_only_fields = ("owner",)


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Пример курса",
            value={
                "name": "Python Basics",
                "description": "Курс для начинающих",
                "lessons_count": 10,
                "is_subscribed": False,
            },
            request_only=False,
            response_only=True,
        )
    ]
)
class CourseSerializer(serializers.ModelSerializer):
    lessons_count = serializers.IntegerField(source="lessons.count", read_only=True)
    lessons = LessonSerializer(many=True, read_only=True)
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "pk",
            "name",
            "preview",
            "description",
            "lessons_count",
            "lessons",
            "owner",
            "is_subscribed",  # добавлено
        ]
        read_only_fields = ("owner",)

    def get_is_subscribed(self, obj):
        """Проверяет, подписан ли текущий пользователь на курс"""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return Subscription.objects.filter(
                user=request.user,
                course=obj
            ).exists()
        return False


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ["id", "user", "course", "created_at"]
        read_only_fields = ["id", "user", "created_at"]


