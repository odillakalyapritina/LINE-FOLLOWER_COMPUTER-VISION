import cv2
import numpy as np
import requests
import time
import threading
from queue import Queue

# Konfigurasi Alamat IP
ESP32_IP = "http://172.20.10.7:80"
DROIDCAM_URL = "http://172.20.10.2:6712/video"

# Command queue for ESP32 communication
command_queue = Queue()
last_command = None
command_cooldown = 0.8  # Cooldown lebih panjang untuk pemula

# Toleransi dan zona presisi (diperbesar)
DEAD_ZONE = 40           # Zona lurus (pixel) - Diperbesar
TURN_THRESHOLD = 80      # Ambang belok tajam (pixel) - Diperbesar
HISTORY_SIZE = 5         # Ukuran history untuk smoothing

# HSV range untuk warna hitam (sesuaikan dengan kondisi)
LOWER_BLACK = np.array([0, 0, 0])
UPPER_BLACK = np.array([180, 255, 50])

# Penyimpanan history posisi garis
position_history = []
no_line_count = 0         # Counter untuk deteksi garis hilang

def send_command_to_esp32():
    """Thread function to send commands to ESP32"""
    global last_command
    while True:
        command = command_queue.get()
        if command == "exit":
            break
        try:
            response = requests.get(f"{ESP32_IP}/{command}", timeout=0.5)
            print(f"Sent: {command} | Response: {response.text}")
            last_command = command
        except Exception as e:
            print(f"Error sending command: {e}")
        command_queue.task_done()

