from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from .models import OTP, UploadedFile
import uuid
import time
import cv2
import os
import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend for server/PDF plotting
import matplotlib.pyplot as plt
from .utils.video_checker import (
    detect_and_save_faces,
    check_video_quality,
    extract_audio_text,
    window_frame_analysis,
    classify_video
)
from .models import VideoCheck 
from django.conf import settings
from .utils.metrics import calculate_wer
from otp_project.firebase import save_login_to_cloud, save_logout_to_cloud
import random
from datetime import timedelta
from .utils.metrics import calculate_wer
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib import messages
from django.conf import settings
from .utils.video_checker import check_video_quality
from .utils.video_checker import classify_video
from .utils.audio_extractor import extract_audio
from .utils.frame_extractor import extract_frames
from .utils.face_detection import detect_faces
from .utils.speech_recognition import transcribe_audio
import os


from django.http import JsonResponse
from django.utils.timezone import now
from firebase_admin import auth
from firebase_config import db
from firebase_config import save_login_to_cloud  # ADD THIS ON TOP
from .models import UserSession
from django.db.models import F, ExpressionWrapper, DurationField

from django.shortcuts import redirect
from django.contrib.auth import logout
from firebase_config import save_logout_to_cloud  # cloud function
import cloudinary.uploader
import cv2
import numpy as np
from transformers import pipeline

from .utils.video_checker import (    
    get_video_info,
    get_video_resolution,
    get_video_duration,
    extract_audio_text,
    check_fake_news,
    check_video_quality
)




# Generate 6-digit OTP
def generate_otp():
    return str(random.randint(100000, 999999))


# LOGIN + SEND OTP
def login_view(request):
    user = None  

    if request.method == 'POST':

        email = request.POST.get('email')

        if not email:
            messages.error(request, "Email is required")
            return redirect('login')

        # Get existing user
        user = User.objects.filter(email=email).first()

        # Create if not exists
        if not user:
            user = User.objects.create_user(
                username=email.split('@')[0] + str(random.randint(1000, 9999)),
                email=email
            )

        # Save login to Firebase safely
        try:
            save_login_to_cloud(user.email)
        except Exception as e:
            print("Firebase login save error:", e)

        # Delete old OTPs
        OTP.objects.filter(user=user).delete()

        # Generate OTP
        otp = generate_otp()

        # Save OTP
        OTP.objects.create(
            user=user,
            otp=otp,
            created_at=timezone.now()
        )

        # Send Email
        send_mail(
            "Your Login OTP",
            f"Your OTP is: {otp}\nValid for 5 minutes.",
            settings.EMAIL_HOST_USER,
            [email],
        )

        # Save session
        request.session['user_id'] = user.id

        return redirect('verify_otp')

    return render(request, 'login.html')
from django.contrib.auth import logout

def logout_view(request):

    if request.user.is_authenticated:
        try:
            save_logout_to_cloud(request.user.email)
        except Exception as e:
            print("Firebase logout save error:", e)

    logout(request)
    return redirect('login')

# VERIFY OTP
def verify_otp(request):

    if request.method == 'POST':

        otp_input = request.POST.get('otp')
        user_id = request.session.get('user_id')

        # Check session
        if not user_id:
            messages.error(request, "Session expired. Please login again.")
            return redirect('login')

        # Get user
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            messages.error(request, "User not found.")
            return redirect('login')

        # Get latest OTP
        otp_obj = OTP.objects.filter(user=user).last()

        if not otp_obj:
            messages.error(request, "OTP not found.")
            return redirect('login')

        # Check OTP Expiry (5 min)
        expiry_time = otp_obj.created_at + timedelta(minutes=5)

        if timezone.now() > expiry_time:
            otp_obj.delete()
            messages.error(request, "OTP expired. Please login again.")
            return redirect('login')

        # Verify OTP
        if otp_input == otp_obj.otp:

            # Login user
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            # Delete OTP
            otp_obj.delete()

            # Clear session
            request.session.pop('user_id', None)

            return redirect('dashboard')

        else:
            messages.error(request, "Invalid OTP")
            return redirect('verify_otp')

    return render(request, 'verify.html')


# DASHBOARD
@login_required
def dashboard(request):
    return render(request, 'dashboard.html')


# UPLOAD PAGE + HANDLER
import os
import re
from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import UploadedFile

