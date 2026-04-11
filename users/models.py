from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
from lms.models import Course, Lesson
from django.contrib.auth.base_user import BaseUserManager

NULLABLE = dict(null=True, blank=True)


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email обязателен")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None

    email = models.EmailField(
        unique=True, verbose_name="Почта", help_text="Укажите почту"
    )
    phone = models.CharField(
        max_length=35, verbose_name="Телефон", help_text="Укажите телефон", **NULLABLE
    )
    city = models.CharField(
        max_length=50, verbose_name="Город", help_text="Укажите город", **NULLABLE
    )
    avatar = models.ImageField(
        upload_to="users/avatars",
        verbose_name="Аватар",
        help_text="Загрузите аватар",
        **NULLABLE,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ("pk",)


class Payment(models.Model):
    class PaymentType(models.TextChoices):
        CASH = "cash", "Наличными"
        BANK = "bank", "Перевод на счёт"
        CARD = "card", "Банковская карта"

    payer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        **NULLABLE,
        verbose_name="плательщик",
        related_name="payments",
    )
    payment_date = models.DateField(auto_now_add=True, verbose_name="Дата оплаты")
    paid_course = models.ForeignKey(
        Course, on_delete=models.SET_NULL, verbose_name="Оплаченный курс", **NULLABLE
    )
    paid_lesson = models.ForeignKey(
        Lesson, on_delete=models.SET_NULL, verbose_name="Оплаченный урок", **NULLABLE
    )
    amount = models.DecimalField(
        decimal_places=2, max_digits=20, verbose_name="Сумма оплаты"
    )
    type = models.CharField(
        max_length=20, choices=PaymentType.choices, verbose_name="Способ оплаты"
    )
    stripe_session_id = models.CharField(
        max_length=255,
        **NULLABLE,
        verbose_name="ID сессии Stripe",
        help_text="Идентификатор сессии оплаты в Stripe",
    )

    def __str__(self):
        return f"{self.payer} - {self.paid_course if self.paid_course else self.paid_lesson} - {self.amount}"

    class Meta:
        verbose_name = "оплата"
        verbose_name_plural = "оплаты"
        ordering = ("payer", "payment_date")
