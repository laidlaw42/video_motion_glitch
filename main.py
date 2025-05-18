import sys
import cv2
import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QPushButton, QFileDialog, QLabel, QProgressBar,
                            QColorDialog, QHBoxLayout, QCheckBox, QSpinBox,
                            QGroupBox, QSlider, QComboBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
import json
from datetime import datetime
from collections import deque
import os

class VideoProcessor(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, video_path, detector, color, save_data, settings):
        super().__init__()
        self.video_path = video_path
        self.detector = detector
        self.color = color
        self.save_data = save_data
        self.settings = settings
        self.is_running = True

    def get_next_output_path(self, base_path):
        counter = 1
        while True:
            output_path = f"{base_path}_{counter}.mp4"
            if not os.path.exists(output_path):
                return output_path
            counter += 1

    def run(self):
        try:
            cap = cv2.VideoCapture(self.video_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = int(cap.get(cv2.CAP_PROP_FPS))

            # Apply resize if enabled
            if self.settings['resize_output']:
                scale = self.settings['resize_scale']
                width = int(width * scale)
                height = int(height * scale)

            base_path = self.video_path.rsplit('.', 1)[0] + '_processed'
            output_path = self.get_next_output_path(base_path)
            
            # Try different codecs in order of preference
            codecs = [
                ('mp4v', cv2.VideoWriter_fourcc(*'mp4v')),  # Default MP4 codec
                ('XVID', cv2.VideoWriter_fourcc(*'XVID')),  # XVID codec
                ('MJPG', cv2.VideoWriter_fourcc(*'MJPG'))   # Motion JPEG codec
            ]
            
            out = None
            for codec_name, fourcc in codecs:
                try:
                    out = cv2.VideoWriter(
                        output_path,
                        fourcc,
                        fps,
                        (width, height),
                        True
                    )
                    if out.isOpened():
                        break
                except:
                    if out:
                        out.release()
                    continue
            
            if not out or not out.isOpened():
                raise Exception("Failed to initialize video writer with any available codec")

            # Set quality parameter if available
            quality = self.settings.get('output_quality', 15)  # Lower default quality
            if hasattr(out, 'set'):
                try:
                    out.set(cv2.VIDEOWRITER_PROP_QUALITY, quality)
                except:
                    pass  # Ignore if quality setting is not supported

            frame_count = 0
            detection_data = []

            while cap.isOpened() and self.is_running:
                ret, frame = cap.read()
                if not ret:
                    break

                # Resize frame if enabled
                if self.settings['resize_output']:
                    frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)

                processed_frame, frame_data = self.detector.process_frame(
                    frame, 
                    self.color,
                    self.settings
                )
                out.write(processed_frame)
                
                if self.save_data:
                    detection_data.append(frame_data)

                frame_count += 1
                progress = int((frame_count / total_frames) * 100)
                self.progress.emit(progress)

            cap.release()
            out.release()

            if self.save_data:
                data_path = output_path.rsplit('.', 1)[0] + '_data.json'
                with open(data_path, 'w') as f:
                    json.dump(detection_data, f)

            self.finished.emit(output_path)

        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self.is_running = False