def upload(request):
    ALLOWED_TYPES = ['pdf', 'txt', 'docx', 'mp4', 'avi', 'mov', 'mkv']
    MAX_SIZE = settings.MAX_UPLOAD_SIZE        # MB
    MAX_CLOUDINARY_SIZE_MB = 100               # Cloudinary free limit

    if request.method == "POST":
        uploaded_file = request.FILES.get('file')

        if not uploaded_file:
            messages.error(request, "Please select a file")
            return redirect('upload')

        file_name = uploaded_file.name
        file_type = file_name.split('.')[-1].lower()
        size_mb = round(uploaded_file.size / (1024 * 1024), 2)

        # Validate type
        if file_type not in ALLOWED_TYPES:
            messages.error(request, "Only PDF, TXT, DOCX, Video files allowed")
            return redirect('upload')

        # Validate local max size
        if size_mb > MAX_SIZE:
            messages.error(request, f"File must be under {MAX_SIZE} MB")
            return redirect('upload')

        # Validate Cloudinary max size
        if size_mb > MAX_CLOUDINARY_SIZE_MB:
            messages.error(request, f"File too large for Cloudinary. Max {MAX_CLOUDINARY_SIZE_MB} MB allowed.")
            return redirect('upload')

        # ✅ TEMP SAVE FILE (needed for ffmpeg video check)
        temp_path = os.path.join(settings.MEDIA_ROOT, uploaded_file.name)
        with open(temp_path, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        # ✅ VIDEO QUALITY CHECK (only for videos)
        if uploaded_file.content_type.startswith("video"):
            if not is_high_quality(temp_path):
                os.remove(temp_path)
                messages.error(request, "Low quality video rejected ❌ Only 1080p allowed.")
                return redirect('upload')

        # 🚀 Save to DB (or upload to Cloudinary if you already have that logic)
        UploadedFile.objects.create(
            user=request.user,
            title=uploaded_file.name,
            file_type=file_type,
            size_mb=size_mb,
            file=result['secure_url']  # Add this if uploading to Cloudinary
        )

        # ✅ CLEAN UP TEMP FILE
        if os.path.exists(temp_path):
            os.remove(temp_path)

        messages.success(request, "File uploaded successfully")
        return redirect('upload')  # Redirect after POST

    else:
        messages.error(request, "No file selected.")
        return redirect('upload')

    # GET request: show user's files
    files = UploadedFile.objects.filter(user=request.user).order_by('-uploaded_at')
    return render(request, 'upload.html', {'files': files})



from django.http import JsonResponse
from firebase_admin import auth
from firebase_config import db
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime

@csrf_exempt
def firebase_login(request):
    if request.method == "POST":
        id_token = request.POST.get("token")

        try:
            decoded = auth.verify_id_token(id_token)
            uid = decoded["uid"]
            email = decoded.get("email")

            # Save login time in Firestore
            db.collection("firebase_users").document(uid).set({
                "email": email,
                "last_login": str(datetime.now())
            }, merge=True)

            request.session["firebase_uid"] = uid

            return JsonResponse({"status": "firebase login success"})

        except Exception as e:
            return JsonResponse({"error": str(e)})

    return JsonResponse({"error": "Invalid request"})
    







from django.http import JsonResponse
from firebase_config import db
from datetime import datetime

def firebase_logout(request):
    uid = request.session.get("firebase_uid")

    if uid:
        db.collection("firebase_users").document(uid).set({
            "last_logout": datetime.now()
        }, merge=True)

    # Clear session (important)
    request.session.flush()

    return JsonResponse({"msg": "firebase logout saved"})




import base64
from django.core.files.storage import FileSystemStorage

def smart_upload(request):
    if request.method == "POST":
        file = request.FILES["file"]
        storage_type = request.POST.get("storage")  # local / cloud

        # ✅ LOCAL STORAGE (your existing style)
        if storage_type == "local":
            fs = FileSystemStorage()
            filename = fs.save(file.name, file)
            return JsonResponse({"msg": "Saved locally", "file": filename})

        # ☁️ CLOUD STORAGE (Firestore DB)
        elif storage_type == "cloud":
            encoded = base64.b64encode(file.read()).decode("utf-8")

            db.collection("cloud_files").add({
                "filename": file.name,
                "data": encoded,
                "uploaded_at": str(now())
            })

            return JsonResponse({"msg": "Saved in Firestore cloud"})
        












        from django.utils.timezone import now
from firebase_config import db

def save_login_to_cloud(user_email):
    db.collection("login_logs").add({
        "email": user_email,
        "login_time": str(now())
    })


    from django.core.files.storage import FileSystemStorage
import cloudinary.uploader

# views.py
from django.shortcuts import render, redirect
from .models import UploadedFile

import re
from django.utils import timezone
from django.shortcuts import render, redirect
from .models import UploadedFile








def upload_file(request):

    files = UploadedFile.objects.filter(user=request.user).order_by('-uploaded_at')

    motion_map = None
    motion_level_value = None
    resolution = None
    fps = None
    transcript = ""
    faces_detected = 0
    frame_count = 0
    inference_time = 0

    if request.method == "POST":

        uploaded_file = request.FILES.get('file')

        if not uploaded_file:
            messages.error(request, "No file selected")
            return redirect('upload_file')

        video_size = uploaded_file.size / (1024 * 1024)

        # ---------------------------
        # SAVE TEMP FILE
        # ---------------------------
        unique_name = f"{uuid.uuid4()}_{uploaded_file.name}"
        temp_path = os.path.join(settings.MEDIA_ROOT, unique_name)

        with open(temp_path, 'wb+') as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)

        # ---------------------------
        # VIDEO ANALYSIS
        # ---------------------------
        if uploaded_file.content_type.startswith("video"):

            print("Processing video:", temp_path)

            # Resolution
            width, height, fps = get_video_resolution(temp_path)
            resolution = f"{width}x{height}" if width and height else "Unknown"

            # Video Quality
            quality_data = check_video_quality(temp_path)

            motion_map = {
                "Low": 1.0,
                "Medium": 2.0,
                "High": 3.0
            }

            motion_level_value = motion_map.get(
                quality_data.get("motion_level"), None
            )

            quality = quality_data.get("quality")
            blur_score = quality_data.get("blur_score")
            brightness = quality_data.get("brightness")

            messages.info(
                request,
                f"Resolution: {resolution}, FPS: {fps} | Quality: {quality} | Blur: {blur_score} | Brightness: {brightness}"
            )

            # Duration
            duration = get_video_duration(temp_path)

            # ---------------------------
            # SPEECH RECOGNITION
            # ---------------------------
            transcript = extract_audio_text(temp_path)
            decoding_method = request.POST.get("decoding_method")
            reference_text = request.POST.get("reference_text")

            # WER calculation
            if reference_text:
                wer_score = calculate_wer(reference_text, transcript)
            else:
                wer_score = 0

            # ---------------------------
            # FRAME EXTRACTION
            # ---------------------------
            frames_folder = os.path.join(settings.MEDIA_ROOT, "frames")
            os.makedirs(frames_folder, exist_ok=True)

            try:
                frame_count = extract_frames(temp_path, frames_folder)
            except Exception as e:
                print("Frame extraction error:", e)

            # ---------------------------
            # FACE DETECTION + TIME
            # ---------------------------
            try:
                faces_detected, inference_time = detect_faces(temp_path)
            except Exception as e:
                print("Face detection error:", e)
                faces_detected = 0
                inference_time = 0

            print("Faces detected:", faces_detected)

            # ---------------------------
            # FAKE DETECTION
            # ---------------------------
            fake_result = check_fake_news(transcript)
            if fake_result:
                label = fake_result.get("label", "REAL")
            else:
                label = "REAL"

            is_fake = True if label.upper() == "FAKE" else False

            # ---------------------------
            # FIX AUDIO VALUE
            # ---------------------------
            audio_status = quality_data.get("audio")
            if audio_status == "Present":
                audio_value = 1.0
            else:
                audio_value = 0.0

            # ---------------------------
            # SAVE ANALYSIS
            # ---------------------------
            video_record = VideoCheck.objects.create(
                video=uploaded_file,
                duration=duration,
                transcript=transcript,
                is_fake=is_fake,
                wer_score=wer_score,
                resolution=resolution,
                fps=fps,
                brightness=brightness,
                blur_score=blur_score,
                noise_level=quality_data.get("noise_level"),
                motion_level=motion_level_value,
                black_frames=quality_data.get("black_frames"),
                audio=audio_value,
                quality_label=quality,
                faces_detected=faces_detected,
                inference_time=inference_time,
                decoding_method=decoding_method,
                reference_text=reference_text,
                size_mb=video_size,
            )

        # ---------------------------
        # AUTO CATEGORY DETECTION
        # ---------------------------
        text_for_classification = uploaded_file.name
        if transcript:
            text_for_classification = transcript

        category = classify_video(text_for_classification)

        # ---------------------------
        # CLOUDINARY UPLOAD
        # ---------------------------
        result = cloudinary.uploader.upload(
            temp_path,
            resource_type="auto",
            folder="user_uploads"
        )
        os.remove(temp_path)

        # ---------------------------
        # SAVE FILE RECORD
        # ---------------------------
        UploadedFile.objects.create(
            user=request.user,
            title=uploaded_file.name,
            file=result['secure_url'],
            file_type=uploaded_file.name.split('.')[-1],
            size_mb=uploaded_file.size / (1024 * 1024),
            category=category
        )

        messages.success(
            request,
            f"File uploaded successfully | Category: {category}"
        )

        return redirect('upload_file')

    return render(request, "upload.html", {"files": files})

