#!/usr/bin/env python3

import sys
import math
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, 
                            QVBoxLayout, QHBoxLayout, QLabel,
                            QPushButton, QCheckBox)
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QBrush
from PyQt5.QtCore import Qt, QPoint, QRect, QTimer

# Import Dynamixel SDK interfaces
from dynamixel_sdk_custom_interfaces.msg import SetPosition
from dynamixel_sdk_custom_interfaces.srv import GetPosition

# Default settings from the read_write_node example
DXL_PAN_ID = 1   # Pan motor ID
DXL_TILT_ID = 9  # Tilt motor ID

# Constants for position conversion
# Dynamixel position range is typically 0-4095 for a full 360 degrees
# In the UI we use 0-360 degrees, so we need conversion
MIN_POSITION = 0
MAX_POSITION = 4095
POSITION_RANGE = MAX_POSITION - MIN_POSITION
DEGREES_PER_POSITION = 360.0 / POSITION_RANGE
POSITIONS_PER_DEGREE = POSITION_RANGE / 360.0

# Default angles for motors
DEFAULT_PAN_ANGLE = 180   # Pan motor default position (90 degrees)
DEFAULT_TILT_ANGLE = 180  # Tilt motor default position (180 degrees)

class MotorControlWidget(QWidget):
    def __init__(self, motor_id, motor_name="Motor", default_angle=0, parent=None):
        super().__init__(parent)
        self.motor_id = motor_id
        self.motor_name = motor_name
        self.default_angle = default_angle
        self.angle = default_angle  # Angle in degrees
        self.position = int(default_angle * POSITIONS_PER_DEGREE)  # Position in Dynamixel units
        self.radius = 100
        # Center the circle in its widget - will be calculated in paintEvent
        self.dragging = False
        self.torque_enabled = False
        self.motor_connected = False  # Track motor connection status
        self.setMinimumSize(2 * (self.radius + 60), 2 * (self.radius + 160))  # Increased height for labels and controls
        
        # Card styling with shadow effect
        self.setStyleSheet("""
            MotorControlWidget {
                background-color: #ffffff;
                border-radius: 15px;
                border: 1px solid #e1e8ed;
                margin: 10px;
            }
            MotorControlWidget:hover {
                border: 1px solid #3498db;
                box-shadow: 0 4px 12px rgba(52, 152, 219, 0.1);
            }
        """)
        
        # Create layout for the card content
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)  # Card padding
        self.main_layout.setSpacing(15)  # Space between card sections
        
        # Card header with motor name and ID
        header_layout = QHBoxLayout()
        
        # Motor name
        self.name_label = QLabel(self.motor_name)
        self.name_label.setFont(QFont('Segoe UI', 16, QFont.Bold))
        self.name_label.setStyleSheet("color: #2c3e50; margin-bottom: 5px;")
        header_layout.addWidget(self.name_label)
        
        # Motor ID badge
        self.id_badge = QLabel(f"ID: {self.motor_id}")
        self.id_badge.setFont(QFont('Segoe UI', 10, QFont.Medium))
        self.id_badge.setStyleSheet("""
            QLabel {
                background-color: #3498db;
                color: white;
                border-radius: 10px;
                padding: 4px 8px;
                max-width: 50px;
            }
        """)
        self.id_badge.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(self.id_badge)
        
        self.main_layout.addLayout(header_layout)
        
        # Widget for drawing the circle (just the circle, no text)
        self.circle_widget = QWidget()
        self.circle_widget.setMinimumSize(2 * (self.radius + 20), 2 * (self.radius + 20))  # Just for the circle
        self.circle_widget.paintEvent = self.paintCircleWidget
        self.circle_widget.mousePressEvent = self.circleMousePressEvent
        self.circle_widget.mouseMoveEvent = self.circleMouseMoveEvent
        self.circle_widget.mouseReleaseEvent = self.circleMouseReleaseEvent
        self.main_layout.addWidget(self.circle_widget)
        
        # Separate labels for angle and status information
        self.angle_label = QLabel(f"{self.angle:.1f}°")
        self.angle_label.setAlignment(Qt.AlignCenter)
        self.angle_label.setFont(QFont('Segoe UI', 18, QFont.Bold))  # Larger and bolder
        self.angle_label.setStyleSheet("color: #2c3e50; margin: 8px 0px 4px 0px;")  # Better spacing
        self.main_layout.addWidget(self.angle_label)
        
        self.status_label = QLabel("DISCONNECTED")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont('Segoe UI', 11, QFont.Medium))  # Slightly larger
        self.status_label.setStyleSheet("""
            QLabel {
                color: #e74c3c; 
                background-color: #ffeaa7;
                border: 1px solid #fdcb6e;
                border-radius: 12px;
                padding: 4px 12px;
                margin: 4px 20px 8px 20px;
            }
        """)  # Status badge styling
        self.main_layout.addWidget(self.status_label)
        
        # Initialize display with current state
        self.update_display()
        
        # Controls section with better styling
        controls_container = QWidget()
        controls_container.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-radius: 8px;
                padding: 10px;
                margin-top: 10px;
            }
        """)
        
        controls_layout = QVBoxLayout(controls_container)  # Changed to vertical for better card layout
        controls_layout.setSpacing(10)
        
        # Torque toggle with modern styling
        self.torque_checkbox = QCheckBox("Enable Torque")
        self.torque_checkbox.setChecked(self.torque_enabled)
        self.torque_checkbox.setEnabled(False)  # Disabled until motor connects
        self.torque_checkbox.setFont(QFont('Segoe UI', 11))
        self.torque_checkbox.setStyleSheet("""
            QCheckBox {
                color: #2c3e50;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 9px;
                border: 2px solid #bdc3c7;
            }
            QCheckBox::indicator:checked {
                background-color: #27ae60;
                border: 2px solid #27ae60;
            }
            QCheckBox::indicator:disabled {
                background-color: #ecf0f1;
                border: 2px solid #bdc3c7;
            }
        """)
        self.torque_checkbox.stateChanged.connect(self.toggleTorque)
        controls_layout.addWidget(self.torque_checkbox)
        
        # Reset position button with modern styling
        self.reset_button = QPushButton("↻ Reset Position")
        self.reset_button.setEnabled(False)  # Disabled until motor connects
        self.reset_button.setFont(QFont('Segoe UI', 11))
        self.reset_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        self.reset_button.clicked.connect(self.resetPosition)
        controls_layout.addWidget(self.reset_button)
        
        self.main_layout.addWidget(controls_container)
        
        # Conversion helpers
        self.rosnode = None  # Will be set by parent

    def set_ros_node(self, node):
        self.rosnode = node
    
    def update_display(self):
        """Update all visual elements (circle, angle, status)"""
        # Update circle drawing
        self.circle_widget.update()
        
        # Update angle label
        self.angle_label.setText(f"{self.angle:.1f}°")
        
        # Update status label with badge styling
        if self.motor_connected:
            self.status_label.setText(f"Position: {self.position}")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #27ae60; 
                    background-color: #d5f4e6;
                    border: 1px solid #27ae60;
                    border-radius: 12px;
                    padding: 4px 12px;
                    margin: 4px 20px 8px 20px;
                    font-weight: 500;
                }
            """)
        else:
            self.status_label.setText("DISCONNECTED")
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #d63031; 
                    background-color: #ffeaa7;
                    border: 1px solid #fdcb6e;
                    border-radius: 12px;
                    padding: 4px 12px;
                    margin: 4px 20px 8px 20px;
                    font-weight: 500;
                }
            """)

    def paintCircleWidget(self, event):
        painter = QPainter(self.circle_widget)
        painter.setRenderHint(QPainter.Antialiasing)

        # Calculate center position to center the circle in the widget
        widget_width = self.circle_widget.width()
        widget_height = self.circle_widget.height()
        
        # Center the circle in the available space
        circle_x = (widget_width - 2 * self.radius) // 2
        circle_y = (widget_height - 2 * self.radius) // 2
        
        # Update circle center for mouse interactions
        self.circle_center = QPoint(circle_x + self.radius, circle_y + self.radius)

        # Draw circle with connection status
        if not self.motor_connected:
            painter.setPen(QPen(Qt.red, 3))  # Red border when disconnected
            painter.setBrush(QBrush(QColor(255, 220, 220)))  # Light red when disconnected
        elif self.torque_enabled:
            painter.setPen(QPen(Qt.black, 2))
            painter.setBrush(QBrush(QColor(230, 230, 255)))  # Light blue when torque enabled
        else:
            painter.setPen(QPen(Qt.black, 2))
            painter.setBrush(QBrush(QColor(240, 240, 240)))  # Light gray when disabled
        
        circle_rect = QRect(circle_x, circle_y, 2 * self.radius, 2 * self.radius)
        painter.drawEllipse(circle_rect)
        
        # Draw line from center to edge (like a clock hand)  
        if self.torque_enabled:
            painter.setPen(QPen(Qt.red, 3))
        else:
            painter.setPen(QPen(Qt.gray, 3))
        line_end_x = self.circle_center.x() + self.radius * math.cos(math.radians(self.angle - 90))
        line_end_y = self.circle_center.y() + self.radius * math.sin(math.radians(self.angle - 90))
        painter.drawLine(self.circle_center, QPoint(int(line_end_x), int(line_end_y)))

        # Draw a small circle at the center
        painter.setPen(QPen(Qt.black, 1))
        painter.setBrush(QBrush(Qt.black))
        painter.drawEllipse(self.circle_center, 5, 5)

    def circleMousePressEvent(self, event):
        # Check if the click is within the circle
        dx = event.x() - self.circle_center.x()
        dy = event.y() - self.circle_center.y()
        dist = math.sqrt(dx*dx + dy*dy)
        
        if dist <= self.radius and self.torque_enabled:
            self.dragging = True
            self.updateAngle(event.x(), event.y())

    def circleMouseMoveEvent(self, event):
        if self.dragging and self.torque_enabled:
            self.updateAngle(event.x(), event.y())

    def circleMouseReleaseEvent(self, event):
        self.dragging = False
        if self.torque_enabled and self.rosnode:
            # Send final position to motor when releasing
            self.send_position_to_motor()

    def updateAngle(self, x, y):
        # Calculate angle from center to mouse point
        dx = x - self.circle_center.x()
        dy = y - self.circle_center.y()
        angle = math.degrees(math.atan2(dy, dx)) + 90
        
        # Normalize to 0-360 range
        self.angle = angle % 360
        
        # Convert angle to Dynamixel position
        self.position = int(self.angle * POSITIONS_PER_DEGREE)
        
        # Update display
        self.update_display()
        
        # Only send to motor if dragging stopped (to reduce traffic)
        # Full position will be sent when mouse is released

    def send_position_to_motor(self):
        if self.rosnode and self.torque_enabled:
            msg = SetPosition()
            msg.id = self.motor_id
            msg.position = self.position
            self.rosnode.publisher.publish(msg)
            self.rosnode.get_logger().info(f"{self.motor_name} (ID: {self.motor_id}) position set to: {self.position}")
    
    def toggleTorque(self, state):
        self.torque_enabled = bool(state)
        self.update_display()
        if self.rosnode:
            self.rosnode.get_logger().info(f"{self.motor_name} (ID: {self.motor_id}) torque {'enabled' if self.torque_enabled else 'disabled'}")
            # In a real implementation, you would send torque command to motor here
            # However, the example doesn't have a direct torque toggle topic
            # You would need to add this functionality to the read_write_node
    
    def resetPosition(self):
        self.angle = self.default_angle
        self.position = int(self.default_angle * POSITIONS_PER_DEGREE)
        self.update_display()
        
        if self.rosnode and self.torque_enabled:
            self.rosnode.get_logger().info(f"{self.motor_name} (ID: {self.motor_id}) position reset to {self.default_angle}°")
            self.send_position_to_motor()
    
    def set_position_from_motor(self, position):
        # Update UI from motor position
        self.position = position
        self.angle = (position * DEGREES_PER_POSITION) % 360
        self.motor_connected = True  # Mark motor as connected when we receive position
        # Enable controls when motor is connected
        self.torque_checkbox.setEnabled(True)
        self.reset_button.setEnabled(True)
        self.update_display()
    
    def set_motor_disconnected(self):
        """Mark motor as disconnected and disable controls"""
        self.motor_connected = False
        self.torque_checkbox.setEnabled(False)
        self.reset_button.setEnabled(False)
        self.update_display()


class DynamixelControlUI(QMainWindow):
    def __init__(self, node):
        super().__init__()
        self.node = node
        self.service_connected = False  # Track overall service status
        self.initUI()
        
        # Initial motor position read
        self.read_motor_positions()
        
    def initUI(self):
        self.setWindowTitle('Dynamixel Motor Control')
        self.setGeometry(100, 100, 800, 650)  # Larger window for card layout
        
        # Main widget and layout with better spacing
        main_widget = QWidget()
        main_widget.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                font-family: 'Segoe UI', 'Arial', sans-serif;
            }
        """)
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(20)  # Better spacing between sections
        main_layout.setContentsMargins(30, 20, 30, 20)  # Consistent margins
        
        # Title label with modern styling
        title_label = QLabel('Dynamixel Motor Control')
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont('Segoe UI', 24, QFont.Bold))
        title_label.setStyleSheet("""
            QLabel {
                color: #2c3e50;
                padding: 15px;
                margin-bottom: 10px;
            }
        """)
        main_layout.addWidget(title_label)
        
        # Service status indicator with card styling
        self.status_label = QLabel('Service Status: Checking connection...')
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont('Segoe UI', 12, QFont.Medium))
        self.update_service_status(False)  # Initialize as disconnected
        main_layout.addWidget(self.status_label)
        
        # Motor controls in card layout
        motors_container = QWidget()
        motors_container.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
        """)
        motors_layout = QHBoxLayout(motors_container)
        motors_layout.setSpacing(30)  # Space between motor cards
        motors_layout.setContentsMargins(0, 0, 0, 0)
        
        # Pan motor control card
        self.pan_motor = MotorControlWidget(DXL_PAN_ID, "Pan Motor", DEFAULT_PAN_ANGLE)
        self.pan_motor.set_ros_node(self.node)
        motors_layout.addWidget(self.pan_motor)
        
        # Tilt motor control card  
        self.tilt_motor = MotorControlWidget(DXL_TILT_ID, "Tilt Motor", DEFAULT_TILT_ANGLE)
        self.tilt_motor.set_ros_node(self.node)
        motors_layout.addWidget(self.tilt_motor)
        
        main_layout.addWidget(motors_container)
        
        # Help instructions with modern styling
        help_label = QLabel('💡 To control motors, run "ros2 run dynamixel_sdk_examples read_write_node" in another terminal')
        help_label.setAlignment(Qt.AlignCenter)
        help_label.setFont(QFont('Segoe UI', 11))
        help_label.setStyleSheet("""
            QLabel {
                color: #6c757d;
                background-color: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 15px 20px;
                margin: 10px 0px;
                line-height: 1.4;
            }
        """)
        main_layout.addWidget(help_label)
    
    def update_service_status(self, connected):
        """Update the service status indicator"""
        self.service_connected = connected
        if connected:
            self.status_label.setText('✓ Dynamixel Service: CONNECTED - Motors ready for control')
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #d5f4e6;
                    color: #27ae60;
                    border: 2px solid #27ae60;
                    border-radius: 10px;
                    padding: 12px 20px;
                    font-weight: 600;
                    margin: 5px;
                }
            """)
        else:
            self.status_label.setText('⚠ Dynamixel Service: DISCONNECTED - Start "read_write_node" to control motors')
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #ffeaa7;
                    color: #d63031;
                    border: 2px solid #fdcb6e;
                    border-radius: 10px;
                    padding: 12px 20px;
                    font-weight: 600;
                    margin: 5px;
                }
            """)
    
    def read_motor_positions(self):
        """Read current motor positions from the motors"""
        self.node.get_logger().info('Reading motor positions...')
        self.get_motor_position(DXL_PAN_ID, self.pan_motor)
        self.get_motor_position(DXL_TILT_ID, self.tilt_motor)
    
    def get_motor_position(self, motor_id, motor_widget):
        """Get position for a specific motor"""
        client = self.node.create_client(GetPosition, 'get_position')
        
        # Check if service is available with a short timeout (non-blocking)
        if not client.wait_for_service(timeout_sec=0.5):
            self.node.get_logger().warning(f'get_position service not available for motor ID {motor_id}. UI will show default positions.')
            # Update service status to disconnected
            self.update_service_status(False)
            # Mark this motor as disconnected
            motor_widget.set_motor_disconnected()
            # Set a timer to retry later
            self.create_retry_timer(motor_id, motor_widget)
            return
        
        request = GetPosition.Request()
        request.id = motor_id
        
        future = client.call_async(request)
        future.add_done_callback(
            lambda f: self.process_position_response(f, motor_widget)
        )
    
    def create_retry_timer(self, motor_id, motor_widget):
        """Create a timer to retry reading motor position later"""
        def retry_callback():
            self.node.get_logger().info(f'Retrying position read for motor ID {motor_id}...')
            # Cancel this timer first
            timer.cancel()
            # Then retry the position read
            self.get_motor_position(motor_id, motor_widget)
        
        # Create a one-shot timer to retry after 5 seconds
        timer = self.node.create_timer(5.0, retry_callback)
    
    def process_position_response(self, future, motor_widget):
        """Process the response from the get_position service"""
        try:
            response = future.result()
            self.node.get_logger().info(f'Received position {response.position} for motor ID {motor_widget.motor_id}')
            motor_widget.set_position_from_motor(response.position)
            # Update service status to connected when we get a successful response
            if not self.service_connected:
                self.update_service_status(True)
        except Exception as e:
            self.node.get_logger().error(f'Service call failed for motor ID {motor_widget.motor_id}: {e}')
            # Update service status to disconnected on failure
            self.update_service_status(False)
            # Mark this motor as disconnected
            motor_widget.set_motor_disconnected()
            # Retry after a delay if the service call failed
            self.create_retry_timer(motor_widget.motor_id, motor_widget)


class DynamixelUINode(Node):
    def __init__(self):
        super().__init__('dynamixel_ui_node')
        
        # Set up QoS profile
        qos = QoSProfile(depth=10)
        
        # Create publisher to send position commands
        self.publisher = self.create_publisher(
            SetPosition,
            'set_position',
            qos
        )
        
        self.get_logger().info('DynamixelUINode is running')
        
        # Start the UI
        app = QApplication(sys.argv)
        self.ui = DynamixelControlUI(self)
        self.ui.show()
        
        # Start a background thread for ROS spinning
        from threading import Thread
        self.ros_thread = Thread(target=self.spin_thread)
        self.ros_thread.daemon = True
        self.ros_thread.start()
        
        # Start Qt event loop
        app.exec_()
    
    def spin_thread(self):
        """Background thread for ROS spinning"""
        rclpy.spin(self)


def main(args=None):
    rclpy.init(args=args)
    
    try:
        node = DynamixelUINode()
    except KeyboardInterrupt:
        pass
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()
