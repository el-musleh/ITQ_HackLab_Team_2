import subprocess
import os
import re

def run_diagnostics():
    print("==================================================")
    print("JETSON NANO CAMERA HARDWARE DIAGNOSTICS")
    print("==================================================")
    
    # 1. Check dmesg for sensor probes
    print("\n[1] Checking camera sensor connection (dmesg)...")
    try:
        dmesg_proc = subprocess.Popen(['dmesg'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, _ = dmesg_proc.communicate()
        dmesg_str = out.decode('utf-8', errors='replace')
        
        imx_lines = [line for line in dmesg_str.splitlines() if 'imx219' in line or 'tegracam' in line or 'camera-control' in line]
        
        cam0_ok = True
        cam1_ok = True
        
        for line in imx_lines:
            print("  " + line)
            if '8-0010' in line and ('failed' in line or 'error' in line or '-121' in line):
                cam0_ok = False
            if '7-0010' in line and ('failed' in line or 'error' in line or '-121' in line):
                cam1_ok = False
                
        print("\nSensor Probe Summary:")
        print("  - CAM0 (Port 0, I2C 8-0010): {}".format("OK" if cam0_ok else "FAILED/DISCONNECTED (error -121)"))
        print("  - CAM1 (Port 1, I2C 7-0010): {}".format("OK" if cam1_ok else "FAILED/DISCONNECTED (error -121)"))
        
    except Exception as e:
        print("  Failed to read dmesg:", e)
        
    # 2. Check /dev/video0
    print("\n[2] Checking /dev/video0 device...")
    if os.path.exists("/dev/video0"):
        print("  /dev/video0 exists.")
    else:
        print("  ERROR: /dev/video0 does not exist! No camera device bound by the kernel.")
        return

    # 3. Analyze captured frame color channels
    print("\n[3] Capturing test frame and analyzing color channels...")
    try:
        import cv2
        import numpy as np
        
        cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
        if not cap.isOpened():
            print("  ERROR: Could not open /dev/video0 via V4L2. Camera might be locked by another process.")
            return
            
        re, img = cap.read()
        cap.release()
        
        if not re:
            print("  ERROR: Failed to read frame from /dev/video0.")
            return
            
        print("  Frame read successfully. Shape: {}".format(img.shape))
        
        # Analyze channels (BGR format)
        mean_b = np.mean(img[:, :, 0])
        mean_g = np.mean(img[:, :, 1])
        mean_r = np.mean(img[:, :, 2])
        
        print("  Channel means (BGR): Blue={:.1f}, Green={:.1f}, Red={:.1f}".format(mean_b, mean_g, mean_r))
        
        # Green screen detection
        if mean_g > 100 and mean_b < 10 and mean_r < 10:
            print("\nDIAGNOSIS: SOLID GREEN SCREEN DETECTED!")
            print("  This means the camera port driver is active, but the physical camera sensor")
            print("  is NOT sending any frame data. The capture buffer remains filled with zero bytes,")
            print("  which OpenCV translates to a green screen.")
        else:
            print("\n  Frame values look normal (not a pure solid green screen).")
            
    except Exception as e:
        print("  Diagnostic frame capture failed:", e)

if __name__ == "__main__":
    run_diagnostics()
