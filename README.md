# Video Motion Detector / Glitch Effect  

This detects and visualizes movement in video files using OpenCV.

Seen this getting around on Instagram and TikTok.
Run the build to create an .exe

![Movement Detector Preview](https://github.com/laidlaw42/video_motion_glitch/raw/main/preview.jpg)

## Building from Source

### Requirements

- Python 3.8 or higher
- OpenCV (cv2)
- PyQt6
- NumPy
- PyInstaller (for building executable)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/movement_detector.git
cd movement_detector
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

### Building the Executable

1. Make sure you have all requirements installed
2. Run the build script:
```bash
python build.py
```
3. The executable will be created in the `dist` folder

## Features

### Detection
- Movement detection with adjustable sensitivity
- Area and speed measurement
- Direction tracking (Up, Down, Left, Right)
- Optional JSON data export for detected movements

### Box Settings
- Customizable box thickness and padding
- Multiple box styles (solid, dashed, dotted)
- Optional rounded corners
- Toggle box visibility
- Custom box color

### Effects
- Inverted effect with adjustable intensity
- Heat map visualization based on movement speed
- Edge detection with customizable color and intensity

### Connections
- Connecting lines between nearby detected objects
- Adjustable line distance
- Custom line color
- Connection point selection (Center or Corner)

### Output Settings
- Adjustable output quality
- Optional video resizing with scale control
- Custom font settings (size, family, color)
- Font display toggle

## Requirements

- Python 3.8 or higher
- OpenCV (cv2)
- PyQt6
- NumPy

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/movement_detector.git
cd movement_detector
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

## Usage

1. Run the application:
```bash
python main.py
```

2. Click "Select Video" to choose a video file for processing
3. Adjust settings as desired:
   - Output quality and resize options
   - Font settings for movement information
   - Box appearance and effects
   - Connection settings
4. Click "Process Video" to start processing
5. The processed video will be saved with "_processed" suffix
6. If "Save detection data to JSON" is enabled, movement data will be saved in a separate JSON file

## Settings Guide

### Output
- Quality: Adjusts the output video quality (1-30)
- Scale: Resize the output video (25-100%)
- Resize Output: Toggle video resizing
- Save detection data to JSON: Export movement data

### Font
- Size: Adjust text size for movement information
- Family: Choose from multiple font options or disable text
- Color: Customize text color

### Box Settings
- Thickness: Adjust box line thickness
- Padding: Add space around detected objects
- Style: Choose between solid, dashed, or dotted lines
- Rounded Corners: Toggle corner rounding
- Show Box: Toggle box visibility
- Color: Customize box color

### Box Effects
- Inverted: Apply negative effect with adjustable intensity
- Heat Map: Color-code based on movement speed
- Edge Detection: Highlight edges with customizable color and intensity

### Connection and Motion
- Movement Sensitivity: Adjust detection threshold
- Line Distance: Set maximum distance for connections
- Connection Point: Choose between center or corner connections
- Show Connecting Lines: Toggle connection visualization
- Color: Customize connection line color

## License

This project is licensed under the MIT License - see the LICENSE file for details. 
