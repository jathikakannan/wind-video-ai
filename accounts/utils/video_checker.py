import subprocess
import json
import os
from moviepy import VideoFileClip
import speech_recognition as sr
import cv2
import numpy as np

from accounts.models import VideoCheck  # correct import for VideoCheck

# Detect Render environment
# Detect Render environment
IS_RENDER = os.environ.get("RENDER") is not None

# Lazy model variables
classifier = None
category_classifier = None

# FFmpeg paths
import os

IS_RENDER = os.environ.get("RENDER") is not None

if IS_RENDER:
    FFMPEG_PATH = "/usr/bin/ffmpeg"
    FFPROBE_PATH = "/usr/bin/ffprobe"
else:
    FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"
    FFPROBE_PATH = r"C:\ffmpeg\bin\ffprobe.exe"
# ---------------------------------------
# LAZY LOAD TRANSFORMER MODELS
# ---------------------------------------
def get_classifier():
    global classifier

    if classifier is None and not IS_RENDER:
        from transformers import pipeline
        classifier = pipeline(
            "text-classification",
            model="distilbert-base-uncased"
        )

    return classifier


def get_category_classifier():
    global category_classifier

    if category_classifier is None and not IS_RENDER:
        from transformers import pipeline
        category_classifier = pipeline(
            "zero-shot-classification",
            model="typeform/distilbert-base-uncased-mnli"
        )

    return category_classifier


# ---------------------------------------
# 🎥 VIDEO INFO
# ---------------------------------------
def get_video_info(video_path):

    try:

        cmd = [
            FFPROBE_PATH,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries",
            "stream=width,height,r_frame_rate,codec_name,bit_rate",
            "-show_entries",
            "format=duration,size,bit_rate",
            "-of", "json",
            video_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)

        stream = data["streams"][0]
        fmt = data["format"]

        width = int(stream.get("width", 0))
        height = int(stream.get("height", 0))

        fps_parts = stream.get("r_frame_rate", "0/1").split("/")
        fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else 0

        duration = float(fmt.get("duration", 0))
        size = int(fmt.get("size", 0))

        codec = stream.get("codec_name", "Unknown")
        bitrate = int(stream.get("bit_rate") or fmt.get("bit_rate", 0))

        orientation = "Landscape" if width >= height else "Portrait"

        return {
            "width": width,
            "height": height,
            "fps": round(fps,2),
            "duration": round(duration,2),
            "size_mb": round(size / (1024*1024),2),
            "codec": codec,
            "bitrate_kbps": round(bitrate / 1000,2),
            "orientation": orientation
        }

    except Exception as e:
        print("Video info error:", e)
        return None


# ---------------------------------------
# RESOLUTION
# ---------------------------------------
def get_video_resolution(video_path):

    info = get_video_info(video_path)

    if info:
        return info["width"], info["height"], info["fps"]

    return 0,0,0


# ---------------------------------------
# DURATION
# ---------------------------------------
def get_video_duration(video_path):

    try:
        clip = VideoFileClip(video_path)
        duration = clip.duration
        clip.close()
        return round(duration,2)

    except:
        return 0


# ---------------------------------------
# AUDIO → TEXT
# ---------------------------------------
def extract_audio_text(video_path):

    try:

        clip = VideoFileClip(video_path)

        if clip.audio is None:
            clip.close()
            return "No audio found"

        audio_path = "temp_audio.wav"

        clip.audio.write_audiofile(audio_path)
        clip.close()

        r = sr.Recognizer()

        with sr.AudioFile(audio_path) as source:
            audio = r.record(source)
            text = r.recognize_google(audio)

        os.remove(audio_path)

        return text

    except:
        return "Speech not detected"


# ---------------------------------------
# FAKE NEWS CHECK
# ---------------------------------------
def check_fake_news(text):

    if not text:
        return {"label":"UNKNOWN","score":0}

    model = get_classifier()

    if model is None:
        return {"label":"MODEL_DISABLED_ON_RENDER","score":0}

    try:

        result = model(text[:512])[0]

        label = result["label"]
        score = result["score"]

        return {
            "label":label,
            "score":round(score*100,2)
        }

    except:
        return {"label":"UNKNOWN","score":0}


