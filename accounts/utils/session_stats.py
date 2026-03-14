from django.contrib.sessions.models import Session
from django.utils import timezone
from datetime import timedelta


def get_user_session_stats():

    now = timezone.now()

    daily_labels = []
    daily_counts = []

    for i in range(7):
        day = now - timedelta(days=i)
        label = day.strftime("%a")

        sessions = Session.objects.filter(expire_date__date=day.date())

        daily_labels.append(label)
        daily_counts.append(sessions.count())

    daily_labels.reverse()
    daily_counts.reverse()

    weekly_labels = ["Week 1","Week 2","Week 3","Week 4"]
    weekly_counts = [2,4,3,5]

    monthly_labels = ["Jan","Feb","Mar","Apr"]
    monthly_counts = [5,6,7,4]

    avg_duration = 10

    return {
        "daily":{"labels":daily_labels,"counts":daily_counts},
        "weekly":{"labels":weekly_labels,"counts":weekly_counts},
        "monthly":{"labels":monthly_labels,"counts":monthly_counts},
        "avg_duration":avg_duration
    }