from cloudinary import CloudinaryImage

def search_files(request, filename=None):
    search_query = request.GET.get('q') or filename

    if search_query:
        files = UploadedFile.objects.filter(title__icontains=search_query)
    else:
        files = UploadedFile.objects.all()

    # Generate signed URLs
    for file in files:
        file.secure_url = CloudinaryImage(file.file).build_url(
            resource_type='auto',
            type='authenticated',
            sign=True
        )

    return render(request, 'search_results.html', {'files': files, 'query': search_query})


import os
import uuid
from django.conf import settings
from django.shortcuts import render
from django.http import HttpResponse

def upload_video(request):

    if request.method == "POST":

        uploaded_file = request.FILES.get('file')

        if not uploaded_file:
            return HttpResponse("No file uploaded")

        unique_name = f"{uuid.uuid4()}_{uploaded_file.name}"
        temp_path = os.path.join(settings.MEDIA_ROOT, unique_name)

        # Save file temporarily
        with open(temp_path, 'wb+') as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)

        # Basic video info
        info = get_video_info(temp_path)

        # Video Quality Analysis
        quality_data = check_video_quality(temp_path)

        # Duration
        duration = get_video_duration(temp_path)

        # Transcript
        transcript = extract_audio_text(temp_path)

        # Fake detection
        fake_result = check_fake_news(transcript)

        if fake_result:
            fake_label = fake_result.get("label", "REAL")
            confidence = fake_result.get("score", 0)
        else:
            fake_label = "REAL"
            confidence = 0

        # ----- FACE DETECTION -----
        try:
            faces_detected, inference_time = detect_faces(temp_path)
        except Exception as e:
            print("Face detection error:", e)
            faces_detected = 0
            inference_time = 0

        print("Faces detected:", faces_detected)

        # ----- WINDOW/FRAME ANALYSIS -----
        windows = window_frame_analysis(temp_path, window_size=30)  # returns list of avg blur
        windows_data = [{"window_index": i+1, "avg_blur": val} for i, val in enumerate(windows)]

        # ----- SAVE VIDEO CHECK RECORD -----
        video_record = VideoCheck.objects.create(
            video=unique_name,  # Or uploaded_file if you want FileField to store original upload
            duration=duration,
            transcript=transcript,
            is_fake=(fake_label.upper() == "FAKE"),
            resolution=quality_data.get("resolution"),
            fps=quality_data.get("fps"),
            brightness=quality_data.get("brightness"),
            blur_score=quality_data.get("blur_score"),
            noise_level=quality_data.get("noise_level"),
            motion_level=quality_data.get("motion_level"),
            black_frames=quality_data.get("black_frames"),
            audio=1.0 if quality_data.get("audio") == "Present" else 0.0,
            quality_label=quality_data.get("quality"),
            faces_detected=faces_detected,
            inference_time=inference_time
        )

        # ----- CONTEXT FOR TEMPLATE -----
        context = {
            "info": info,
            "resolution": quality_data.get("resolution"),
            "fps": quality_data.get("fps"),
            "duration": duration,
            "transcript": transcript,
            "fake_label": fake_label,
            "confidence": confidence,
            "brightness": quality_data.get("brightness"),
            "blur_score": quality_data.get("blur_score"),
            "noise_level": quality_data.get("noise_level"),
            "motion_level": quality_data.get("motion_level"),
            "black_frames": quality_data.get("black_frames"),
            "audio": quality_data.get("audio"),
            "quality": quality_data.get("quality"),
            "faces_detected": faces_detected,        # <-- added for template/table
            "video_url": settings.MEDIA_URL + unique_name,
            "windows": windows_data
        }

        return render(request, "video.html", context)

    return render(request, "video.html")
