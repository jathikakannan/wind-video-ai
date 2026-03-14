from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.utils import timezone
from .models import UserSession


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):

    ip = request.META.get('REMOTE_ADDR')

    UserSession.objects.create(
        user=user,
        login_time=timezone.now(),
        ip_address=ip
    )


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):

    session = UserSession.objects.filter(
        user=user,
        logout_time__isnull=True
    ).last()

    if session:
        session.logout_time = timezone.now()
        session.save()