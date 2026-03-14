from utils.audio_extractor import extract_audio
from utils.frame_extractor import extract_frames
from utils.face_detection import detect_faces
from utils.speech_recognition import transcribe_audio
import os

video_path = "test_video.mp4"
audio_path = "test_audio.wav"

current_dir = os.path.dirname(os.path.abspath(__file__))
frame_folder = os.path.join(current_dir, "frames")

print("Step 1: Extracting audio...")
extract_audio(video_path, audio_path)

print("Step 2: Speech recognition...")
text = transcribe_audio(audio_path)
print("Transcript:", text)

print("Step 3: Extracting frames...")
count = extract_frames(video_path, frame_folder)
print("Frames extracted:", count)

print("Step 4: Detecting faces...")

frame_path = os.path.join(frame_folder, "frame_0.jpg")
faces = detect_faces(frame_path)

print("Faces detected:", faces)

print("Pipeline completed successfully!")