from django.shortcuts import render
from .models import VideoCheck


from django.db.models import Avg
from .models import VideoCheck


import os
import tempfile
import requests
from django.shortcuts import render
from django.db.models import Avg
from .models import VideoCheck

# Helper function to download Cloudinary video temporarily
def download_temp_file(url):
    """Download Cloudinary video temporarily to analyze."""
    response = requests.get(url, stream=True)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    for chunk in response.iter_content(chunk_size=8192):
        temp_file.write(chunk)
    temp_file.close()
    return temp_file.name

from django.shortcuts import render
from django.db.models import Avg
from .models import VideoCheck
import os

def video_list(request):
    # Get all videos
    videos = VideoCheck.objects.all().order_by('-uploaded_at')

    windows_per_video = []  # List of windows metrics for all videos

    # Compute window metrics for each video
    for v in videos:
        if v.video and os.path.exists(v.video.path):
            windows = window_frame_analysis(v.video.path, window_size=30)
            windows_per_video.append({
                "video_id": v.id,
                "windows": windows
            })
        else:
            windows_per_video.append({
                "video_id": v.id,
                "windows": []
            })

    # Average metrics for charts (across all videos)
    avg_blur = VideoCheck.objects.aggregate(Avg('blur_score'))['blur_score__avg'] or 0
    avg_brightness = VideoCheck.objects.aggregate(Avg('brightness'))['brightness__avg'] or 0
    avg_noise = VideoCheck.objects.aggregate(Avg('noise_level'))['noise_level__avg'] or 0
    avg_motion = VideoCheck.objects.aggregate(Avg('motion_level'))['motion_level__avg'] or 0

    fake_count = VideoCheck.objects.filter(is_fake=True).count()
    real_count = VideoCheck.objects.filter(is_fake=False).count()

    context = {
        "videos": videos,
        "fake_count": fake_count,
        "real_count": real_count,
        "avg_blur": round(avg_blur, 2),
        "avg_brightness": round(avg_brightness, 2),
        "avg_noise": round(avg_noise, 2),
        "avg_motion": round(avg_motion, 2),
        "windows_per_video": windows_per_video,  # all window data
    }

    return render(request, "video_list.html", context)
def video_detail(request, id):
    video = VideoCheck.objects.get(id=id)
    return render(request, "video_detail.html", {"video": video})
    from django.shortcuts import render
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from cloudinary import CloudinaryImage

from django.http import JsonResponse

from django.http import JsonResponse

def search_files_default(request):

    query = request.GET.get("q", "")

    # ✅ Suggestion request (AJAX)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":

        files = UploadedFile.objects.filter(title__icontains=query)[:6]

        suggestions = []

        for file in files:
            if file.title:
                suggestions.append(file.title)

        return JsonResponse(suggestions, safe=False)

    # =========================
    # YOUR ORIGINAL SEARCH
    # =========================

    files = UploadedFile.objects.all()

    if query:

        titles = [file.title for file in files if file.title]

        vectorizer = TfidfVectorizer()

        tfidf_matrix = vectorizer.fit_transform(titles + [query])

        similarity = cosine_similarity(
            tfidf_matrix[-1], tfidf_matrix[:-1]
        ).flatten()

        ranked_files = sorted(
            zip(similarity, files),
            key=lambda x: x[0],
            reverse=True
        )

        files = [file for score, file in ranked_files if score > 0]

    for file in files:
        file.secure_url = CloudinaryImage(file.file).build_url(
            resource_type="auto",
            sign_url=True
        )

    return render(request, "search_results.html", {
        "files": files,
        "query": query
    })



