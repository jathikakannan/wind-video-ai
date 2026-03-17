from django.urls import path
from . import views




urlpatterns = [

    # Authentication
    path('', views.login_view, name='login'),
    path('verify/', views.verify_otp, name='verify_otp'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('logout/', views.logout_view, name='logout'),

    # Upload
    path('upload/', views.upload_file, name='upload_file'),

    # Smart Upload
    path("smart-upload/", views.smart_upload, name="smart_upload"),

    # Firebase
    path("firebase-login/", views.firebase_login, name="firebase_login"),
    path("firebase-logout/", views.firebase_logout, name="firebase_logout"),

    # Search
    path("search/", views.search_files_default, name="search_files"),

    # Video
    path("videos/", views.video_list, name="video_list"),
    path('analyze-windows/<int:id>/', views.analyze_windows, name='analyze_windows'),
    path('advanced-analysis/<int:id>/', views.advanced_video_analysis, name='advanced_analysis'),
    path("video-dashboard/", views.video_dashboard, name="video_dashboard"),
    path("dashboard-data/", views.dashboard_data, name="dashboard_data"),
        path('generate-report/', views.generate_report, name='generate_report'),  # <- new
            path('batch-process/', views.batch_process, name='batch_process'),  # ✅ new URL




    

    






]