# ---------------------------------------
# VIDEO QUALITY ANALYSIS
# ---------------------------------------
def check_video_quality(video_path):

    cap = cv2.VideoCapture(video_path)

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    blur_scores = []
    brightness_scores = []
    noise_scores = []
    motion_scores = []

    black_frames = 0
    prev_frame = None

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        blur = cv2.Laplacian(gray, cv2.CV_64F).var()
        blur_scores.append(blur)

        brightness = np.mean(gray)
        brightness_scores.append(brightness)

        noise = np.std(gray)
        noise_scores.append(noise)

        if brightness < 10:
            black_frames += 1

        if prev_frame is not None:
            diff = cv2.absdiff(prev_frame, gray)
            motion_scores.append(np.mean(diff))

        prev_frame = gray

    cap.release()

    avg_blur = np.mean(blur_scores) if blur_scores else 0
    avg_brightness = np.mean(brightness_scores) if brightness_scores else 0
    avg_noise = np.mean(noise_scores) if noise_scores else 0
    avg_motion = np.mean(motion_scores) if motion_scores else 0

    motion_level = "Low" if avg_motion < 2 else "Medium" if avg_motion < 10 else "High"

    quality = "GOOD"

    if avg_blur < 50:
        quality = "Blurry"

    if avg_brightness < 40:
        quality = "Dark"

    audio_status = "Present"

    try:

        clip = VideoFileClip(video_path)

        if clip.audio is None:
            audio_status = "No Audio"

        clip.close()

    except:
        audio_status = "Unknown"

    return {
        "resolution": f"{width}x{height}",
        "fps": round(fps,2),
        "frames": frame_count,
        "brightness": round(avg_brightness,2),
        "blur_score": round(avg_blur,2),
        "noise_level": round(avg_noise,2),
        "motion_level": motion_level,
        "black_frames": black_frames,
        "audio": audio_status,
        "quality": quality
    }


# ---------------------------------------
# VIDEO CATEGORY CLASSIFICATION
# ---------------------------------------
CATEGORIES = [
    "education",
    "songs",
    "comedy",
    "emotions",
    "tutorial"
]

def classify_video(text):

    if not text:
        return "others"

    model = get_category_classifier()

    if model is None:
        return "model_disabled"

    try:

        result = model(
            text[:200],
            candidate_labels=CATEGORIES
        )

        return result["labels"][0]

    except Exception as e:
        print("Category classification error:", e)
        return "others"


# ---------------------------------------
# Thumbnail
# ---------------------------------------
def generate_thumbnail(video_path):

    cap = cv2.VideoCapture(video_path)

    success, frame = cap.read()

    if success:
        thumbnail_path = "thumbnail.jpg"
        cv2.imwrite(thumbnail_path, frame)
        cap.release()
        return thumbnail_path

    cap.release()
    return None


# ---------------------------------------
# Scene Detection
# ---------------------------------------
def detect_scene_changes(video_path):

    cap = cv2.VideoCapture(video_path)

    prev_frame = None
    scene_changes = 0

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if prev_frame is not None:

            diff = cv2.absdiff(prev_frame, gray)
            score = diff.mean()

            if score > 30:
                scene_changes += 1

        prev_frame = gray

    cap.release()

    return scene_changes


# ---------------------------------------
# Total Frames
# ---------------------------------------
def get_total_frames(video_path):

    cap = cv2.VideoCapture(video_path)

    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    cap.release()

    return frames
      # make sure path is correct

def detect_and_save_faces(video_path, video_file=None):
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    cap = cv2.VideoCapture(video_path)
    frame_count = 0
    faces_detected = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        if frame_count % 10 != 0:  # process every 10th frame
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)
        faces_detected += len(faces)

    cap.release()
    print("Faces detected:", faces_detected)

    # Save to DB
    if video_file:
        VideoCheck.objects.create(
            video=video_file,
            faces_detected=faces_detected
        )

    return faces_detected
# Keep backward compatibility
# At the bottom of accounts/utils/video_checker.py

def video_analysis(video_path, video_file=None):
    """Perform complete video analysis: quality, faces, and scenes."""
    quality = check_video_quality(video_path)
    faces = detect_and_save_faces(video_path, video_file)
    scenes = detect_scene_changes(video_path)

    return {
        "quality": quality,
        "faces_detected": faces,
        "scene_changes": scenes
    }

# Alias for backward compatibility with views.py
window_frame_analysis = video_analysis