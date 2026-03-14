# WIND_Project/accounts/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# ----------------------------
# OTP Model
# ----------------------------
class OTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.email} - {self.otp}"

# ----------------------------
# Uploaded File Model
# ----------------------------
class UploadedFile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    file = models.TextField()  # URL or path of uploaded file (Cloudinary / Local)
    file_type = models.CharField(max_length=20)
    size_mb = models.FloatField()
    category = models.CharField(max_length=100, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

# ----------------------------
# Video Check / Analysis Model
# ----------------------------
class VideoCheck(models.Model):

    video = models.FileField(upload_to="videos/")
    duration = models.FloatField(blank=True, null=True)

    transcript = models.TextField(blank=True, null=True)
    reference_text = models.TextField(blank=True, null=True)

    decoding_method = models.CharField(max_length=20, blank=True, null=True)

    wer_score = models.FloatField(blank=True, null=True)

    is_fake = models.BooleanField(default=False)

    resolution = models.CharField(max_length=20, blank=True, null=True)
    fps = models.FloatField(blank=True, null=True)

    brightness = models.FloatField(blank=True, null=True)
    blur_score = models.FloatField(blank=True, null=True)
    noise_level = models.FloatField(blank=True, null=True)

    motion_level = models.FloatField(blank=True, null=True)
    black_frames = models.IntegerField(blank=True, null=True)

    audio = models.FloatField(blank=True, null=True)

    quality_label = models.CharField(max_length=50, blank=True, null=True)

    faces_detected = models.IntegerField(default=0)

    inference_time = models.FloatField(blank=True, null=True)

    size_mb = models.FloatField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)  
    def __str__(self):
        return f"Video {self.id} - {self.video.name}"

# ----------------------------
# User Session Model
# ----------------------------
class UserSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    login_time = models.DateTimeField(default=timezone.now)
    logout_time = models.DateTimeField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)  # matches your admin.py

    def __str__(self):
        return f"{self.user.email} | {self.login_time} - {self.logout_time}"

# ----------------------------
# Firebase User
# ----------------------------
class FirebaseUser(models.Model):
    uid = models.CharField(max_length=100, unique=True)
    email = models.EmailField()
    last_login = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.email

# ----------------------------
# Video Result / Optional
# ----------------------------
class VideoResult(models.Model):
    video = models.ForeignKey(VideoCheck, on_delete=models.CASCADE)
    result_text = models.TextField(blank=True, null=True)
    score = models.FloatField(blank=True, null=True)
    analyzed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Result {self.id} for Video {self.video.id}"