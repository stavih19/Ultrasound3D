# Ultrasound3D

A Python desktop tool for viewing and comparing 3D ultrasound / medical imaging volumes stored as `.nii` or `.nii.gz` files.

The application watches a selected directory for newly created NIfTI files, automatically loads them, and provides an interactive GUI for browsing slices, aligning two volumes, rotating, scaling, and visually comparing them.

## Overview

`Ultrasound3D` is designed for quick visual inspection of 3D ultrasound data.  
It supports loading medical volume files, displaying them slice by slice, and comparing two volumes side by side with manual alignment controls.

The project is written in Python and uses:

- `Tkinter` for the graphical user interface
- `nibabel` for loading NIfTI medical imaging files
- `Pillow` for image processing and display
- `OpenCV` for video/frame support
- `watchdog` for monitoring a folder for new files
- `python-dotenv` for environment configuration

## Features

- Load and visualize `.nii` and `.nii.gz` medical imaging files
- Automatically monitor a directory for new ultrasound volume files
- Browse through 3D volume slices using a scrollbar
- Compare two volumes visually
- Adjust alignment between two loaded volumes:
  - X-axis offset
  - Y-axis offset
  - Z-axis slice difference
- Rotate displayed slices by 90 degrees
- Zoom in and out
- Reset visualization settings
- Display a neck reference image with slice-position indication
- Ignore segmentation files containing `seg` in the filename

## Repository Structure

```text
Ultrasound3D/
├── main.py              # Main application code
├── requirements.txt     # Python dependencies
├── neck_avatar.png      # Neck reference image used in the GUI
├── start.spec           # PyInstaller build specification
├── .env                 # Environment configuration
├── .gitignore
└── README.md
