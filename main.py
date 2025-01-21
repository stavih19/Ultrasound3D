import cv2
import tkinter as tk
from PIL import Image, ImageTk
import os
import sys
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import nibabel as nib  # Add this import for handling .nii files
import platform
import gzip
import shutil
import tempfile

# Configuration
development_mode = False  # Set to False for production
default_file_path = "/home/hagai-stavi/Desktop/PythonProjects/VideoScrolling/IM_0003_mp4_volume.nii"  # Replace with a valid file path
frame_width = 0.7


class VideoPlayer:
    def __init__(self, master, file_path):
        self.master = master
        self.master.after(100, self.center_first_frame)  # Delay to ensure canvas dimensions are available

        # Get 80% of the screen size
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        self.window_width = int(screen_width * 0.5)
        self.window_height = int(screen_height * 0.5)

        # Calculate position to center the window
        x_position = (screen_width - self.window_width) // 2
        y_position = (screen_height - self.window_height) // 2

        # Configure the window size
        self.master.geometry(f"{self.window_width}x{self.window_height}+{x_position}+{y_position}")
        self.master.title("Video Frame Viewer")

        # Create main layout frames
        self.main_frame = tk.Frame(self.master)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.left_frame = tk.Frame(self.main_frame, width=self.window_width * frame_width, height=self.window_height)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.right_frame = tk.Frame(self.main_frame, width=self.window_width * (1 - frame_width), height=self.window_height)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y)

        # Set up the canvas for the video frame
        self.canvas = tk.Canvas(self.left_frame, width=int(self.window_width * frame_width), height=self.window_height - 200)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Set up the vertical scrollbar for overlap adjustment
        self.overlap_scrollbar = tk.Scale(self.right_frame, from_=-100, to=1, 
                                          orient=tk.VERTICAL, label="Overlap", command=self.on_overlap_scroll)
        self.overlap_scrollbar.set(1)  # Default overlap value
        self.overlap_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.overlap_scrollbar.place(x=0, y=self.window_height - 150)

        # Set up the neck representation canvas
        self.neck_canvas = tk.Canvas(self.right_frame, width=int(self.window_width * (1 - frame_width)), height=self.window_height - 200)
        self.neck_canvas.pack(fill=tk.Y, pady=10)

        # Load the neck image or create a placeholder
        self.neck_image_path = resource_path("neck_avatar.png")  # Replace with the path to the neck image
        if os.path.exists(self.neck_image_path):
            neck_img = Image.open(self.neck_image_path)
            neck_width, neck_height = neck_img.size
            scale_factor = min((self.window_width * 0.3) / neck_width, (self.window_height - 200) / neck_height)
            new_width = int(neck_width * scale_factor)
            new_height = int(neck_height * scale_factor)
            neck_img_resized = neck_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            self.neck_image_tk = ImageTk.PhotoImage(neck_img_resized)
            x_offset = (self.window_width * 0.3 - new_width) // 2
            y_offset = (self.window_height - 200 - new_height) // 2
            self.neck_canvas.create_image(x_offset, y_offset, anchor=tk.NW, image=self.neck_image_tk)
            self.neck_image_height = new_height
            self.neck_image_top = y_offset
        else:
            self.neck_canvas.create_rectangle(0, 0, self.window_width * 0.3, self.window_height - 200, fill="lightgray")
            self.neck_canvas.create_text(self.window_width * 0.3 // 2, (self.window_height - 200) // 2, text="Neck Placeholder", fill="black")
            self.neck_image_height = self.window_height - 200
            self.neck_image_top = 0

        # Set up the scrollbar
        self.scrollbar = tk.Scale(self.left_frame, from_=0, to=100, orient=tk.HORIZONTAL, command=self.on_scroll)
        self.scrollbar.pack(fill=tk.X, pady=5)

        # Set up the button frame
        self.button_frame = tk.Frame(self.left_frame)
        self.button_frame.pack(fill=tk.X, pady=5)

        # Add navigation buttons to the button frame
        self.prev_button = tk.Button(self.button_frame, text="Backward", command=self.show_previous_frame)
        self.prev_button.pack(side=tk.LEFT, padx=10)

        # self.start_stop_button = tk.Button(self.button_frame, text="Start", command=self.toggle_playback)
        # self.start_stop_button.pack(side=tk.LEFT, padx=10)

        self.next_button = tk.Button(self.button_frame, text="Forward", command=self.show_next_frame)
        self.next_button.pack(side=tk.RIGHT, padx=10)

        # Add bindings for button press and release events
        self.next_button.bind("<ButtonPress>", lambda event: self.on_next_button_press())
        self.next_button.bind("<ButtonRelease>", lambda event: self.on_next_button_release())

        self.prev_button.bind("<ButtonPress>", lambda event: self.on_prev_button_press())
        self.prev_button.bind("<ButtonRelease>", lambda event: self.on_prev_button_release())

        # Playback and file properties
        self.video = None
        self.slices = None
        self.current_frame_index = 0
        self.total_frames = 0
        self.is_playing = False
        self.is_next_button_held = False
        self.is_prev_button_held = False
        self.overlap = 0

        # Determine the file type and load the appropriate file
        _, ext = os.path.splitext(file_path)
        if ext.lower() == ".gz":
            self.load_nii_file(file_path)
        else:
            self.load_video(file_path)

    def prevent_zero(self, num):
        if num == 0:
            return 0.0001
        return num

    def load_nii_file(self, file_path):
        """Load a .nii or .nii.gz file and extract slices."""
        try:
            # Handle .nii.gz files
            if file_path.endswith(".gz"):
                print(f"Decompressing {file_path}...")
                # Create a temporary file to store the decompressed data
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".nii")
                with gzip.open(file_path, 'rb') as gz_file:
                    with open(temp_file.name, 'wb') as temp_out:
                        shutil.copyfileobj(gz_file, temp_out)
                file_path = temp_file.name  # Update the file path to the decompressed file
                print(f"Decompressed to {file_path}")

            # Load the decompressed or regular .nii file
            nii_image = nib.load(file_path)
            nii_data = nii_image.get_fdata()
            self.slices = [nii_data[:, :, i] for i in range(nii_data.shape[2])]
            self.total_frames = len(self.slices)
            self.current_frame_index = 0

            # Normalize pixel values for visualization
            self.slices = [
                (slice_ - slice_.min()) / self.prevent_zero(slice_.max() - slice_.min()) * 255
                for slice_ in self.slices
            ]
            self.scrollbar.config(to=self.total_frames - 1)
            self.show_frame(0)

            # Clean up temporary file if it was created
            if file_path.endswith(".nii") and "temp_file" in locals():
                os.unlink(temp_file.name)

        except Exception as e:
            print(f"Error loading .nii or .nii.gz file: {e}")


    def load_video(self, video_path):
        """Load a video file and initialize frame navigation."""
        if self.video:
            self.video.release()
        self.video = cv2.VideoCapture(video_path)
        if not self.video.isOpened():
            print(f"Error: Couldn't open the video {video_path}.")
            return
        self.video_width = int(self.video.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.video_height = int(self.video.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = int(self.video.get(cv2.CAP_PROP_FPS)) or 30
        self.delay = int(1000 / self.fps)
        self.total_frames = int(self.video.get(cv2.CAP_PROP_FRAME_COUNT))
        self.scrollbar.config(to=self.total_frames - 1)
        self.show_frame(0)

    def play_video(self):
        """Play video frames sequentially."""
        if not self.is_playing:
            return  # Exit if playback is stopped

        if self.current_frame_index + 1 < self.total_frames:
            self.current_frame_index += 1
            self.show_frame(self.current_frame_index)
            self.scrollbar.set(self.current_frame_index)  # Sync the scrollbar with the frame index

            # Schedule the next frame update after 0.1 seconds
            self.master.after(100, self.play_video)
        else:
            # Stop playback if the last frame is reached
            self.is_playing = False
            # self.start_stop_button.config(text="Start")  # Reset button to "Start"


    def toggle_playback(self):
        """Toggle between Start and Stop playback."""
        if self.is_playing:
            # Stop playback
            self.is_playing = False
            # self.start_stop_button.config(text="Start")
        else:
            # Start playback
            self.is_playing = True
            # self.start_stop_button.config(text="Stop")
            self.play_video()  # Begin the playback loop


    def center_first_frame(self):
        """Center the first frame after the canvas dimensions are initialized."""
        self.canvas.update_idletasks()  # Ensure the canvas has updated dimensions
        self.show_frame(0)  # Display the first frame centered


    def on_scroll(self, value):
        """Handle scrollbar movement."""
        frame_index = int(float(value))
        self.show_frame(frame_index)
        self.is_playing = False
        # self.start_stop_button.config(text="Start")

    def on_next_button_press(self):
        """Handle the press event of the Next button."""
        self.is_next_button_held = True
        self.master.after(500, lambda: self.show_next_frame() if self.is_next_button_held else None)

    def on_next_button_release(self):
        """Handle the release event of the Next button."""
        self.is_next_button_held = False

    def on_prev_button_press(self):
        """Handle the press event of the Previous button."""
        self.is_prev_button_held = True
        self.master.after(500, lambda: self.show_previous_frame() if self.is_prev_button_held else None)

    def on_prev_button_release(self):
        """Handle the release event of the Previous button."""
        self.is_prev_button_held = False

    def update_neck_representation(self, frame_index):
        """Update the red line position on the neck representation."""
        if self.total_frames > 0:
            movement_range_start = self.neck_image_top + self.neck_image_height // 2
            movement_range_end = self.neck_image_top + (3 * self.neck_image_height // 4)
            y_position = int(
                movement_range_start + (frame_index / (self.total_frames - 1)) * (movement_range_end - movement_range_start)
            )
            self.neck_canvas.delete("line")
            self.neck_canvas.create_line(0, y_position, self.window_width * 0.3, y_position, fill="red", width=3, tags="line")

    def show_frame(self, frame_index):
        scaleup = 1
        """Show the frame (or slice) at the specified index, centered on the canvas."""
        # Clear the canvas initially
        self.canvas.delete("all")

        if 0 <= frame_index < self.total_frames:
            if hasattr(self, 'slices'):
                # For .nii slices
                slice_ = self.slices[frame_index]
                img = Image.fromarray(slice_.astype('uint8')).convert('L')
                frame_width, frame_height = img.size

                # Resize the frame (double the size)
                new_width, new_height = frame_width * scaleup, frame_height * scaleup
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            else:
                # For video frames
                self.video.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                ret, frame = self.video.read()
                if not ret:
                    print(f"Failed to read frame at index {frame_index}.")
                    return

                # Resize the frame
                frame_resized, frame_width, frame_height = self.resize_frame(frame)
                frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb)

                # Resize again to double the size
                new_width, new_height = frame_width * scaleup, frame_height * scaleup
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Calculate the offsets to center the resized frame in the canvas
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            x_offset = max((canvas_width - new_width) // 2, 0) - (new_width / 2) - self.overlap
            x_offset2 = x_offset + new_width + (self.overlap * 2)
            y_offset = max((canvas_height - new_height) // 2, 0)
            y_offset2 = max((canvas_height - new_height) // 2, 0)

            # Display the resized image
            self.current_frame_image = ImageTk.PhotoImage(image=img)
            self.canvas.create_image(x_offset, y_offset, anchor=tk.NW, image=self.current_frame_image)
            self.canvas.create_image(x_offset2, y_offset2, anchor=tk.NW, image=self.current_frame_image)

            # Update the current frame index and red line position
            self.current_frame_index = frame_index
            self.update_neck_representation(frame_index)
        else:
            print("Frame index out of range.")

    def on_overlap_scroll(self, value):
        """Handle overlap adjustment through the scrollbar."""
        self.overlap = int(value)
        self.show_frame(self.current_frame_index)


    def show_next_frame(self):
        """Show the next frame."""
        if self.current_frame_index + 1 < self.total_frames:
            self.current_frame_index += 1
            self.show_frame(self.current_frame_index)
            self.scrollbar.set(self.current_frame_index)
        if self.is_next_button_held:
            self.master.after(10, self.show_next_frame)

    def show_previous_frame(self):
        """Show the previous frame."""
        if self.current_frame_index > 0:
            self.current_frame_index -= 1
            self.show_frame(self.current_frame_index)
            self.scrollbar.set(self.current_frame_index)
        if self.is_prev_button_held:
            self.master.after(10, self.show_previous_frame)


class DirectoryWatcher(FileSystemEventHandler):
    def __init__(self, directory):
        self.directory = directory
        self.tk_instance = None
        self.video_player = None

    def is_file_ready(self, file_path):
        try:
            with open(file_path, 'rb'):
                return True
        except IOError:
            return False


    def on_created(self, event):
        if event.is_directory:
            return
        _, ext = os.path.splitext(event.src_path)
        if ext.lower() in [".nii", ".gz"]:  # Include .nii.gz
            for _ in range(10):
                if self.is_file_ready(event.src_path):
                    self.show_file(event.src_path)
                    return
                time.sleep(1)


    def show_file(self, file_path):
        if not self.tk_instance:
            self.tk_instance = tk.Tk()
            self.video_player = VideoPlayer(self.tk_instance, file_path)
            self.tk_instance.mainloop()
        else:
            _, ext = os.path.splitext(file_path)
            if ext.lower() == ".gz":
                self.video_player.load_nii_file(file_path)
            else:
                self.video_player.load_video(file_path)


def resource_path(relative_path):
    """Get the absolute path to a resource, considering PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller creates a temporary folder to unpack the files
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def get_downloads_path():
    """Get the full path of the Downloads folder based on the operating system."""
    os_name = platform.system()

    if os_name == "Windows":
        downloads_path = os.path.join(os.getenv("USERPROFILE"), "Downloads")
    elif os_name == "Darwin":  # macOS
        downloads_path = os.path.join(os.getenv("HOME"), "Downloads")
    elif os_name == "Linux":
        downloads_path = os.path.join(os.getenv("HOME"), "Downloads")
    else:
        raise OSError(f"Unsupported operating system: {os_name}")

    if os.path.exists(downloads_path):
        return downloads_path
    else:
        raise FileNotFoundError("Downloads directory not found.")


def main(directory_path):
    if development_mode:
        root = tk.Tk()
        VideoPlayer(root, resource_path('IM_0003_mp4_volume.nii.gz'))
        root.mainloop()
    else:
        if(directory_path is None or '' or not os.path.isdir(directory_path)):
            directory = os.path.abspath(os.getcwd())
        event_handler = DirectoryWatcher(directory)
        observer = Observer()
        observer.schedule(event_handler, directory, recursive=False)
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()


if __name__ == "__main__":
    directory = os.getenv('LISTENING_DIRECTORY', 'D:\\docker_test\\test')
    print("Watching on - " + directory)
    print("After cerate the file it will take a couple of seconds")
    print("Waiting for .nii files to create there ...")
    main(directory)
