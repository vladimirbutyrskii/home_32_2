import stripe
from django.conf import settings
from django.db import transaction

from lms.models import Course
from users.models import Payment, User


stripe.api_key = settings.STRIPE_SECRET_KEY


def create_stripe_product(course: Course) -> str:
    """Создает продукт в Stripe на основе курса"""
    product = stripe.Product.create(
        name=course.name,
        description=course.description or f"Курс: {course.name}",
    )
    return product.id


def create_stripe_price(amount: float, product_id: str) -> str:
    """Создает цену в Stripe для продукта"""
    # Сумма в копейках (центах)
    amount_in_cents = int(amount * 100)

    price = stripe.Price.create(
        product=product_id,
        unit_amount=amount_in_cents,
        currency="rub",
    )
    return price.id


def create_checkout_session(price_id: str, success_url: str, cancel_url: str) -> dict:
    """Создает сессию оплаты в Stripe"""
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[
            {
                "price": price_id,
                "quantity": 1,
            }
        ],
        mode="payment",
        success_url=success_url,
        cancel_url=cancel_url,
    )
    return {
        "session_id": session.id,
        "url": session.url,
    }


def create_payment_intent(amount: float, course_name: str) -> dict:
    """Создает PaymentIntent для оплаты (альтернативный вариант)"""
    amount_in_cents = int(amount * 100)

    intent = stripe.PaymentIntent.create(
        amount=amount_in_cents,
        currency="rub",
        metadata={
            "course_name": course_name,
        },
    )
    return {
        "client_secret": intent.client_secret,
        "payment_intent_id": intent.id,
    }


def process_payment(
    user: User,
    course: Course,
    amount: float,
    success_url: str,
    cancel_url: str,
) -> dict:
    """
    Полный процесс создания платежа:
    1. Создает продукт в Stripe
    2. Создает цену
    3. Создает сессию оплаты
    4. Сохраняет платеж в БД
    """
    with transaction.atomic():
        # Создаем продукт и цену в Stripe
        product_id = create_stripe_product(course)
        price_id = create_stripe_price(amount, product_id)

        # Создаем сессию оплаты
        session_data = create_checkout_session(
            price_id=price_id,
            success_url=success_url,
            cancel_url=cancel_url,
        )

        # Сохраняем платеж в БД
        payment = Payment.objects.create(
            payer=user,
            amount=amount,
            type="card",  # оплата картой через Stripe
            paid_course=course,
            stripe_session_id=session_data["session_id"],  # добавляем поле
        )

        return {
            "payment_id": payment.id,
            "session_id": session_data["session_id"],
            "payment_url": session_data["url"],
        }