def get_line_center(frame):
    """Deteksi pusat garis dengan filter HSV dan noise reduction"""
    # Crop ROI (fokus di bagian bawah frame)
    height, width = frame.shape[:2]
    roi_height = height // 2
    roi = frame[roi_height:, :]
    
    # Convert to HSV and threshold
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, LOWER_BLACK, UPPER_BLACK)
    
    # Noise reduction
    kernel = np.ones((5,5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    
    # Find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    
    # Find largest contour
    largest_contour = max(contours, key=cv2.contourArea)
    
    # Filter small contours (noise)
    if cv2.contourArea(largest_contour) < 500:
        return None
        
    M = cv2.moments(largest_contour)
    if M["m00"] == 0:
        return None
    
    # Calculate center and adjust to full frame coordinates
    cx = int(M["m10"] / M["m00"])
    cy = int(M["m01"] / M["m00"]) + roi_height
    
    return cx, cy

def calculate_smoothed_position(new_pos):
    """Smooth position using moving average"""
    global position_history
    
    position_history.append(new_pos)
    if len(position_history) > HISTORY_SIZE:
        position_history.pop(0)
    
    # Calculate average
    avg_x = sum(p[0] for p in position_history) // len(position_history)
    avg_y = sum(p[1] for p in position_history) // len(position_history)
    
    return (avg_x, avg_y)

def main():
    global no_line_count, last_command
    
    # Start ESP32 communication thread
    esp32_thread = threading.Thread(target=send_command_to_esp32, daemon=True)
    esp32_thread.start()
    
    # Video capture setup
    cap = cv2.VideoCapture(DROIDCAM_URL)
    if not cap.isOpened():
        print("Error: Cannot connect to DroidCam")
        command_queue.put("exit")
        return
    
    # Set buffer size and resolution
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    last_command_time = time.time()
    fps_update_time = time.time()
    fps_counter = 0
    current_fps = 0
    
    try:
        while True:
            start_time = time.time()
            
            # Read frame
            ret, frame = cap.read()
            if not ret:
                print("Failed to get frame")
                break
            
            # Gambar batas ROI
            height, width = frame.shape[:2]
            roi_height = height // 2
            
            # Gambar persegi panjang untuk menunjukkan area ROI
            cv2.rectangle(frame, (0, roi_height), (width, height), (255, 0, 0), 2)
            cv2.putText(frame, "ROI", (10, roi_height - 10), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
            
            # Calculate FPS
            fps_counter += 1
            if time.time() - fps_update_time >= 1.0:
                current_fps = fps_counter
                fps_counter = 0
                fps_update_time = time.time()
            
            current_time = time.time()
            
            # +++ PERUBAHAN UTAMA: GESER GARIS TENGAH KE KANAN 25% +++
            center_x = int(width * 0.25)  # Garis tengah di 25% lebar frame
            
            # SELALU proses deteksi garis
            line_center = get_line_center(frame)
            
            if line_center:
                no_line_count = 0
                # Smooth position
                smoothed_pos = calculate_smoothed_position(line_center)
                cx, cy = smoothed_pos
                
                # Draw detected elements
                cv2.circle(frame, (cx, cy), 10, (0, 0, 255), -1)
            else:
                no_line_count += 1

            # Periksa cooldown SETELAH deteksi garis
            cooldown_active = (current_time - last_command_time) <= command_cooldown
            
            # Penanganan garis hilang (prioritas tinggi)
            if no_line_count > 10:
                if last_command != "stop":
                    command_queue.put("stop")
                    last_command = "stop"
                    last_command_time = current_time
                cv2.putText(frame, "GARIS HILANG!", (width//2-100, height//2), 
                          cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)
            
            # Pemrosesan perintah normal (hanya jika tidak dalam cooldown dan ada garis)
            elif not cooldown_active and line_center:
                deviation = cx - center_x
                abs_deviation = abs(deviation)
                
                # +++ KONFIGURASI MOTOR DENGAN 2 PIN +++
                # Determine command based on deviation
                if abs_deviation < DEAD_ZONE:
                    command = "forward"    # IN1 dan IN4 HIGH
                    action_text = "MAJU"
                    color = (0, 255, 0)  # Hijau
                elif abs_deviation > TURN_THRESHOLD:
                    if deviation < 0:
                        command = "right"   # IN4 HIGH (motor kiri maju), IN1 LOW
                        action_text = "BELOK KANAN*"
                        color = (0, 0, 255)  # Merah
                    else:
                        command = "left"    # IN1 HIGH (motor kanan maju), IN4 LOW
                        action_text = "BELOK KIRI*"
                        color = (0, 0, 255)  # Merah
                else:
                    if deviation < 0:
                        command = "right"   # IN4 HIGH (motor kiri maju), IN1 LOW
                        action_text = "belok_kanan"
                        color = (0, 165, 255)  # Oranye
                    else:
                        command = "left"    # IN1 HIGH (motor kanan maju), IN4 LOW
                        action_text = "belok_kiri"
                        color = (0, 165, 255)  # Oranye
                
                # Send command if changed
                if command != last_command:
                    command_queue.put(command)
                    last_command = command
                    last_command_time = current_time
                
                # Display action text
                cv2.putText(frame, action_text, (cx-50, cy-20), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            
            # Draw GUI elements
            # Garis tengah (di 25% lebar frame)
            cv2.line(frame, (center_x, 0), (center_x, height), (0, 0, 255), 2)
            
            # Zona presisi (relatif terhadap garis tengah baru)
            cv2.line(frame, (center_x - DEAD_ZONE, 0), (center_x - DEAD_ZONE, height), (0, 255, 255), 1)
            cv2.line(frame, (center_x + DEAD_ZONE, 0), (center_x + DEAD_ZONE, height), (0, 255, 255), 1)
            cv2.line(frame, (center_x - TURN_THRESHOLD, 0), (center_x - TURN_THRESHOLD, height), (0, 100, 255), 1)
            cv2.line(frame, (center_x + TURN_THRESHOLD, 0), (center_x + TURN_THRESHOLD, height), (0, 100, 255), 1)
            
            # Tampilkan posisi garis tengah
            cv2.putText(frame, f"Tengah: {center_x}px", (center_x - 70, 60), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 0), 2)
            
            # Status cooldown
            if cooldown_active:
                cooldown_percent = min(100, int((current_time - last_command_time)/command_cooldown * 100))
                cv2.putText(frame, f"CD: {cooldown_percent}%", (width-120, 30), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            
            # Display FPS
            cv2.putText(frame, f"FPS: {current_fps}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Display last command
            if last_command:
                cv2.putText(frame, f"Last: {last_command}", (10, height-10), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 1)
            
            cv2.imshow('Line Follower Controller', frame)
            
            # Tampilkan mask untuk debug
            hsv_full = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            mask_full = cv2.inRange(hsv_full, LOWER_BLACK, UPPER_BLACK)
            cv2.imshow('Mask', mask_full)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    
    finally:
        # Cleanup
        command_queue.put("stop")
        command_queue.put("exit")
        cap.release()
        cv2.destroyAllWindows()
        esp32_thread.join(timeout=1)

if __name__ == "__main__":
    main()