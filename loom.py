import cv2
import numpy as np
import mss
import pyaudio
import wave
import threading
import time
import os
from moviepy.editor import VideoFileClip, AudioFileClip

# --- CONFIGURATION ---
OUTPUT_FILENAME = "LoomClone_Recording.mp4"
SCREEN_SIZE = (1920, 1080)  # Adjust to your monitor resolution
WEBCAM_INDEX = 0            # 0 is usually the default webcam
WEBCAM_SIZE = (200, 200)    # Size of the camera bubble
WEBCAM_POSITION = "bottom-left" # Options: bottom-left, bottom-right

class LoomRecorder:
    def __init__(self):
        self.recording = False
        self.screen_capture = mss.mss()
        self.audio = pyaudio.PyAudio()
        
        # Audio Config
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.rate = 44100
        self.chunk = 1024
        self.audio_frames = []
        
        # Video Config
        self.fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self.out = None
        self.cap = cv2.VideoCapture(WEBCAM_INDEX)

    def start_audio(self):
        stream = self.audio.open(format=self.audio_format, channels=self.channels,
                                 rate=self.rate, input=True, frames_per_buffer=self.chunk)
        print("[*] Audio Recording Started...")
        while self.recording:
            data = stream.read(self.chunk)
            self.audio_frames.append(data)
        
        stream.stop_stream()
        stream.close()
        self.audio.terminate()

        # Save temporary audio file
        wf = wave.open("temp_audio.wav", "wb")
        wf.setnchannels(self.channels)
        wf.setsampwidth(self.audio.get_sample_size(self.audio_format))
        wf.setframerate(self.rate)
        wf.writeframes(b''.join(self.audio_frames))
        wf.close()

    def get_webcam_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return None
        
        # Resize and make it square for the circle effect
        frame = cv2.resize(frame, (WEBCAM_SIZE[0], WEBCAM_SIZE[1]))
        
        # Create circular mask
        mask = np.zeros((WEBCAM_SIZE[1], WEBCAM_SIZE[0]), dtype=np.uint8)
        cv2.circle(mask, (WEBCAM_SIZE[0]//2, WEBCAM_SIZE[1]//2), WEBCAM_SIZE[0]//2, (255, 255, 255), -1)
        
        # Apply mask
        masked_frame = cv2.bitwise_and(frame, frame, mask=mask)
        return masked_frame, mask

    def start_video(self):
        # Setup Video Writer
        self.out = cv2.VideoWriter("temp_video.mp4", self.fourcc, 20.0, SCREEN_SIZE)
        print("[*] Video Recording Started... Press 'q' to stop.")
        
        monitor = self.screen_capture.monitors[1] # Primary monitor

        while self.recording:
            # 1. Capture Screen
            screen_shot = np.array(self.screen_capture.grab(monitor))
            frame = cv2.cvtColor(screen_shot, cv2.COLOR_BGRA2BGR)
            frame = cv2.resize(frame, SCREEN_SIZE)

            # 2. Capture Webcam
            cam_frame, cam_mask = self.get_webcam_frame()

            if cam_frame is not None:
                # Calculate position for webcam overlay
                h, w, _ = cam_frame.shape
                sh, sw, _ = frame.shape
                
                # Position logic
                if WEBCAM_POSITION == "bottom-left":
                    top_y = sh - h - 20
                    left_x = 20
                else:
                    top_y = sh - h - 20
                    left_x = sw - w - 20

                # Region of Interest (ROI) on screen
                roi = frame[top_y:top_y+h, left_x:left_x+w]

                # Blend images
                # Where mask is black (0), keep screen. Where white (255), use cam.
                img1_bg = cv2.bitwise_and(roi, roi, mask=cv2.bitwise_not(cam_mask))
                img2_fg = cv2.bitwise_and(cam_frame, cam_frame, mask=cam_mask)
                dst = cv2.add(img1_bg, img2_fg)
                
                # Put combined area back into main frame
                frame[top_y:top_y+h, left_x:left_x+w] = dst

            # Write frame
            self.out.write(frame)

            # Show preview (Optional, comment out if annoying)
            cv2.imshow("Loom Clone Preview (Minimize Me)", cv2.resize(frame, (960, 540)))
            
            if cv2.waitKey(1) == ord('q'):
                self.recording = False
                break

        self.out.release()
        self.cap.release()
        cv2.destroyAllWindows()

    def merge_media(self):
        print("[*] Merging Audio and Video... Please wait.")
        try:
            video_clip = VideoFileClip("temp_video.mp4")
            audio_clip = AudioFileClip("temp_audio.wav")
            
            final_clip = video_clip.set_audio(audio_clip)
            final_clip.write_videofile(OUTPUT_FILENAME, codec="libx264", audio_codec="aac")
            
            # Cleanup temp files
            video_clip.close()
            audio_clip.close()
            os.remove("temp_video.mp4")
            os.remove("temp_audio.wav")
            print(f"[*] Done! Saved as {OUTPUT_FILENAME}")
        except Exception as e:
            print(f"Error merging: {e}")

    def start(self):
        self.recording = True
        
        # Start Audio and Video in parallel threads
        audio_thread = threading.Thread(target=self.start_audio)
        video_thread = threading.Thread(target=self.start_video)
        
        audio_thread.start()
        video_thread.start()
        
        video_thread.join() # Wait for video loop to finish (triggered by 'q')
        audio_thread.join() # Ensure audio finishes
        
        self.merge_media()

if __name__ == "__main__":
    app = LoomRecorder()
    app.start()
