from django.urls import include, path
from rest_framework.routers import DefaultRouter
from users.apps import UsersConfig
from users.views import UserViewSet, PaymentListView, CreatePaymentView, PaymentIntentView

app_name = UsersConfig.name

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="users")

urlpatterns = [
    path("payments/", PaymentListView.as_view(), name="payment_list"),
    path("create-payment/", CreatePaymentView.as_view(), name="create_payment"),
    path("create-payment-intent/", PaymentIntentView.as_view(), name="payment_intent"),
] + router.urls