import cv2
import numpy as np

def window_frame_analysis(video_path, window_size=30):
    """
    Analyze video in windows and compute:
    blur, brightness, noise, motion, and qualitative quality per window.
    """
    cap = cv2.VideoCapture(video_path)

    frame_count = 0
    blur_scores = []
    brightness_scores = []
    noise_scores = []
    motion_scores = []
    windows = []

    prev_gray = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Blur
        blur = cv2.Laplacian(gray, cv2.CV_64F).var()
        blur_scores.append(blur)

        # Brightness
        brightness_scores.append(np.mean(gray))

        # Noise (estimate as standard deviation of Laplacian)
        noise_scores.append(np.std(cv2.Laplacian(gray, cv2.CV_64F)))

        # Motion (difference from previous frame)
        if prev_gray is not None:
            motion = np.mean(cv2.absdiff(gray, prev_gray))
            motion_scores.append(motion)
        prev_gray = gray

        frame_count += 1

        # If window is complete
        if frame_count % window_size == 0:
            avg_blur = sum(blur_scores) / len(blur_scores)
            avg_brightness = sum(brightness_scores) / len(brightness_scores)
            avg_noise = sum(noise_scores) / len(noise_scores)
            avg_motion = sum(motion_scores) / len(motion_scores) if motion_scores else 0

            # Qualitative label
            if avg_blur < 100:
                quality = "Blur"
            elif avg_brightness < 50:
                quality = "Dark"
            elif avg_noise > 50:
                quality = "Noisy"
            elif avg_motion < 2:
                quality = "Static"
            else:
                quality = "Good"

            windows.append({
                "window_index": len(windows)+1,
                "avg_blur": avg_blur,
                "avg_brightness": avg_brightness,
                "avg_noise": avg_noise,
                "avg_motion": avg_motion,
                "quality": quality
            })

            # Reset for next window
            blur_scores = []
            brightness_scores = []
            noise_scores = []
            motion_scores = []

    # Handle last partial window
    if blur_scores:
        avg_blur = sum(blur_scores) / len(blur_scores)
        avg_brightness = sum(brightness_scores) / len(brightness_scores)
        avg_noise = sum(noise_scores) / len(noise_scores)
        avg_motion = sum(motion_scores) / len(motion_scores) if motion_scores else 0

        if avg_blur < 100:
            quality = "Blur"
        elif avg_brightness < 50:
            quality = "Dark"
        elif avg_noise > 50:
            quality = "Noisy"
        elif avg_motion < 2:
            quality = "Static"
        else:
            quality = "Good"

        windows.append({
            "window_index": len(windows)+1,
            "avg_blur": avg_blur,
            "avg_brightness": avg_brightness,
            "avg_noise": avg_noise,
            "avg_motion": avg_motion,
            "quality": quality
        })

    cap.release()
    return windows
def detect_problem_frames(video_path):

    cap = cv2.VideoCapture(video_path)

    frame_no = 0

    problem_frames = []

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        blur = cv2.Laplacian(gray, cv2.CV_64F).var()

        brightness = np.mean(gray)

        if blur < 40:
            problem_frames.append(f"Frame {frame_no} → Blur")

        if brightness < 30:
            problem_frames.append(f"Frame {frame_no} → Dark")

        frame_no += 1

    cap.release()

    return problem_frames[:10]
def calculate_quality_score(blur, brightness, noise, motion):

    score = 0

    score += (100 - blur)
    score += brightness
    score += (100 - noise)

    if motion < 0.5:
        score += 80
    else:
        score += 40

    final_score = round(score / 4, 2)

    if final_score > 75:
        label = "Good"
    elif final_score > 50:
        label = "Medium"
    else:
        label = "Low"

    return final_score, label
def generate_summary(transcript):

    try:

        summarizer = pipeline("summarization")

        summary = summarizer(
            transcript,
            max_length=60,
            min_length=20,
            do_sample=False
        )

        return summary[0]["summary_text"]

    except:
        return "Summary not available"
    def get_video_metadata(video_path):

      cap = cv2.VideoCapture(video_path)

      fps = cap.get(cv2.CAP_PROP_FPS)

      width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)

      height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)

      frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)

      duration = frame_count / fps if fps else 0

      cap.release()

    return {

        "resolution": f"{int(width)}x{int(height)}",
        "fps": fps,
        "duration": duration
    }
def get_video_metadata(video_path):

    cap = cv2.VideoCapture(video_path)

    fps = cap.get(cv2.CAP_PROP_FPS)

    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)

    height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)

    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)

    duration = frame_count / fps if fps else 0

    cap.release()

    return {

        "resolution": f"{int(width)}x{int(height)}",
        "fps": fps,
        "duration": duration
    }
def generate_recommendations(blur, brightness, noise):

    rec = []

    if blur > 60:
        rec.append("Use better camera focus")

    if brightness < 40:
        rec.append("Record video in brighter lighting")

    if noise > 50:
        rec.append("Reduce background noise")

    if not rec:
        rec.append("Video quality is good")

    return rec
