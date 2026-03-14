from django import views
from django.contrib import admin
from django.urls import path, include

from django.conf import settings
from django.conf.urls.static import static
from accounts import views  


urlpatterns = [

    path('admin/', admin.site.urls),

    path('', include('accounts.urls')),
    path('accounts/', include('allauth.urls')),
    # otp_project/urls.py



    path('search/<str:filename>/', views.search_files, name='search_files'),
    path('search/', views.search_files, name='search_files_default'),



]


# Serve media files in development
if settings.DEBUG:

    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