class MovementDetector:
    def __init__(self):
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500, detectShadows=False)
        self.prev_centers = {}
        self.next_id = 0

    def get_heat_color(self, speed, max_speed):
        # Convert speed to a color (blue -> green -> yellow -> red)
        if max_speed == 0:
            return (255, 0, 0)  # Blue for no movement
        
        ratio = min(speed / max_speed, 1.0)
        if ratio < 0.25:
            # Blue to Green
            return (255, int(255 * ratio * 4), 0)
        elif ratio < 0.5:
            # Green to Yellow
            return (255 - int(255 * (ratio - 0.25) * 4), 255, 0)
        elif ratio < 0.75:
            # Yellow to Orange
            return (0, 255 - int(255 * (ratio - 0.5) * 4), int(255 * (ratio - 0.5) * 4))
        else:
            # Orange to Red
            return (0, int(255 * (1 - ratio) * 4), 255)

    def draw_box(self, frame, x, y, w, h, color, settings, speed=0, max_speed=0):
        # Calculate padding
        padding = settings['box_padding']
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = min(frame.shape[1] - x, w + 2 * padding)
        h = min(frame.shape[0] - y, h + 2 * padding)

        if settings['box_style'] == 'solid':
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, settings['box_thickness'])
        elif settings['box_style'] == 'dashed':
            # Draw dashed rectangle
            dash_length = 10
            for i in range(0, w, dash_length * 2):
                cv2.line(frame, (x + i, y), (x + min(i + dash_length, w), y), color, settings['box_thickness'])
                cv2.line(frame, (x + i, y + h), (x + min(i + dash_length, w), y + h), color, settings['box_thickness'])
            for i in range(0, h, dash_length * 2):
                cv2.line(frame, (x, y + i), (x, y + min(i + dash_length, h)), color, settings['box_thickness'])
                cv2.line(frame, (x + w, y + i), (x + w, y + min(i + dash_length, h)), color, settings['box_thickness'])
        elif settings['box_style'] == 'dotted':
            # Draw dotted rectangle
            dot_spacing = 10
            for i in range(0, w, dot_spacing):
                cv2.circle(frame, (x + i, y), settings['box_thickness']//2, color, -1)
                cv2.circle(frame, (x + i, y + h), settings['box_thickness']//2, color, -1)
            for i in range(0, h, dot_spacing):
                cv2.circle(frame, (x, y + i), settings['box_thickness']//2, color, -1)
                cv2.circle(frame, (x + w, y + i), settings['box_thickness']//2, color, -1)

        if settings['box_corners']:
            # Draw rounded corners
            corner_length = min(w, h) // 4
            # Top-left corner
            cv2.line(frame, (x, y + corner_length), (x, y), color, settings['box_thickness'])
            cv2.line(frame, (x, y), (x + corner_length, y), color, settings['box_thickness'])
            # Top-right corner
            cv2.line(frame, (x + w - corner_length, y), (x + w, y), color, settings['box_thickness'])
            cv2.line(frame, (x + w, y), (x + w, y + corner_length), color, settings['box_thickness'])
            # Bottom-left corner
            cv2.line(frame, (x, y + h - corner_length), (x, y + h), color, settings['box_thickness'])
            cv2.line(frame, (x, y + h), (x + corner_length, y + h), color, settings['box_thickness'])
            # Bottom-right corner
            cv2.line(frame, (x + w - corner_length, y + h), (x + w, y + h), color, settings['box_thickness'])
            cv2.line(frame, (x + w, y + h - corner_length), (x + w, y + h), color, settings['box_thickness'])

    def process_frame(self, frame, color, settings):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        fgmask = self.background_subtractor.apply(gray)
        
        kernel = np.ones((5,5), np.uint8)
        fgmask = cv2.morphologyEx(fgmask, cv2.MORPH_OPEN, kernel)
        fgmask = cv2.morphologyEx(fgmask, cv2.MORPH_CLOSE, kernel)
        
        contours, _ = cv2.findContours(fgmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        frame_data = []
        current_centers = {}
        boxes = []
        max_speed = 0

        # First pass to find max speed
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > settings['min_area']:  # Use the sensitivity setting
                x, y, w, h = cv2.boundingRect(contour)
                center = (x + w//2, y + h//2)
                
                if center in self.prev_centers:
                    prev_center = self.prev_centers[center]
                    dx = center[0] - prev_center[0]
                    dy = center[1] - prev_center[1]
                    speed = np.sqrt(dx*dx + dy*dy)
                    max_speed = max(max_speed, speed)

        # Second pass to process and draw
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > settings['min_area']:  # Use the sensitivity setting
                x, y, w, h = cv2.boundingRect(contour)
                center = (x + w//2, y + h//2)
                
                speed = 0
                direction = "N/A"
                if center in self.prev_centers:
                    prev_center = self.prev_centers[center]
                    dx = center[0] - prev_center[0]
                    dy = center[1] - prev_center[1]
                    speed = np.sqrt(dx*dx + dy*dy)
                    
                    if abs(dx) > abs(dy):
                        direction = "Right" if dx > 0 else "Left"
                    else:
                        direction = "Down" if dy > 0 else "Up"

                # Get the region of interest
                roi = frame[y:y+h, x:x+w].copy()

                # Apply effects based on settings
                if settings['negative_effect']:
                    negative_roi = cv2.bitwise_not(roi)
                    alpha = settings['negative_intensity'] / 100.0
                    roi = cv2.addWeighted(roi, 1-alpha, negative_roi, alpha, 0)

                if settings['heat_map']:
                    heat_color = self.get_heat_color(speed, max_speed)
                    heat_alpha = settings['heat_intensity'] / 100.0
                    heat_overlay = np.full_like(roi, heat_color)
                    roi = cv2.addWeighted(roi, 1-heat_alpha, heat_overlay, heat_alpha, 0)

                if settings['edge_detection']:
                    edges = cv2.Canny(roi, 100, 200)
                    edge_alpha = settings['edge_intensity'] / 100.0
                    edge_overlay = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
                    # Apply edge color
                    edge_overlay[edges > 0] = settings['edge_color']
                    roi = cv2.addWeighted(roi, 1-edge_alpha, edge_overlay, edge_alpha, 0)

                # Apply the processed region back to the frame
                frame[y:y+h, x:x+w] = roi

                # Draw bounding box with effects
                box_color = color
                if settings['heat_map']:
                    box_color = self.get_heat_color(speed, max_speed)
                self.draw_box(frame, x, y, w, h, box_color, settings, speed, max_speed)
                
                # Display area and speed with adjustable font size and color
                info_text = f'{int(area)}'
                if speed > 0:
                    info_text += f' | {int(speed)}px/f'
                cv2.putText(frame, info_text, (x, y - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, settings['font_size'], 
                           settings['font_color'], 2)

                # Store box information with connection point
                connection_point = center if settings['connection_point'] == 'center' else (x, y)
                boxes.append({
                    'center': center,
                    'connection_point': connection_point,
                    'area': area
                })

                frame_data.append({
                    'area': int(area),
                    'position': {'x': x, 'y': y, 'width': w, 'height': h},
                    'speed': float(speed),
                    'direction': direction
                })

                current_centers[center] = center

        # Draw lines between nearby boxes
        if settings['show_lines']:
            for i, box1 in enumerate(boxes):
                for box2 in boxes[i+1:]:
                    point1 = box1['connection_point']
                    point2 = box2['connection_point']
                    distance = np.sqrt((point1[0] - point2[0])**2 + (point1[1] - point2[1])**2)
                    
                    if distance < settings['line_distance']:
                        intensity = int(255 * (1 - distance/settings['line_distance']))
                        line_color = (
                            int(settings['line_color'][0] * intensity/255),
                            int(settings['line_color'][1] * intensity/255),
                            int(settings['line_color'][2] * intensity/255)
                        )
                        cv2.line(frame, point1, point2, line_color, 2)

        self.prev_centers = current_centers
        return frame, frame_data

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Movement Detector")
        self.setMinimumSize(800, 800)  # Wider window for two columns
        
        # Initialize variables
        self.video_path = None
        self.detector = MovementDetector()
        self.processor = None
        self.box_color = (0, 0, 0)  # Black
        self.line_color = (255, 192, 203)  # Pink
        self.edge_color = (255, 255, 170)  # #aaffff in BGR
        self.font_color = (0, 0, 0)  # Black
        
        # Settings dictionary
        self.settings = {
            'line_distance': 200,
            'show_lines': True,
            'negative_effect': True,
            'negative_intensity': 100,
            'line_color': self.line_color,
            'heat_map': True,
            'heat_intensity': 50,
            'edge_detection': True,
            'edge_intensity': 50,
            'edge_color': self.edge_color,
            'box_thickness': 2,
            'box_style': 'solid',  # 'solid', 'dashed', or 'dotted'
            'box_corners': False,
            'box_padding': 0,
            'output_quality': 15,  # Lower default quality for better compression
            'resize_output': True,  # Enable resize by default
            'resize_scale': 0.75,   # Default scale (75% of original size)
            'font_size': 0.9,       # Default font size
            'min_area': 500,        # Default minimum area for movement detection
            'font_color': self.font_color,  # Default font color
            'save_data': False,     # Default save data state
            'font_family': 'Arial', # Default font family
            'show_box': True,       # Default show bounding box
            'connection_point': 'center',  # Default connection point
        }
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 5)  # Reduced bottom margin
        main_layout.setSpacing(10)
        
        # Create two-column layout
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(20)  # Space between columns
        
        # Left column
        left_column = QVBoxLayout()
        left_column.setSpacing(4)  # Reduced spacing between groups
        
        # Right column
        right_column = QVBoxLayout()
        right_column.setSpacing(4)  # Reduced spacing between groups
        
        # Add settings groups to columns
        # Left column: Output and Font settings
        self.create_video_settings(left_column)
        self.create_detection_settings(left_column)
        self.create_box_settings(left_column)
        
        # Right column: Box Effects and Connections & Motion
        self.create_effect_settings(right_column)
        self.create_connection_settings(right_column)
        
        # Add columns to main layout with stretch factors
        columns_layout.addLayout(left_column, 1)  # Left column gets stretch factor 1
        columns_layout.addLayout(right_column, 1)  # Right column gets stretch factor 1
        main_layout.addLayout(columns_layout)
        
        # Status and progress
        self.status_label = QLabel("Select a video file to begin")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.select_button = self.create_button("Select Video", self.select_video)
        self.process_button = self.create_button("Process Video", self.process_video)
        self.process_button.setEnabled(False)
        self.cancel_button = self.create_button("Cancel Processing", self.cancel_processing)
        self.cancel_button.setVisible(False)
        
        button_layout.addWidget(self.select_button)
        button_layout.addWidget(self.process_button)
        button_layout.addWidget(self.cancel_button)
        
        # Add widgets to main layout with minimal spacing
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(self.progress_bar)
        main_layout.addLayout(button_layout, 0)  # Set stretch factor to 0 to prevent expansion

        # Set slider styles
        self.set_slider_styles()

    def create_button(self, text, callback):
        button = QPushButton(text)
        button.setFixedHeight(30)  # Consistent button height
        button.setMinimumWidth(120)  # Minimum width for buttons
        button.clicked.connect(callback)
        return button

    def create_color_button(self, text, callback):
        button = QPushButton(text)
        button.setFixedSize(100, 30)  # Fixed size for color buttons
        button.clicked.connect(callback)
        return button

    def create_color_preview(self, color, callback):
        preview = QLabel()
        preview.setFixedSize(30, 30)
        preview.setStyleSheet(f"background-color: rgb{color}; border: 1px solid #666666;")
        preview.setCursor(Qt.CursorShape.PointingHandCursor)  # Show pointer cursor on hover
        preview.mousePressEvent = lambda e: callback()  # Make clickable
        return preview

    def create_color_value_label(self, color):
        return QLabel(f"RGB: {color}")

    def create_slider_layout(self, label_text, min_val, max_val, value, callback, value_format="{0}"):
        layout = QHBoxLayout()
        layout.setSpacing(8)  # Reduced spacing between elements
        
        # Label with fixed width
        label = QLabel(label_text)
        label.setFixedWidth(120)  # Fixed width for labels
        
        # Slider with fixed height and width
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setFixedHeight(20)  # Fixed height for sliders
        slider.setFixedWidth(150)  # Fixed width for sliders
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(value)
        slider.valueChanged.connect(callback)
        
        # Value label with fixed width
        value_label = QLabel(value_format.format(value))
        value_label.setFixedWidth(50)  # Fixed width for value labels
        
        layout.addWidget(label)
        layout.addWidget(slider)
        layout.addWidget(value_label)
        return layout, slider, value_label

    def create_checkbox(self, text, checked, callback):
        checkbox = QCheckBox(text)
        checkbox.setChecked(checked)
        checkbox.stateChanged.connect(callback)
        return checkbox

    def create_combobox(self, items, current_text, callback):
        combobox = QComboBox()
        combobox.addItems(items)
        combobox.setCurrentText(current_text)
        combobox.currentTextChanged.connect(callback)
        return combobox

    def set_slider_styles(self):
        # Get all sliders in the window
        sliders = self.findChildren(QSlider)
        for slider in sliders:
            slider.setStyleSheet("""
                QSlider::groove:horizontal {
                    border: 1px solid #666666;
                    height: 8px;
                    background: #a0a0a0;
                    margin: 2px 0;
                    border-radius: 4px;
                }
                QSlider::handle:horizontal {
                    background: #505050;
                    border: 1px solid #404040;
                    width: 18px;
                    margin: -2px 0;
                    border-radius: 9px;
                }
                QSlider::handle:horizontal:hover {
                    background: #606060;
                    border: 1px solid #505050;
                }
                QSlider::sub-page:horizontal {
                    background: #808080;
                    border-radius: 4px;
                }
                QSlider::sub-page:horizontal:hover {
                    background: #909090;
                }
            """)

    def create_group_box(self, title):
        group = QGroupBox(title)
        group.setStyleSheet("""
            QGroupBox {
                font-weight: 600;
                border: 1px solid #cccccc;
                border-radius: 5px;
                margin-top: 4px;
                padding: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        return group

    def create_video_settings(self, parent_layout):
        group = self.create_group_box("Output")
        layout = QVBoxLayout()
        layout.setSpacing(8)  # Reduced spacing
        
        # Quality settings
        quality_layout, self.quality_slider, self.quality_value = self.create_slider_layout(
            "Quality:", 1, 30, self.settings['output_quality'],
            self.update_output_quality
        )
        
        # Resize settings
        resize_layout = QVBoxLayout()
        resize_layout.setSpacing(4)  # Reduced spacing
        
        resize_scale_layout, self.resize_scale_slider, self.resize_scale_value = self.create_slider_layout(
            "Scale:", 25, 100, int(self.settings['resize_scale'] * 100),
            self.update_resize_scale, "{0}%"
        )
        
        resize_options = QHBoxLayout()
        resize_options.setSpacing(8)  # Reduced spacing
        self.resize_checkbox = self.create_checkbox("Resize Output", self.settings['resize_output'], self.toggle_resize)
        self.save_data_checkbox = self.create_checkbox("Save detection data to JSON", False, self.toggle_save_data)
        resize_options.addWidget(self.resize_checkbox)
        resize_options.addWidget(self.save_data_checkbox)
        resize_options.addStretch()
        
        resize_layout.addLayout(resize_scale_layout)
        resize_layout.addLayout(resize_options)
        
        layout.addLayout(quality_layout)
        layout.addLayout(resize_layout)
        group.setLayout(layout)
        parent_layout.addWidget(group)

    def create_detection_settings(self, parent_layout):
        group = self.create_group_box("Font")
        layout = QVBoxLayout()
        layout.setSpacing(8)  # Reduced spacing

        # Font settings
        font_layout, self.font_slider, self.font_value = self.create_slider_layout(
            "Size:", 1, 20, int(self.settings['font_size'] * 10),
            self.update_font_size, "{0:.1f}"
        )

        # Font family selection
        font_family_layout = QHBoxLayout()
        font_family_layout.setSpacing(8)  # Reduced spacing
        font_family_label = QLabel("Family:")
        font_family_label.setFixedWidth(120)
        self.font_family_combo = self.create_combobox(
            ['Off', 'Arial', 'Times New Roman', 'Courier New', 'Verdana', 'Georgia'],
            self.settings['font_family'],
            self.update_font_family
        )
        font_family_layout.addWidget(font_family_label)
        font_family_layout.addWidget(self.font_family_combo)
        font_family_layout.addStretch()

        # Font color selection
        font_color_layout = QHBoxLayout()
        font_color_layout.setSpacing(8)  # Reduced spacing
        self.font_color_preview = self.create_color_preview(self.font_color, self.select_font_color)
        self.font_color_value = self.create_color_value_label(self.font_color)
        font_color_layout.addWidget(self.font_color_preview)
        font_color_layout.addWidget(self.font_color_value)
        font_color_layout.addStretch()
        
        layout.addLayout(font_layout)
        layout.addLayout(font_family_layout)
        layout.addLayout(font_color_layout)
        group.setLayout(layout)
        parent_layout.addWidget(group)

    def create_box_settings(self, parent_layout):
        group = self.create_group_box("Box Settings")
        layout = QVBoxLayout()
        layout.setSpacing(8)  # Reduced spacing
        
        # Thickness
        thickness_layout, self.thickness_slider, self.thickness_value = self.create_slider_layout(
            "Thickness:", 1, 5, self.settings['box_thickness'],
            self.update_box_thickness, "{0}px"
        )
        
        # Padding
        padding_layout, self.padding_slider, self.padding_value = self.create_slider_layout(
            "Padding:", 0, 20, self.settings['box_padding'],
            self.update_box_padding, "{0}px"
        )
        
        # Style
        style_layout = QHBoxLayout()
        style_layout.setSpacing(8)  # Reduced spacing
        style_label = QLabel("Style:")
        style_label.setFixedWidth(120)  # Match other labels
        self.style_combo = self.create_combobox(['solid', 'dashed', 'dotted'], self.settings['box_style'], self.update_box_style)
        style_layout.addWidget(style_label)
        style_layout.addWidget(self.style_combo)
        style_layout.addStretch()
        
        # Corners
        corners_layout = QHBoxLayout()
        corners_layout.setSpacing(8)  # Reduced spacing
        self.corners_checkbox = self.create_checkbox("Rounded Corners", self.settings['box_corners'], self.toggle_box_corners)
        corners_layout.addWidget(self.corners_checkbox)
        corners_layout.addStretch()
        
        # Color selection and show box checkbox
        color_layout = QHBoxLayout()
        color_layout.setSpacing(8)  # Reduced spacing
        self.box_color_preview = self.create_color_preview(self.box_color, self.select_box_color)
        self.box_color_value = self.create_color_value_label(self.box_color)
        self.show_box_checkbox = self.create_checkbox("Show Box", self.settings['show_box'], self.toggle_show_box)
        color_layout.addWidget(self.box_color_preview)
        color_layout.addWidget(self.box_color_value)
        color_layout.addWidget(self.show_box_checkbox)
        color_layout.addStretch()
        
        layout.addLayout(thickness_layout)
        layout.addLayout(padding_layout)
        layout.addLayout(style_layout)
        layout.addLayout(corners_layout)
        layout.addLayout(color_layout)
        group.setLayout(layout)
        parent_layout.addWidget(group)

    def create_effect_settings(self, parent_layout):
        group = self.create_group_box("Box Effects")
        layout = QVBoxLayout()
        layout.setSpacing(8)  # Reduced spacing
        
        # Inverted effect settings
        inverted_layout = QHBoxLayout()
        inverted_layout.setSpacing(8)  # Reduced spacing
        self.negative_checkbox = self.create_checkbox("Inverted", self.settings['negative_effect'], self.toggle_negative_effect)
        negative_intensity_layout, self.negative_slider, self.negative_value = self.create_slider_layout(
            "", 0, 100, self.settings['negative_intensity'],
            self.update_negative_intensity, "{0}%"
        )
        inverted_layout.addWidget(self.negative_checkbox)
        inverted_layout.addLayout(negative_intensity_layout)
        
        # Heat map settings
        heat_layout = QHBoxLayout()
        heat_layout.setSpacing(8)  # Reduced spacing
        self.heat_checkbox = self.create_checkbox("Heat Map", self.settings['heat_map'], self.toggle_heat_map)
        heat_intensity_layout, self.heat_slider, self.heat_value = self.create_slider_layout(
            "", 0, 100, self.settings['heat_intensity'],
            self.update_heat_intensity, "{0}%"
        )
        heat_layout.addWidget(self.heat_checkbox)
        heat_layout.addLayout(heat_intensity_layout)
        
        # Edge detection settings
        edge_layout = QVBoxLayout()
        edge_layout.setSpacing(8)  # Reduced spacing
        
        # Edge detection header with checkbox and intensity
        edge_header = QHBoxLayout()
        edge_header.setSpacing(8)  # Reduced spacing
        self.edge_checkbox = self.create_checkbox("Edge Detection", self.settings['edge_detection'], self.toggle_edge_detection)
        edge_intensity_layout, self.edge_slider, self.edge_value = self.create_slider_layout(
            "", 0, 100, self.settings['edge_intensity'],
            self.update_edge_intensity, "{0}%"
        )
        edge_header.addWidget(self.edge_checkbox)
        edge_header.addLayout(edge_intensity_layout)
        
        # Edge color selection (at bottom)
        edge_color_layout = QHBoxLayout()
        edge_color_layout.setSpacing(8)  # Reduced spacing
        self.edge_color_preview = self.create_color_preview(self.edge_color, self.select_edge_color)
        self.edge_color_value = self.create_color_value_label(self.edge_color)
        edge_color_layout.addWidget(self.edge_color_preview)
        edge_color_layout.addWidget(self.edge_color_value)
        edge_color_layout.addStretch()
        
        edge_layout.addLayout(edge_header)
        edge_layout.addLayout(edge_color_layout)
        
        layout.addLayout(inverted_layout)
        layout.addLayout(heat_layout)
        layout.addLayout(edge_layout)
        group.setLayout(layout)
        parent_layout.addWidget(group)

    def create_connection_settings(self, parent_layout):
        group = self.create_group_box("Connection and Motion")
        layout = QVBoxLayout()
        layout.setSpacing(8)  # Reduced spacing
        
        # Movement sensitivity
        sensitivity_layout, self.sensitivity_slider, self.sensitivity_value_label = self.create_slider_layout(
            "Movement Sensitivity:", 50, 1000, self.settings['min_area'],
            self.update_sensitivity
        )
        
        # Line distance slider
        distance_layout, self.distance_slider, self.distance_value = self.create_slider_layout(
            "Line Distance:", 50, 500, self.settings['line_distance'],
            self.update_line_distance, "{0}px"
        )
        
        # Connection point selection
        connection_point_layout = QHBoxLayout()
        connection_point_layout.setSpacing(8)
        connection_point_label = QLabel("Connection Point:")
        connection_point_label.setFixedWidth(120)
        self.connection_point_combo = self.create_combobox(
            ['Center', 'Corner'],
            self.settings['connection_point'].capitalize(),
            self.update_connection_point
        )
        connection_point_layout.addWidget(connection_point_label)
        connection_point_layout.addWidget(self.connection_point_combo)
        connection_point_layout.addStretch()
        
        # Line color selection and show lines checkbox
        line_layout = QHBoxLayout()
        line_layout.setSpacing(8)  # Reduced spacing
        self.show_lines_checkbox = self.create_checkbox("Show Connecting Lines", self.settings['show_lines'], self.toggle_lines)
        self.line_color_preview = self.create_color_preview(self.line_color, self.select_line_color)
        self.line_color_value = self.create_color_value_label(self.line_color)
        line_layout.addWidget(self.show_lines_checkbox)
        line_layout.addWidget(self.line_color_preview)
        line_layout.addWidget(self.line_color_value)
        line_layout.addStretch()
        
        layout.addLayout(sensitivity_layout)
        layout.addLayout(distance_layout)
        layout.addLayout(connection_point_layout)
        layout.addLayout(line_layout)
        group.setLayout(layout)
        parent_layout.addWidget(group)

    def select_box_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.box_color = (color.blue(), color.green(), color.red())
            self.box_color_preview.setStyleSheet(f"background-color: {color.name()}")
            self.box_color_value.setText(f"RGB: {self.box_color}")
    
    def select_line_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.line_color = (color.blue(), color.green(), color.red())
            self.settings['line_color'] = self.line_color
            self.line_color_preview.setStyleSheet(f"background-color: {color.name()}")
            self.line_color_value.setText(f"RGB: {self.line_color}")
    
    def select_edge_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.edge_color = (color.blue(), color.green(), color.red())
            self.settings['edge_color'] = self.edge_color
            self.edge_color_preview.setStyleSheet(f"background-color: {color.name()}")
            self.edge_color_value.setText(f"RGB: {self.edge_color}")
    
    def select_font_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.font_color = (color.blue(), color.green(), color.red())
            self.settings['font_color'] = self.font_color
            self.font_color_preview.setStyleSheet(f"background-color: {color.name()}")
            self.font_color_value.setText(f"RGB: {self.font_color}")
    
    def update_line_distance(self, value):
        self.settings['line_distance'] = value
        self.distance_value.setText(f"{value}px")
    
    def toggle_lines(self, state):
        self.settings['show_lines'] = bool(state)
    
    def toggle_negative_effect(self, state):
        self.settings['negative_effect'] = bool(state)
    
    def update_negative_intensity(self, value):
        self.settings['negative_intensity'] = value
        self.negative_value.setText(f"{value}%")
    
    def toggle_heat_map(self, state):
        self.settings['heat_map'] = bool(state)
    
    def update_heat_intensity(self, value):
        self.settings['heat_intensity'] = value
        self.heat_value.setText(f"{value}%")
    
    def toggle_edge_detection(self, state):
        self.settings['edge_detection'] = bool(state)
    
    def update_edge_intensity(self, value):
        self.settings['edge_intensity'] = value
        self.edge_value.setText(f"{value}%")
    
    def update_box_thickness(self, value):
        self.settings['box_thickness'] = value
        self.thickness_value.setText(f"{value}px")
    
    def update_box_style(self, style):
        self.settings['box_style'] = style
    
    def toggle_box_corners(self, state):
        self.settings['box_corners'] = bool(state)
    
    def update_box_padding(self, value):
        self.settings['box_padding'] = value
        self.padding_value.setText(f"{value}px")
    
    def toggle_glow(self, state):
        self.settings['glow_effect'] = bool(state)
    
    def update_glow_intensity(self, value):
        self.settings['glow_intensity'] = value
        self.glow_intensity_value.setText(f"{value}%")
    
    def update_glow_radius(self, value):
        self.settings['glow_radius'] = value
        self.glow_radius_value.setText(f"{value}px")
    
    def toggle_pulse(self, state):
        self.settings['pulse_effect'] = bool(state)
    
    def update_pulse_intensity(self, value):
        self.settings['pulse_intensity'] = value
        self.pulse_intensity_value.setText(f"{value}%")
    
    def update_pulse_radius(self, value):
        self.settings['pulse_radius'] = value
        self.pulse_radius_value.setText(f"{value}px")
    
    def update_output_quality(self, value):
        self.settings['output_quality'] = value
        self.quality_value.setText(str(value))
    
    def toggle_resize(self, state):
        self.settings['resize_output'] = bool(state)
        self.resize_scale_slider.setEnabled(bool(state))

    def update_resize_scale(self, value):
        self.settings['resize_scale'] = value / 100.0
        self.resize_scale_value.setText(f"{value}%")

    def update_font_size(self, value):
        self.settings['font_size'] = value / 10.0
        self.font_value.setText(f"{value/10.0:.1f}")

    def update_sensitivity(self, value):
        self.settings['min_area'] = value
        self.sensitivity_value_label.setText(str(value))

    def toggle_save_data(self, state):
        self.settings['save_data'] = bool(state)

    def update_font_family(self, font):
        self.settings['font_family'] = font

    def toggle_show_box(self, state):
        self.settings['show_box'] = bool(state)

    def update_connection_point(self, point):
        self.settings['connection_point'] = point.lower()

    def set_processing_state(self, is_processing):
        self.select_button.setEnabled(not is_processing)
        self.process_button.setEnabled(not is_processing)
        self.cancel_button.setVisible(is_processing)
        self.progress_bar.setVisible(is_processing)
        if is_processing:
            self.status_label.setText("Processing video...")
        else:
            self.status_label.setText(f"Selected: {self.video_path}" if self.video_path else "Select a video file to begin")

    def select_video(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            "",
            "Video Files (*.mp4 *.mov *.avi *.mkv)"
        )
        if file_name:
            self.video_path = file_name
            self.status_label.setText(f"Selected: {file_name}")
            self.process_button.setEnabled(True)
    
    def process_video(self):
        if not self.video_path:
            self.status_label.setText("Please select a video file first")
            return
        
        self.set_processing_state(True)
        self.progress_bar.setValue(0)
        
        self.processor = VideoProcessor(
            self.video_path,
            self.detector,
            self.box_color,
            self.save_data_checkbox.isChecked(),
            self.settings
        )
        self.processor.progress.connect(self.update_progress)
        self.processor.finished.connect(self.processing_finished)
        self.processor.error.connect(self.processing_error)
        self.processor.start()
    
    def cancel_processing(self):
        if self.processor and self.processor.isRunning():
            self.processor.stop()
            self.processor.wait()
            self.set_processing_state(False)
            self.status_label.setText("Processing cancelled")
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
    
    def processing_finished(self, output_path):
        self.set_processing_state(False)
        self.status_label.setText(f"Processing complete! Saved to: {output_path}")
    
    def processing_error(self, error_msg):
        self.set_processing_state(False)
        self.status_label.setText(f"Error: {error_msg}")
    
    def closeEvent(self, event):
        if self.processor and self.processor.isRunning():
            self.processor.stop()
            self.processor.wait()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 