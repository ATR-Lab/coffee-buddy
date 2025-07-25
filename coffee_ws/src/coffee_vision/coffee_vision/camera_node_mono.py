#!/usr/bin/env python3

import sys
import cv2
import rclpy
import time
import numpy as np
import threading
import os
import subprocess
import json
import collections
from rclpy.node import Node
from python_qt_binding.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QComboBox, QHBoxLayout, QCheckBox, QMessageBox
from python_qt_binding.QtGui import QImage, QPixmap
from python_qt_binding.QtCore import Qt, QTimer, pyqtSignal, QObject
from std_msgs.msg import Float32MultiArray, String
from sensor_msgs.msg import Image
from geometry_msgs.msg import Point
from cv_bridge import CvBridge

# Models directory for face detection models
MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
os.makedirs(MODELS_DIR, exist_ok=True)


class FrameGrabber(QObject):
    """Dedicated thread for frame capture to improve performance"""
    frame_ready = pyqtSignal(np.ndarray)
    error = pyqtSignal(str)
    
    def __init__(self, node=None):
        super().__init__()
        self.node = node
        # Camera properties
        self.camera = None
        self.camera_index = 0
        self.frame_width = 640
        self.frame_height = 480
        self.backend = cv2.CAP_ANY
        
        # Camera optimization settings
        self.target_fps = 30
        self.target_exposure = 100  # Auto exposure target (0-255)
        self.camera_props = {
            cv2.CAP_PROP_FRAME_WIDTH: self.frame_width,
            cv2.CAP_PROP_FRAME_HEIGHT: self.frame_height,
            cv2.CAP_PROP_FPS: self.target_fps,
            cv2.CAP_PROP_BUFFERSIZE: 1,  # Minimal latency
            # cv2.CAP_PROP_AUTOFOCUS: 0,  # Disable autofocus
            # cv2.CAP_PROP_AUTO_EXPOSURE: 1,  # Enable auto exposure
            # cv2.CAP_PROP_AUTO_WB: 1,  # Enable auto white balance
            # cv2.CAP_PROP_EXPOSURE: self.target_exposure,
        }
        self.running = False
        self.lock = threading.Lock()
        self.capture_thread = None
        self.process_thread = None
        self.publish_thread = None
        self.high_quality = False
        
        # Initialize shared frame buffer
        self.current_frame = None
        self.processed_frame = None
        self.current_faces = []
        self.frame_lock = threading.Lock()
        self.frame_timestamp = 0  # Track frame freshness
        
        # UI frame rate control
        self.last_ui_update = 0
        self.min_ui_interval = 1.0 / 30  # Target 30 FPS for UI
        
        # Face detection control
        self.last_detection_time = 0
        self.min_detection_interval = 1.0 / 6  # Max 6 face detections per second
        self.max_detection_time = 0.1  # Maximum 100ms for face detection
        self.detection_skip_frames = 5  # Process every 5th frame
        self.detection_frame_counter = 0
        
        # Publishing rate control
        self.last_publish_time = 0
        self.min_publish_interval = 1.0 / 30.0  # Max 30 fps for publishing
        
        # Face detection
        self.enable_face_detection = True
        self.face_detector = None
        self.face_net = None
        self.face_confidence_threshold = 0.5
        
        # Smoothing for face detection
        self.prev_faces = []
        self.smoothing_factor = 0.4  # Higher value = more smoothing
        self.smoothing_frames = 5    # Number of frames to average

        # # Get parameters
        # self.invert_x = self.get_parameter('invert_x').value
        # self.invert_y = self.get_parameter('invert_y').value
        # self.eye_range = self.get_parameter('eye_range').value
        
        # TODO: Added this hot fix
        self.invert_x = False
        self.invert_y = False
        # self.eye_range = 3.0
        self.eye_range = 1.0 # The constraint for the values of the eye movement in the UI

        # ROS publishers for face data and images
        if self.node:
            self.face_pub = node.create_publisher(String, 'face_detection_data', 10)
            self.face_position_pub = node.create_publisher(Point, '/vision/face_position', 10)
            self.face_position_pub_v2 = node.create_publisher(String, '/vision/face_position_v2', 10)
            self.frame_pub = node.create_publisher(Image, '/coffee_bot/camera/image_raw', 10)
            self.face_image_pub = node.create_publisher(Image, 'face_images', 10)
            self.bridge = CvBridge()
            
        # Face recognition data
        self.face_ids = {}  # Map of face index to recognized face ID
        self.last_recognition_time = 0
        self.recognition_timeout = 3.0  # Clear recognition data after 3 seconds
        
        self.init_face_detector()
     
    def publish_face_data(self, faces):
        """Publish face detection data for other nodes"""
        if not self.node:
            return
        
        # Ensure faces is at least an empty list
        faces = faces if faces else []
            
        # Create JSON with face data - convert NumPy types to Python native types
        face_data = {
            "timestamp": float(time.time()),
            "frame_width": int(self.frame_width),
            "frame_height": int(self.frame_height),
            "faces": [
                {
                    "x1": int(face["x1"]),
                    "y1": int(face["y1"]),
                    "x2": int(face["x2"]),
                    "y2": int(face["y2"]),
                    "center_x": int(face["center_x"]),
                    "center_y": int(face["center_y"]),
                    "confidence": float(face["confidence"]),
                    "id": str(face.get("id", "Unknown"))
                }
                for face in faces
            ]
        }
        
        # Publish
        msg = String()
        msg.data = json.dumps(face_data)
        self.face_pub.publish(msg)

    def publish_face_position_v2(self, faces):
        """Publish face detection data for other nodes"""
        if not self.node:
            return
            
        # Ensure faces is at least an empty list
        faces = faces if faces else []
            
        # Create JSON with face data - convert NumPy types to Python native types
        face_data = {
            "timestamp": float(time.time()),
            "frame_width": int(self.frame_width),
            "frame_height": int(self.frame_height),
            "faces": [
                {
                    "x1": int(face["x1"]),
                    "y1": int(face["y1"]),
                    "x2": int(face["x2"]),
                    "y2": int(face["y2"]),
                    "center_x": int(face["center_x"]),
                    "center_y": int(face["center_y"]),
                    "confidence": float(face["confidence"]),
                    "id": str(face.get("id", "Unknown"))
                }
                for face in faces
            ]
        }
        
        # Publish
        msg = String()
        msg.data = json.dumps(face_data)
        self.face_position_pub_v2.publish(msg)

        
    def publish_face_position(self, faces):
        """Process incoming face detection data"""

        try:
            # If no faces detected or all faces have very low confidence, publish zero position
            if not faces:
                self.target_face_position = Point()
                self.target_face_position.x = 0.0
                self.target_face_position.y = 0.0
                self.target_face_position.z = 0.0
                self.face_position_pub.publish(self.target_face_position)
                return

            # Select target face (largest/closest)
            largest_area = 0
            largest_face = None
            
            for face in faces:
                width = face['x2'] - face['x1']
                height = face['y2'] - face['y1']
                area = width * height
                
                if area > largest_area:
                    largest_area = area
                    largest_face = face
            
            if largest_face:
                self.target_face_position = (
                    largest_face['center_x'], 
                    largest_face['center_y']
                )
                
                # Log face position before transformation
                face_x = self.target_face_position[0]
                face_y = self.target_face_position[1]
                center_x = self.frame_width / 2
                center_y = self.frame_height / 2
                dx = face_x - center_x
                dy = face_y - center_y
                
                self.node.get_logger().debug(f"Face detected at ({face_x:.1f}, {face_y:.1f}), offset from center: ({dx:.1f}, {dy:.1f})")
                
                # Transform camera coordinates to eye controller coordinates
                eye_position = self.transform_camera_to_eye_coords(
                    self.target_face_position[0],
                    self.target_face_position[1]
                )
                
                # Call go_to_pos only if we have a valid position
                if eye_position:
                    # self.controller.go_to_pos(eye_position)
                    # self.node.get_logger().info(f'Moving eyes to position: ({eye_position[0]:.2f}, {eye_position[1]:.2f})')
                    point_msg = Point()
                    point_msg.x = eye_position[0]
                    point_msg.y = eye_position[1]
                    point_msg.z = 0.0
                    self.face_position_pub.publish(point_msg)

        except Exception as e:
            self.node.get_logger().error(f"Error processing face position data: {e}")

    def publish_face_images(self, frame, faces):
        """Extract and publish individual face images"""
        if not self.node:
            return
            
        try:
            for i, face in enumerate(faces):
                # Extract face with margin
                margin = 0.2  # 20%
                
                # Get dimensions
                x1, y1 = face['x1'], face['y1']
                x2, y2 = face['x2'], face['y2']
                h, w = frame.shape[:2]
                
                # Calculate margin
                margin_x = int((x2 - x1) * margin)
                margin_y = int((y2 - y1) * margin)
                
                # Apply margin
                x1_margin = max(0, x1 - margin_x)
                y1_margin = max(0, y1 - margin_y)
                x2_margin = min(w, x2 + margin_x)
                y2_margin = min(h, y2 + margin_y)
                
                # Extract face
                face_img = frame[y1_margin:y2_margin, x1_margin:x2_margin]
                
                # Skip if too small
                if face_img.size == 0 or face_img.shape[0] < 30 or face_img.shape[1] < 30:
                    continue
                    
                # Resize
                face_img = cv2.resize(face_img, (150, 150))
                
                # Publish
                face_msg = self.bridge.cv2_to_imgmsg(face_img, encoding="bgr8")
                face_msg.header.stamp = self.node.get_clock().now().to_msg()
                face_msg.header.frame_id = f"face_{i}"
                self.face_image_pub.publish(face_msg)
                
        except Exception as e:
            if self.node:
                self.node.get_logger().error(f"Error publishing face images: {e}")

    def transform_camera_to_eye_coords(self, camera_x, camera_y):
        """Transform camera coordinates to eye controller coordinates (-3.0 to 3.0 range)"""
        # Normalize to -1.0 to 1.0
        # Note: We invert the coordinates to ensure proper eye direction
        # (When face is on right side, eyes should look right)
        norm_x = (camera_x - self.frame_width/2) / (self.frame_width/2)
        norm_y = (camera_y - self.frame_height/2) / (self.frame_height/2)
        
        # Add sensitivity multiplier (like in eye_tracking.py)
        sensitivity = 1.5  # Higher = more sensitive eye movement
        norm_x *= sensitivity
        norm_y *= sensitivity
        
        # Apply inversions if configured
        # Note: By default we want norm_x to be positive when face is on right side
        # So default should have invert_x=False
        # TODO: Fix / look into
        if self.invert_x:
            norm_x = -norm_x
        if self.invert_y:
            norm_y = -norm_y
        
        # Scale to eye controller range (-3.0 to 3.0)
        eye_x = norm_x * self.eye_range
        eye_y = norm_y * self.eye_range
        
        # Clamp values to valid range
        eye_x = max(-self.eye_range, min(self.eye_range, eye_x))
        eye_y = max(-self.eye_range, min(self.eye_range, eye_y))
        
        # Debug output for tuning
        self.node.get_logger().debug(f'Camera coords: ({camera_x}, {camera_y}) -> Eye coords: ({eye_x}, {eye_y})')
        
        return (eye_x, eye_y)

    def publish_frame(self, frame):
        """Publish camera frame to ROS topics"""
        if not self.node:
            return
            
        try:
            frame_msg = self.bridge.cv2_to_imgmsg(frame, encoding="bgr8")
            frame_msg.header.stamp = self.node.get_clock().now().to_msg()
            self.frame_pub.publish(frame_msg)
        except Exception as e:
            if self.node:
                self.node.get_logger().error(f"Error publishing frame: {e}")
    
    def init_face_detector(self):
        """Initialize the OpenCV DNN face detector"""
        try:
            # Try to get the models from disk, or download them if not present
            model_file = os.path.join(MODELS_DIR, "opencv_face_detector_uint8.pb")
            config_file = os.path.join(MODELS_DIR, "opencv_face_detector.pbtxt")
            
            # Download the model files if they don't exist
            if not os.path.exists(model_file) or not os.path.exists(config_file):
                self.download_face_model(model_file, config_file)
            
            # Load the DNN face detector
            self.face_net = cv2.dnn.readNet(model_file, config_file)
            
            # Switch to a more accurate backend if available
            if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                self.face_net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
                self.face_net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
            else:
                self.face_net.setPreferableBackend(cv2.dnn.DNN_BACKEND_DEFAULT)
                self.face_net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            
            print("Face detector (OpenCV DNN) initialized successfully")
        except Exception as e:
            print(f"Error initializing face detector: {e}")
            self.face_net = None
    
    def download_face_model(self, model_file, config_file):
        """Download the face detection model if needed"""
        try:
            # Model URLs
            model_url = "https://github.com/spmallick/learnopencv/raw/refs/heads/master/AgeGender/opencv_face_detector_uint8.pb"
            config_url = "https://raw.githubusercontent.com/spmallick/learnopencv/refs/heads/master/AgeGender/opencv_face_detector.pbtxt"
            
            # Download the files
            import urllib.request
            print("Downloading face detection model...")
            urllib.request.urlretrieve(model_url, model_file)
            urllib.request.urlretrieve(config_url, config_file)
            print("Face detection model downloaded successfully")
        except Exception as e:
            print(f"Error downloading face model: {e}")
            raise
    
    def start(self, camera_index, backend=cv2.CAP_ANY):
        with self.lock:
            if self.running:
                self.stop()
            
            self.camera_index = camera_index
            self.backend = backend
            self.running = True
            
            # Start capture thread
            self.capture_thread = threading.Thread(target=self._capture_loop)
            self.capture_thread.daemon = True
            self.capture_thread.start()
            
            # Start processing thread
            self.process_thread = threading.Thread(target=self._process_loop)
            self.process_thread.daemon = True
            self.process_thread.start()
            
            # Start publishing thread if ROS node exists
            if self.node:
                self.publish_thread = threading.Thread(target=self._publish_loop)
                self.publish_thread.daemon = True
                self.publish_thread.start()
    
    def stop(self):
        """Stop the frame grabber threads"""
        with self.frame_lock:
            self.running = False
            self.current_frame = None
            self.processed_frame = None
            self.current_faces = []
        
        # Wait for threads to finish
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join()
        
        if self.process_thread and self.process_thread.is_alive():
            self.process_thread.join()
            
        if self.publish_thread and self.publish_thread.is_alive():
            self.publish_thread.join()
        
        # Release camera if it's open
        if self.camera and self.camera.isOpened():
            self.camera.release()
            self.camera = None
    
    def set_quality(self, high_quality):
        """Toggle between low resolution and high resolution with optimal settings"""
        if high_quality:
            self.frame_width = 1280
            self.frame_height = 720
            self.target_fps = 24  # Lower FPS for higher resolution
        else:
            self.frame_width = 640
            self.frame_height = 480
            self.target_fps = 30  # Higher FPS for lower resolution
        
        # Update camera properties
        self.camera_props.update({
            cv2.CAP_PROP_FRAME_WIDTH: self.frame_width,
            cv2.CAP_PROP_FRAME_HEIGHT: self.frame_height,
            cv2.CAP_PROP_FPS: self.target_fps
        })
        
        if self.camera and self.camera.isOpened():
            # Apply new settings
            for prop, value in self.camera_props.items():
                try:
                    self.camera.set(prop, value)
                except:
                    pass
            
            # Verify new settings
            actual_width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = self.camera.get(cv2.CAP_PROP_FPS)
            
            print(f"Quality changed to: {actual_width}x{actual_height} @ {actual_fps:.1f} FPS")
            
            # Update UI with blank frame of new size
            self.frame_ready.emit(np.zeros((self.frame_height, self.frame_width, 3), dtype=np.uint8))
    
    def toggle_face_detection(self, enable):
        """Enable or disable face detection"""
        with self.lock:
            self.enable_face_detection = enable
            if enable and self.face_net is None:
                self.init_face_detector()
            
            # Reset face tracking when toggling
            self.prev_faces = []
    
    def detect_faces_dnn(self, frame):
        """Detect faces using OpenCV's DNN-based face detector"""
        if self.face_net is None:
            return []
        
        # Get frame dimensions
        h, w = frame.shape[:2]
        
        # Prepare input blob for the network
        blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300), [104, 117, 123], False, False)
        self.face_net.setInput(blob)
        
        # Run forward pass
        detections = self.face_net.forward()
        
        # Parse detections
        faces = []
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > self.face_confidence_threshold:
                # Get face bounding box
                x1 = int(detections[0, 0, i, 3] * w)
                y1 = int(detections[0, 0, i, 4] * h)
                x2 = int(detections[0, 0, i, 5] * w)
                y2 = int(detections[0, 0, i, 6] * h)
                
                # Make sure the coordinates are within the frame
                x1 = max(0, min(x1, w-1))
                y1 = max(0, min(y1, h-1))
                x2 = max(0, min(x2, w-1))
                y2 = max(0, min(y2, h-1))
                
                if x2 > x1 and y2 > y1:  # Valid face
                    faces.append({
                        'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
                        'center_x': (x1 + x2) // 2,
                        'center_y': (y1 + y2) // 2,
                        'radius': max((x2 - x1), (y2 - y1)) // 2,
                        'confidence': confidence
                    })
        
        return faces
    
    def smooth_face_detections(self, faces):
        """Apply temporal smoothing to face detections to reduce flickering"""
        if not faces:
            # If no faces detected in current frame but we have previous faces,
            # decay them but keep showing them for a while
            if self.prev_faces:
                # Slowly reduce confidence of previous faces
                for face in self.prev_faces:
                    face['confidence'] *= 0.8  # Decay factor
                
                # Remove faces with very low confidence
                self.prev_faces = [f for f in self.prev_faces if f['confidence'] > 0.2]
                return self.prev_faces
            return []
        
        # If we have new faces, smoothly transition to them
        if not self.prev_faces:
            # First detection, just use it
            self.prev_faces = faces
            return faces
        
        # Try to match new faces with previous faces
        new_faces = []
        for new_face in faces:
            # Find closest previous face
            best_match = None
            min_distance = float('inf')
            
            for i, prev_face in enumerate(self.prev_faces):
                # Calculate distance between centers
                dx = new_face['center_x'] - prev_face['center_x']
                dy = new_face['center_y'] - prev_face['center_y']
                distance = (dx*dx + dy*dy) ** 0.5
                
                if distance < min_distance:
                    min_distance = distance
                    best_match = i
            
            # If we found a close enough match, smooth the transition
            if best_match is not None and min_distance < 100:  # Threshold distance
                prev_face = self.prev_faces[best_match]
                
                # Smooth position and size
                smoothed_face = {
                    'center_x': int(self.smoothing_factor * prev_face['center_x'] + 
                                    (1 - self.smoothing_factor) * new_face['center_x']),
                    'center_y': int(self.smoothing_factor * prev_face['center_y'] + 
                                    (1 - self.smoothing_factor) * new_face['center_y']),
                    'radius': int(self.smoothing_factor * prev_face['radius'] + 
                                 (1 - self.smoothing_factor) * new_face['radius']),
                    'confidence': new_face['confidence']
                }
                
                # Calculate new bounding box from smoothed center and radius
                r = smoothed_face['radius']
                cx = smoothed_face['center_x']
                cy = smoothed_face['center_y']
                smoothed_face['x1'] = cx - r
                smoothed_face['y1'] = cy - r
                smoothed_face['x2'] = cx + r
                smoothed_face['y2'] = cy + r
                
                new_faces.append(smoothed_face)
                # Remove the matched face to prevent double matching
                self.prev_faces.pop(best_match)
            else:
                # No match, add as new face
                new_faces.append(new_face)
        
        # Add any remaining unmatched previous faces with decayed confidence
        for face in self.prev_faces:
            face['confidence'] *= 0.5  # Faster decay for unmatched faces
            if face['confidence'] > 0.3:  # Only keep if still confident enough
                new_faces.append(face)
        
        # Update previous faces for next frame
        self.prev_faces = new_faces
        return new_faces
    
    def draw_face_circles(self, frame, faces):
        """Draw transparent circles over detected faces with IDs"""
        if not faces:
            return frame
        
        # Create an overlay for transparency
        overlay = frame.copy()
        
        # Draw circles and face data on overlay
        for i, face in enumerate(faces):
            # Get face ID if available
            face_id = face.get('id', 'Unknown')
            
            # Choose color based on face ID
            if face_id != 'Unknown':
                # Use different color for recognized faces
                color = (0, 200, 255)  # Orange for recognized faces
            else:
                color = (0, 255, 0)  # Green for detected faces
            
            # Draw circle on overlay
            cv2.circle(overlay, 
                      (face['center_x'], face['center_y']), 
                      face['radius'], 
                      color, 
                      -1)
            
            # Draw rectangle around face
            cv2.rectangle(frame, (face['x1'], face['y1']), (face['x2'], face['y2']), color, 2)
            
            # Display face ID and confidence
            face_conf = face.get('confidence', 0.0)
            id_text = f"ID: {face_id}" if face_id != 'Unknown' else "Unknown"
            conf_text = f"Conf: {face_conf:.2f}"
            
            cv2.putText(frame, id_text, (face['x1'], face['y1'] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            cv2.putText(frame, conf_text, (face['x1'], face['y1'] + face['height'] if 'height' in face else (face['y2']-face['y1']) + 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # Blend the overlay with the original frame for transparency
        alpha = 0.3  # Transparency factor
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        
        # Add indicator text if faces detected
        cv2.putText(frame, f"Faces: {len(faces)}", (10, 70), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Display number of recognized faces
        recog_count = len([f for f in faces if f.get('id', 'Unknown') != 'Unknown'])
        if recog_count > 0:
            cv2.putText(frame, f"Recognized: {recog_count}/{len(faces)}", (10, 110), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        return frame
    
    def _capture_loop(self):
        """Main capture loop for camera frames"""
        try:
            # Try different backends if the default doesn't work
            backends_to_try = [
                (cv2.CAP_V4L2, "V4L2"),        # Linux V4L2
                (cv2.CAP_GSTREAMER, "GStreamer"),  # GStreamer
                (cv2.CAP_ANY, "Auto-detect")    # Let OpenCV choose
            ]
            
            # Start with the specified backend
            if self.backend != cv2.CAP_ANY:
                backends_to_try.insert(0, (self.backend, "User selected"))
            
            success = False
            error_msg = ""
            
            # Try each backend until one works
            for backend, backend_name in backends_to_try:
                try:
                    if backend == cv2.CAP_ANY:
                        self.camera = cv2.VideoCapture(self.camera_index)
                    else:
                        self.camera = cv2.VideoCapture(self.camera_index, backend)
                    
                    if not self.camera.isOpened():
                        error_msg = f"Could not open camera {self.camera_index} with {backend_name} backend"
                        continue
                    
                    success = True
                    print(f"Successfully opened camera with {backend_name} backend")
                    break
                except Exception as e:
                    error_msg = f"Error opening camera with {backend_name} backend: {str(e)}"
                    continue
            
            if not success:
                self.error.emit(f"Failed to open camera: {error_msg}")
                return
            
            # Configure camera with optimal settings
            for prop, value in self.camera_props.items():
                try:
                    self.camera.set(prop, value)
                except:
                    pass  # Skip unsupported properties
            
            # Verify and adjust settings
            actual_width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = self.camera.get(cv2.CAP_PROP_FPS)
            
            print(f"Camera configured with: {actual_width}x{actual_height} @ {actual_fps:.1f} FPS")
            
            # Warm up the camera
            for _ in range(5):
                self.camera.read()
            
            # Read a test frame to check actual size
            ret, frame = self.camera.read()
            if ret:
                frame_h, frame_w = frame.shape[:2]
                if frame_w != actual_width or frame_h != actual_height:
                    print(f"Warning: Actual frame size ({frame_w}x{frame_h}) differs from requested ({actual_width}x{actual_height})")
                    self.frame_width = frame_w
                    self.frame_height = frame_h
            
            # Main capture loop
            while self.running:
                ret, frame = self.camera.read()
                if not ret:
                    continue
                
                # Flip frame horizontally
                frame = cv2.flip(frame, 1)
                
                # Update shared frame buffer
                with self.frame_lock:
                    self.current_frame = frame
                    self.frame_timestamp = time.time()
                        
        except Exception as e:
            self.error.emit(f"Error in capture thread: {str(e)}")
        finally:
            if self.camera and self.camera.isOpened():
                self.camera.release()
                self.camera = None
    
    def _process_loop(self):
        """Process frames from the queue"""
        try:
            frame_count = 0
            start_time = time.time()
            fps = 0
            face_detection_interval = 3  # Reduced face detection frequency
            frame_index = 0
            
            while self.running:
                # Get latest frame
                with self.frame_lock:
                    frame = self.current_frame
                    frame_time = self.frame_timestamp
                    if frame is None:
                        continue
                    
                    # Make a copy to avoid holding the lock
                    frame = frame.copy()
                
                # Skip if frame is too old (> 100ms)
                if time.time() - frame_time > 0.1:
                    continue
                
                # Adaptive face detection with time budgeting
                self.detection_frame_counter += 1
                current_time = time.time()
                
                # Check if we should attempt face detection
                should_detect = (
                    self.enable_face_detection and
                    self.detection_frame_counter >= self.detection_skip_frames and
                    current_time - self.last_detection_time >= self.min_detection_interval
                )
                
                if should_detect:
                    detection_start = time.time()
                    faces = self.detect_faces_dnn(frame)
                    detection_time = time.time() - detection_start
                    
                    # If detection took too long, increase skip frames
                    if detection_time > self.max_detection_time:
                        self.detection_skip_frames = min(10, self.detection_skip_frames + 1)
                    else:
                        # If detection was fast, gradually decrease skip frames
                        self.detection_skip_frames = max(3, self.detection_skip_frames - 1)
                    
                    self.current_faces = faces  # No smoothing for better latency
                    self.last_detection_time = current_time
                    self.detection_frame_counter = 0
                    
                    # Check if recognition data is stale
                    if current_time - self.last_recognition_time > self.recognition_timeout:
                        self.face_ids = {}
                    
                    # Add face IDs
                    for i, face in enumerate(faces):
                        if i in self.face_ids:
                            face['id'] = self.face_ids[i]['id']
                        else:
                            face['id'] = 'Unknown'
                
                # Draw faces if available
                if self.current_faces:
                    frame = self.draw_face_circles(frame, self.current_faces)
                
                # Update FPS counter
                frame_count += 1
                if frame_count >= 30:  # Increased sample size for smoother FPS
                    current_time = time.time()
                    elapsed = current_time - start_time
                    fps = frame_count / elapsed if elapsed > 0 else 0
                    frame_count = 0
                    start_time = current_time
                
                # Draw FPS
                cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                
                # Update processed frame
                with self.frame_lock:
                    self.processed_frame = frame
                
                # Emit frame for UI with rate limiting
                current_time = time.time()
                if current_time - self.last_ui_update >= self.min_ui_interval:
                    self.frame_ready.emit(frame)
                    self.last_ui_update = current_time
        except Exception as e:
            self.error.emit(f"Error in process thread: {str(e)}")
    
    def _publish_loop(self):
        """Handle ROS publishing at controlled rate"""
        try:
            while self.running:
                current_time = time.time()
                
                # Check if enough time has passed since last publish
                if current_time - self.last_publish_time >= self.min_publish_interval:
                    # Get latest processed frame
                    with self.frame_lock:
                        frame = self.processed_frame
                        faces = self.current_faces[:] if self.current_faces else []
                    
                    if frame is not None:
                        # Publish frame and face data
                        self.publish_frame(frame)
                        # Always publish face position, even when no faces are detected
                        # This is used so that we can re-center the eyes -- zero them in.
                        # self.publish_face_position(faces)
                        # Always publish face data, even when no faces are detected
                        self.publish_face_position_v2(faces)
                        self.publish_face_data(faces)
                        # Only publish face images when faces are actually detected
                        if faces:
                            self.publish_face_images(frame, faces)
                        
                        self.last_publish_time = current_time
        except Exception as e:
            self.error.emit(f"Error in publish thread: {str(e)}")

class CameraViewer(QMainWindow):
    def __init__(self, node):
        super().__init__()
        self.node = node
        self.frame_grabber = FrameGrabber(node)
        self.frame_grabber.frame_ready.connect(self.process_frame)
        self.frame_grabber.error.connect(self.handle_camera_error)
        self.high_quality = False
        self.face_detection_enabled = True
        self.initUI()
        self.check_video_devices()
        self.scan_cameras()
        
    def initUI(self):
        self.setWindowTitle('Coffee Camera - Webcam Viewer')
        self.setGeometry(100, 100, 800, 600)
        
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        # Camera feed display
        self.image_label = QLabel("No camera feed available")
        self.image_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.image_label)
        
        # Controls layout
        controls_layout = QHBoxLayout()  # Horizontal layout
        
        # Camera selection
        camera_selection_layout = QVBoxLayout()
        camera_label = QLabel("Camera:")
        self.camera_combo = QComboBox()
        self.camera_combo.currentIndexChanged.connect(self.change_camera)
        
        camera_selection_layout.addWidget(camera_label)
        camera_selection_layout.addWidget(self.camera_combo)
        
        # Refresh camera list button
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.scan_cameras)
        camera_selection_layout.addWidget(self.refresh_button)
        
        controls_layout.addLayout(camera_selection_layout)
        
        # Quality controls
        quality_layout = QVBoxLayout()
        quality_label = QLabel("Quality:")
        
        self.quality_checkbox = QCheckBox("High Quality (1080p)")
        self.quality_checkbox.setChecked(self.high_quality)
        self.quality_checkbox.stateChanged.connect(self.toggle_quality)
        
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(self.quality_checkbox)
        
        # Face detection toggle
        self.face_detection_checkbox = QCheckBox("Face Detection")
        self.face_detection_checkbox.setChecked(self.face_detection_enabled)
        self.face_detection_checkbox.stateChanged.connect(self.toggle_face_detection)
        quality_layout.addWidget(self.face_detection_checkbox)
        
        controls_layout.addLayout(quality_layout)
        
        # Camera diagnostics button
        self.diagnostics_button = QPushButton("Camera Diagnostics")
        self.diagnostics_button.clicked.connect(self.show_diagnostics)
        controls_layout.addWidget(self.diagnostics_button)
        
        # Add some spacer for better layout
        controls_layout.addStretch(1)
        
        main_layout.addLayout(controls_layout)
        
        # Pre-allocate buffers for better performance
        self.qt_image = None
        self.pixmap = None
    
    def toggle_face_detection(self, state):
        """Toggle face detection on/off"""
        self.face_detection_enabled = bool(state)
        self.node.get_logger().info(f"Face detection {'enabled' if self.face_detection_enabled else 'disabled'}")
        self.frame_grabber.toggle_face_detection(self.face_detection_enabled)
    
    def check_video_devices(self):
        """Check what video devices are available in the system"""
        if not os.path.exists('/dev'):
            self.node.get_logger().warn("No /dev directory found - not a Linux system?")
            return
        
        video_devices = []
        for device in os.listdir('/dev'):
            if device.startswith('video'):
                full_path = f"/dev/{device}"
                if os.access(full_path, os.R_OK):
                    video_devices.append(full_path)
        
        if not video_devices:
            self.node.get_logger().warn("No video devices found in /dev/")
            return
        
        self.node.get_logger().info(f"Found video devices: {', '.join(video_devices)}")
        
        # Check if any are in use
        try:
            output = subprocess.check_output(['fuser'] + video_devices, stderr=subprocess.STDOUT, text=True)
            self.node.get_logger().warn(f"Some video devices are in use: {output}")
        except subprocess.CalledProcessError:
            # No devices in use (fuser returns non-zero if no processes found)
            self.node.get_logger().info("No video devices appear to be in use")
        except Exception as e:
            # Some other error with fuser
            self.node.get_logger().warn(f"Error checking device usage: {e}")
    
    def show_diagnostics(self):
        """Show camera diagnostics information"""
        info = "Camera Diagnostics:\n\n"
        
        # Check for video devices
        video_devices = []
        for device in os.listdir('/dev'):
            if device.startswith('video'):
                full_path = f"/dev/{device}"
                access = os.access(full_path, os.R_OK)
                video_devices.append(f"{full_path} (Readable: {access})")
        
        if video_devices:
            info += "Video Devices:\n" + "\n".join(video_devices) + "\n\n"
        else:
            info += "No video devices found!\n\n"
        
        # OpenCV version
        info += f"OpenCV Version: {cv2.__version__}\n"
        
        # Face detection status
        info += f"Face Detection: {'Enabled' if self.face_detection_enabled else 'Disabled'}\n"
        info += f"Using OpenCV DNN-based face detector\n\n"
        
        # Check which OpenCV backends are available
        info += "Available OpenCV Backends:\n"
        backends = [
            (cv2.CAP_V4L2, "Linux V4L2"),
            (cv2.CAP_GSTREAMER, "GStreamer"),
            (cv2.CAP_FFMPEG, "FFMPEG"),
            (cv2.CAP_IMAGES, "Images"),
            (cv2.CAP_DSHOW, "DirectShow (Windows)"),
            (cv2.CAP_ANY, "Auto-detect")
        ]
        
        for backend_id, name in backends:
            info += f"- {name}\n"
        
        # Show message box with diagnostic info
        QMessageBox.information(self, "Camera Diagnostics", info)
    
    def scan_cameras(self):
        """Scan for available cameras"""
        self.camera_combo.clear()
        
        # Stop current camera if running
        self.frame_grabber.stop()
        
        # Check for cameras using direct V4L2 access first
        self.node.get_logger().info("Scanning for cameras...")
        available_cameras = []
        
        # In Linux, we can check directly which devices are video capture devices
        if os.path.exists('/dev'):
            for i in range(10):
                device_path = f"/dev/video{i}"
                if os.path.exists(device_path) and os.access(device_path, os.R_OK):
                    try:
                        # Try to open the camera directly with V4L2
                        cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
                        if cap.isOpened():
                            # It's a valid camera
                            camera_name = f"Camera {i} ({device_path})"
                            available_cameras.append((i, camera_name))
                            cap.release()
                        else:
                            self.node.get_logger().info(f"Device {device_path} exists but couldn't be opened as a camera")
                    except Exception as e:
                        self.node.get_logger().warn(f"Error checking {device_path}: {e}")
        
        # Fallback to generic scanning
        if not available_cameras:
            self.node.get_logger().info("Direct scan failed, trying generic approach...")
            for i in range(2):  # Only try the first two indices to avoid lengthy timeouts
                try:
                    cap = cv2.VideoCapture(i)
                    if cap.isOpened():
                        camera_name = f"Camera {i}"
                        available_cameras.append((i, camera_name))
                        cap.release()
                except Exception as e:
                    self.node.get_logger().warn(f"Error scanning camera {i}: {e}")
        
        # Add available cameras to combo box
        for idx, name in available_cameras:
            self.camera_combo.addItem(name, idx)
            
        if not available_cameras:
            self.node.get_logger().error("No cameras found!")
            self.image_label.setText("No cameras found! Check connections and permissions.")
            return
            
        # If any camera is available, start the first one
        if self.camera_combo.count() > 0:
            self.change_camera(self.camera_combo.currentIndex())
    
    def change_camera(self, index):
        """Change to a different camera"""
        if index >= 0:
            camera_index = self.camera_combo.itemData(index)
            self.node.get_logger().info(f"Changing to camera index {camera_index}")
            self.frame_grabber.stop()
            self.frame_grabber.set_quality(self.high_quality)
            self.frame_grabber.toggle_face_detection(self.face_detection_enabled)
            # Try with V4L2 backend specifically on Linux
            if os.name == 'posix':
                self.frame_grabber.start(camera_index, cv2.CAP_V4L2)
            else:
                self.frame_grabber.start(camera_index)
    
    def toggle_quality(self, state):
        """Toggle between high and low quality modes"""
        self.high_quality = bool(state)
        self.node.get_logger().info(f"Quality set to {'high' if self.high_quality else 'standard'}")
        self.frame_grabber.set_quality(self.high_quality)
    
    def handle_camera_error(self, error_msg):
        """Handle errors from the camera thread"""
        self.node.get_logger().error(f"Camera error: {error_msg}")
        self.image_label.setText(f"Camera error: {error_msg}\nTry refreshing or check permissions.")
    
    def process_frame(self, frame):
        """Process and display a camera frame - optimized for speed"""
        if frame is None:
            return
            
        # Convert colors - BGR to RGB (optimized)
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Scale image to fit label
        label_width = self.image_label.width()
        label_height = self.image_label.height()
        
        if label_width > 0 and label_height > 0:
            h, w = rgb_image.shape[:2]
            
            # Calculate scale factor to fit in label while preserving aspect ratio
            scale_w = label_width / w
            scale_h = label_height / h
            scale = min(scale_w, scale_h)
            
            # Always scale to fit the label
            new_size = (int(w * scale), int(h * scale))
            # Use INTER_LINEAR for better quality when upscaling, INTER_AREA for downscaling
            interpolation = cv2.INTER_LINEAR if scale > 1.0 else cv2.INTER_AREA
            rgb_image = cv2.resize(rgb_image, new_size, interpolation=interpolation)
        
        # Convert to QImage and display (reusing objects when possible)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        
        # Convert to QImage efficiently
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        self.image_label.setPixmap(pixmap)
    
    def closeEvent(self, event):
        """Clean up when window is closed"""
        self.frame_grabber.stop()
        event.accept()


class CameraNode(Node):
    def __init__(self, executor):
        # Initialize node
        super().__init__('coffee_camera_node')
        self.get_logger().info('Camera node is starting...')
        
        # Store executor
        self.executor = executor
        self.executor.add_node(self)
        
        # Start the UI
        app = QApplication(sys.argv)
        self.ui = CameraViewer(self)
        self.ui.show()
        
        # Start a background thread for ROS spinning
        self.spinning = True
        self.ros_thread = threading.Thread(target=self.spin_thread)
        self.ros_thread.daemon = True
        self.ros_thread.start()
        
        # # Add parameters for mapping
        # self.declare_parameter('invert_x', False)  # Default FALSE for correct eye movement
        # self.declare_parameter('invert_y', False)  # Default FALSE for correct eye movement
        # self.declare_parameter('eye_range', 3.0)   # Max range for eye movement (-3.0 to 3.0)

        # # Get parameters
        # self.invert_x = self.get_parameter('invert_x').value
        # self.invert_y = self.get_parameter('invert_y').value
        # self.eye_range = self.get_parameter('eye_range').value

        self.invert_x = False
        self.invert_y = False
        # self.eye_range = 3.0
        self.eye_range = 1.0 # The constraint for the values of the eye movement in the UI

        try:
            # Start Qt event loop
            app.exec_()
        except KeyboardInterrupt:
            self.spinning = False
            self.destroy_node()
    
    def spin_thread(self):
        """Background thread for ROS spinning"""
        while self.spinning:
            self.executor.spin_once(timeout_sec=0.1)
        self.destroy_node()
    
    def destroy_node(self):
        """Clean shutdown"""
        self.get_logger().info('Shutting down camera node')
        self.spinning = False
        
        # Stop the frame grabber
        if hasattr(self, 'ui') and hasattr(self.ui, 'frame_grabber'):
            # Stop frame grabber
            try:
                self.ui.frame_grabber.stop()
                self.get_logger().info('Frame grabber stopped')
            except Exception as e:
                self.get_logger().error(f'Error stopping frame grabber: {e}')
        
        # Clean up ROS resources
        super().destroy_node()


def main(args=None):
    try:
        # Initialize ROS2
        rclpy.init(args=args)
        
        # Create executor first
        executor = rclpy.executors.SingleThreadedExecutor()
        
        # Create and run the node
        node = CameraNode(executor)
    except Exception as e:
        print(f"Error in camera node: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == '__main__':
    main()