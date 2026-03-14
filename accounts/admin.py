# WIND_Project/accounts/admin.py

from django.contrib import admin
from .models import UploadedFile, OTP, FirebaseUser, UserSession, VideoCheck, VideoResult

# ----------------------------
# Uploaded File
# ----------------------------
@admin.register(UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'file_type', 'size_mb', 'category', 'uploaded_at')
    search_fields = ('title', 'user__email', 'category')
    list_filter = ('file_type', 'category', 'uploaded_at')
    ordering = ('-uploaded_at',)

# ----------------------------
# OTP
# ----------------------------
@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ('user', 'otp', 'created_at')
    search_fields = ('user__email', 'otp')
    list_filter = ('created_at',)
    ordering = ('-created_at',)

# ----------------------------
# Firebase User
# ----------------------------
@admin.register(FirebaseUser)
class FirebaseUserAdmin(admin.ModelAdmin):
    list_display = ('email', 'uid', 'last_login')
    search_fields = ('email', 'uid')
    list_filter = ('last_login',)
    ordering = ('-last_login',)

# ----------------------------
# User Session
# ----------------------------
@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'login_time', 'logout_time', 'ip_address')
    search_fields = ('user__email', 'ip_address')
    list_filter = ('login_time',)
    ordering = ('-login_time',)

# ----------------------------
# Video Check / Analysis
# ----------------------------
@admin.register(VideoCheck)
class VideoCheckAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'video', 'duration', 'is_fake', 'resolution', 'fps',
        'brightness', 'blur_score', 'noise_level', 'motion_level',
        'faces_detected', 'inference_time', 'created_at'
    )
    search_fields = ('video',)
    list_filter = ('is_fake', 'created_at', 'resolution')
    ordering = ('-created_at',)

# ----------------------------
# Video Result
# ----------------------------
@admin.register(VideoResult)
class VideoResultAdmin(admin.ModelAdmin):
    list_display = ('id', 'video', 'score', 'analyzed_at')
    search_fields = ('video__video', 'result_text')
    list_filter = ('analyzed_at',)
    ordering = ('-analyzed_at',)