def analyze_windows(video_path):

    windows = window_frame_analysis(video_path)

    analysis = []

    for i, value in enumerate(windows):

        if value < 40:
            analysis.append(f"Window {i} → Blur detected")

        else:
            analysis.append(f"Window {i} → Good")

    return analysis
def extract_keywords(text):

    words = text.split()

    keywords = list(set(words))

    return keywords[:10]
def build_dashboard_data(quality_data):

    dashboard = {

        "blur": quality_data.get("blur_score"),
        "brightness": quality_data.get("brightness"),
        "noise": quality_data.get("noise_level"),
        "motion": quality_data.get("motion_level")

    }

    return dashboard
def advanced_video_analysis(video_path, transcript):

    metadata = get_video_metadata(video_path)

    windows = analyze_windows(video_path)

    problem_frames = detect_problem_frames(video_path)

    quality_data = check_video_quality(video_path)

    score, label = calculate_quality_score(
        quality_data.get("blur_score",0),
        quality_data.get("brightness",0),
        quality_data.get("noise_level",0),
        quality_data.get("motion_level",0)
    )

    summary = generate_summary(transcript)

    recommendations = generate_recommendations(
        quality_data.get("blur_score",0),
        quality_data.get("brightness",0),
        quality_data.get("noise_level",0)
    )

    keywords = extract_keywords(transcript)

    return {

        "metadata": metadata,
        "windows": windows,
        "problem_frames": problem_frames,
        "quality_score": score,
        "quality_label": label,
        "summary": summary,
        "recommendations": recommendations,
        "keywords": keywords
    }



    # accounts/views.py

from django.shortcuts import render
from .models import VideoCheck
from django.db.models import Avg

from django.shortcuts import render
from django.db.models import Avg
from .models import VideoCheck

# accounts/views.py



# accounts/views.py

from django.shortcuts import render
from django.db.models import Avg
from .models import VideoCheck

# accounts/views.py
from django.shortcuts import render
from django.db.models import Avg
from .models import VideoCheck

# accounts/views.py
def video_dashboard(request):
    videos = VideoCheck.objects.all()

    for v in videos:
        suggestions = []

        # Blur
        if v.blur_score is not None:
            if v.blur_score > 5:
                suggestions.append("Video is blurry → Use a better camera or adjust focus")
            elif v.blur_score > 2:
                suggestions.append("Slight blur detected → Consider stabilization")

        # Brightness
        if v.brightness is not None:
            if v.brightness < 50:
                suggestions.append("Low brightness → Increase lighting or adjust exposure")
            elif v.brightness > 200:
                suggestions.append("High brightness → Reduce lighting or adjust exposure")

        # Noise
        if v.noise_level is not None and v.noise_level > 5:
            suggestions.append("High noise → Reduce background noise or improve mic quality")

        # Motion
        if v.motion_level is not None and v.motion_level > 10:
            suggestions.append("Excessive motion → Stabilize camera")

        # Black frames
        if v.black_frames is not None and v.black_frames > 0:
            suggestions.append("Black frames detected → Check video encoding or trimming")

        # Fake detection
        if v.is_fake:
            suggestions.append("Video flagged as FAKE → Verify source content")

        # Save suggestions in object (for template display)
        v.suggestion = "\n".join(suggestions) if suggestions else "Video looks good"

    context = {
        "videos": videos,
        "fake_count": videos.filter(is_fake=True).count(),
        "real_count": videos.filter(is_fake=False).count(),
        "avg_blur": round(sum(v.blur_score or 0 for v in videos)/len(videos), 2) if videos else 0,
        "avg_brightness": round(sum(v.brightness or 0 for v in videos)/len(videos), 2) if videos else 0,
        "avg_noise": round(sum(v.noise_level or 0 for v in videos)/len(videos), 2) if videos else 0,
        "avg_motion": round(sum(v.motion_level or 0 for v in videos)/len(videos), 2) if videos else 0,
        "windows": [],  # your window analysis data
    }

    return render(request, "video_dashboard.html", context)
    from django.db.models import Count, DurationField, ExpressionWrapper, F
from django.shortcuts import render
from django.db.models import Count, F, ExpressionWrapper, DurationField
from .models import UserSession
from datetime import datetime
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth

