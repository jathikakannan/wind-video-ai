from django.contrib import admin
from .models import OTP, UploadedFile, VideoCheck, UserSession, FirebaseUser, VideoResult

@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ('user', 'otp', 'created_at')
    search_fields = ('user__email', 'otp')
    list_filter = ('created_at',)

@admin.register(UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'file_type', 'size_mb', 'category', 'uploaded_at')
    search_fields = ('title', 'user__email', 'category')
    list_filter = ('file_type', 'uploaded_at')

@admin.register(VideoCheck)
class VideoCheckAdmin(admin.ModelAdmin):
    list_display = ('id', 'video', 'uploaded_at', 'duration', 'is_fake', 'quality_label', 'blur_score', 'faces_detected')
    search_fields = ('video', 'transcript', 'reference_text', 'quality_label')
    list_filter = ('is_fake', 'uploaded_at', 'quality_label')
    readonly_fields = ('uploaded_at',)

@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'login_time', 'logout_time', 'ip_address')
    search_fields = ('user__email', 'ip_address')
    list_filter = ('login_time', 'logout_time')

@admin.register(FirebaseUser)
class FirebaseUserAdmin(admin.ModelAdmin):
    list_display = ('email', 'uid', 'last_login')
    search_fields = ('email', 'uid')
    list_filter = ('last_login',)

@admin.register(VideoResult)
class VideoResultAdmin(admin.ModelAdmin):
    list_display = ('video', 'score', 'analyzed_at')
    search_fields = ('video__video', 'result_text')
    list_filter = ('analyzed_at',)