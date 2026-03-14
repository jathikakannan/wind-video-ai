import cv2
import os

def extract_frames(video_path, frame_folder):

    cap = cv2.VideoCapture(video_path)

    count = 0

    while True:
        ret, frame = cap.read()

        if not ret:
            break

        frame_path = f"{frame_folder}/frame_{count}.jpg"
        cv2.imwrite(frame_path, frame)

        count += 1

    cap.release()

    return count