def get_user_session_stats():
    # Annotate each session with duration
    sessions = UserSession.objects.annotate(
        duration=ExpressionWrapper(F('logout_time') - F('login_time'), output_field=DurationField())
    )

    # --- Daily Stats ---
    daily_data = sessions.annotate(day=TruncDay('login_time')) \
                         .values('day') \
                         .annotate(count=Count('id')) \
                         .order_by('day')
    daily_labels = [x['day'].strftime('%Y-%m-%d') for x in daily_data]
    daily_counts = [x['count'] for x in daily_data]

    # --- Weekly Stats ---
    weekly_data = sessions.annotate(week=TruncWeek('login_time')) \
                          .values('week') \
                          .annotate(count=Count('id')) \
                          .order_by('week')
    weekly_labels = [x['week'].strftime('%Y-%m-%d') for x in weekly_data]
    weekly_counts = [x['count'] for x in weekly_data]

    # --- Monthly Stats ---
    monthly_data = sessions.annotate(month=TruncMonth('login_time')) \
                           .values('month') \
                           .annotate(count=Count('id')) \
                           .order_by('month')
    monthly_labels = [x['month'].strftime('%Y-%m') for x in monthly_data]
    monthly_counts = [x['count'] for x in monthly_data]

    # --- Average Session Duration in minutes ---
    total_seconds = sum([s.duration.total_seconds() for s in sessions if s.duration], 0)
    total_sessions = sessions.count()
    avg_session_minutes = (total_seconds / total_sessions) / 60 if total_sessions else 0

    return {
        'daily': {'labels': daily_labels, 'counts': daily_counts},
        'weekly': {'labels': weekly_labels, 'counts': weekly_counts},
        'monthly': {'labels': monthly_labels, 'counts': monthly_counts},
        'avg_duration': avg_session_minutes
    }

from django.shortcuts import render
from django.http import JsonResponse
from .models import VideoCheck
from .utils.session_stats import get_user_session_stats


from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
from django.db.models.functions import TruncDate

from .models import VideoCheck, UserSession
from .utils.session_stats import get_user_session_stats



from django.shortcuts import render
from django.utils import timezone
from django.db.models import Count
from django.db.models.functions import TruncDate
from datetime import timedelta
from .models import VideoCheck, UserSession

def dashboard(request):
    # ===== SESSION STATS =====
    stats = get_user_session_stats()  # returns dict with 'avg_duration'

    # ===== VIDEO DATA =====
    videos = VideoCheck.objects.all().order_by("-uploaded_at")
    total_videos = videos.count()

    # Safely handle None values for inference_time
    avg_time = 0
    if total_videos > 0:
        total_inference_time = 0
        for v in videos:
            total_inference_time += v.inference_time if v.inference_time is not None else 0
        avg_time = total_inference_time / total_videos

    # Safely handle None values for faces_detected
    total_faces = 0
    for v in videos:
        total_faces += v.faces_detected if v.faces_detected is not None else 0

    # ===== USER ACTIVITY COUNTERS =====
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)

    users_today = UserSession.objects.filter(login_time__date=today).count()
    users_week = UserSession.objects.filter(login_time__date__gte=week_ago).count()

    # ===== VIDEO PROCESSING TIMELINE =====
    video_timeline = (
        VideoCheck.objects
        .annotate(day=TruncDate('uploaded_at'))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )

    # Ensure timeline counts are never None
    timeline_labels = [str(v["day"]) for v in video_timeline]
    timeline_counts = [v["count"] if v["count"] is not None else 0 for v in video_timeline]

    # ===== CONTEXT =====
    context = {
        "avg_session_minutes": stats.get("avg_duration", 0),

        # video analytics
        "videos": videos,
        "total_videos": total_videos,
        "avg_time": round(avg_time, 2),
        "total_faces": total_faces,

        # user activity counters
        "users_today": users_today,
        "users_week": users_week,

        # video timeline graph
        "video_timeline_labels": timeline_labels,
        "video_timeline_counts": timeline_counts,
    }

    return render(request, "dashboard.html", context)
from .utils.audio_extractor import extract_audio
from .utils.frame_extractor import extract_frames
from .utils.face_detection import detect_faces
from .utils.speech_recognition import transcribe_audio
from .utils.benchmark import measure_inference

def process_video(video_path):

    audio_path = "temp_audio.wav"

    extract_audio(video_path, audio_path)

    transcript, inference_time = measure_inference(
        transcribe_audio, audio_path
    )

    frame_folder = "frames"

    extract_frames(video_path, frame_folder)

    faces = detect_faces(f"{frame_folder}/frame_0.jpg")

    return transcript, faces, inference_time
import cv2
import time

def detect_faces(video_path):

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    cap = cv2.VideoCapture(video_path)

    frame_count = 0
    faces_detected = 0

    start_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1

        # Process only every 10th frame
        if frame_count % 10 != 0:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.3,
            minNeighbors=5
        )

        faces_detected += len(faces)

    cap.release()

    end_time = time.time()

    inference_time = round(end_time - start_time, 2)

    print("Faces detected:", faces_detected)

    return faces_detected, inference_time
def dashboard_data(request):

    stats = get_user_session_stats()

    videos = VideoCheck.objects.all()

    total_videos = videos.count()

    avg_time = 0
    if total_videos > 0:
        avg_time = sum(getattr(v, "inference_time", 0) for v in videos) / total_videos

    total_faces = sum(getattr(v, "faces_detected", 0) for v in videos)

    video_names = [f"Video {v.id}" for v in videos]
    inference_times = [getattr(v, "inference_time", 0) for v in videos]

    data = {

        "daily_labels": stats["daily"]["labels"],
        "daily_counts": stats["daily"]["counts"],

        "weekly_labels": stats["weekly"]["labels"],
        "weekly_counts": stats["weekly"]["counts"],

        "monthly_labels": stats["monthly"]["labels"],
        "monthly_counts": stats["monthly"]["counts"],

        "video_names": video_names,
        "inference_times": inference_times,

        "total_videos": total_videos,
        "avg_time": round(avg_time, 2),
        "total_faces": total_faces
    }

    return JsonResponse(data)
def get_video_info(video_path):
    cap = cv2.VideoCapture(video_path)

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    resolution = f"{width}x{height}"

    cap.release()

    return resolution, fps
# Example: otp_project/app1/views.py
from otp_project.firebase import db  # import the Firestore client

def example_view(request):
    # Get all documents from "users" collection
    docs = db.collection("users").get()
    
    users = [doc.to_dict() for doc in docs]
    return render(request, "example.html", {"users": users})
# accounts/views.py

# accounts/views.py
# accounts/views.py
from django.template.loader import render_to_string
from django.http import HttpResponse
from xhtml2pdf import pisa
import datetime
import matplotlib.pyplot as plt
import io
import base64

from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from .models import UploadedFile, VideoCheck  # Ensure correct import

# ------------------------
# PDF Report Generation
# ------------------------
@login_required




def generate_report(request):
    if request.method == "POST":
        # Get video IDs sent from batch process
        video_ids = request.POST.getlist('video_ids')  # e.g. ['12','13']
        if not video_ids:
            return HttpResponse("No videos selected for report", status=400)

        videos = VideoCheck.objects.filter(id__in=video_ids)

        # ------------------------
        # Generate suggestions for each video
        # ------------------------
        for v in videos:
            suggestions = []
            if v.blur_score is not None:
                if v.blur_score > 5: 
                    suggestions.append("Video is blurry → Use better camera or adjust focus")
                elif v.blur_score > 2: 
                    suggestions.append("Slight blur → Consider stabilization")
            if v.brightness is not None:
                if v.brightness < 50: 
                    suggestions.append("Low brightness → Increase lighting")
                elif v.brightness > 200: 
                    suggestions.append("High brightness → Reduce lighting")
            if v.noise_level is not None and v.noise_level > 5:
                suggestions.append("High noise → Improve mic quality")
            if v.motion_level is not None and v.motion_level > 10:
                suggestions.append("Excessive motion → Stabilize camera")
            if v.black_frames is not None and v.black_frames > 0:
                suggestions.append("Black frames detected → Check video trimming/encoding")
            if v.is_fake:
                suggestions.append("Video flagged as FAKE → Verify source content")
            v.suggestion = "\n".join(suggestions) if suggestions else "Video looks good"

        # ------------------------
        # Charts for only these videos
        # ------------------------
        fake_count = sum(v.is_fake for v in videos)
        real_count = len(videos) - fake_count

        # Pie chart
        fig1, ax1 = plt.subplots(figsize=(3,3))
        ax1.pie([fake_count, real_count], labels=['Fake','Real'], autopct='%1.1f%%', colors=['#ff4d4d','#28a745'])
        ax1.set_title("Fake vs Real Videos")
        buf1 = io.BytesIO()
        fig1.savefig(buf1, format='png', bbox_inches='tight')
        buf1.seek(0)
        pie_chart = base64.b64encode(buf1.getvalue()).decode('utf-8')
        plt.close(fig1)

        # Bar chart
        avg_brightness = sum(v.brightness or 0 for v in videos)/len(videos) if videos else 0
        avg_blur = sum(v.blur_score or 0 for v in videos)/len(videos) if videos else 0
        avg_noise = sum(v.noise_level or 0 for v in videos)/len(videos) if videos else 0
        avg_motion = sum(v.motion_level or 0 for v in videos)/len(videos) if videos else 0

        fig2, ax2 = plt.subplots(figsize=(5,3))
        ax2.bar(['Brightness','Blur','Noise','Motion'], 
                [avg_brightness, avg_blur, avg_noise, avg_motion],
                color=['#007bff','#ff6600','#ffc107','#17a2b8'])
        ax2.set_ylabel('Average Value')
        ax2.set_title("Video Quality Metrics")
        buf2 = io.BytesIO()
        fig2.savefig(buf2, format='png', bbox_inches='tight')
        buf2.seek(0)
        bar_chart = base64.b64encode(buf2.getvalue()).decode('utf-8')
        plt.close(fig2)

        # ------------------------
        # Render PDF
        # ------------------------
        html = render_to_string('video_report.html', {
            'videos': videos,
            'now': datetime.datetime.now(),
            'pie_chart': pie_chart,
            'bar_chart': bar_chart,
        })

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="video_report.pdf"'
        pisa_status = pisa.CreatePDF(html, dest=response)
        if pisa_status.err:
            return HttpResponse("Error generating PDF", status=500)

        return response  # return PDF response
    return HttpResponse("Invalid request", status=400)
# Batch Process Videos
# ------------------------
@login_required
def batch_process(request):
    if request.method == "POST":
        files = request.FILES.getlist("videos")  # gets multiple uploaded files
        for f in files:
            # Save in UploadedFile model
            UploadedFile.objects.create(
                user=request.user,
                title=f.name,
                file=f,              # file field in UploadedFile
                file_type=f.content_type,
                size_mb=f.size / (1024*1024)
            )

            # Optional: also create VideoCheck for analysis (auto suggestion)
            VideoCheck.objects.create(
                video=f,
                duration=None,       # fill after analysis
                resolution=None,
                fps=None
            )
        return redirect("video_dashboard")  # redirect back to dashboard
    return redirect("video_dashboard")