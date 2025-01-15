import cv2
import tkinter as tk
from PIL import Image, ImageTk
import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import nibabel as nib  # Add this import for handling .nii files


class VideoPlayer:
    def __init__(self, master, file_path):
        self.master = master

        # Get 80% of the screen size
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        self.window_width = int(screen_width * 0.8)
        self.window_height = int(screen_height * 0.8)

        # Configure the window size
        self.master.geometry(f"{self.window_width}x{self.window_height}")
        self.master.title("Video Frame Viewer")

        # Set up the main frame to hold canvas and buttons
        self.main_frame = tk.Frame(self.master)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Set up the canvas to display frames
        self.canvas = tk.Canvas(self.main_frame, width=self.window_width, height=self.window_height - 100)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Set up the scrollbar
        self.scrollbar = tk.Scale(
            self.master, from_=0, to=100, orient=tk.HORIZONTAL, command=self.on_scroll
        )
        self.scrollbar.pack(fill=tk.X, pady=5)

        # Set up the button frame
        self.button_frame = tk.Frame(self.master)
        self.button_frame.pack(fill=tk.X, pady=5)

        # Add navigation buttons to the button frame
        self.prev_button = tk.Button(self.button_frame, text="Previous", command=self.show_previous_frame)
        self.prev_button.pack(side=tk.LEFT, padx=10)

        self.start_stop_button = tk.Button(self.button_frame, text="Start", command=self.toggle_playback)
        self.start_stop_button.pack(side=tk.LEFT, padx=10)

        self.next_button = tk.Button(self.button_frame, text="Next", command=self.show_next_frame)
        self.next_button.pack(side=tk.RIGHT, padx=10)

        # Playback and file properties
        self.video = None
        self.slices = None
        self.current_frame_index = 0
        self.total_frames = 0
        self.is_playing = False

        # Determine the file type and load the appropriate file
        _, ext = os.path.splitext(file_path)
        if ext.lower() == ".nii":
            self.load_nii_file(file_path)
        else:
            self.load_video(file_path)


    def load_nii_file(self, file_path):
        """Load a .nii file and extract slices."""
        try:
            # Load the NIfTI file
            nii_image = nib.load(file_path)
            nii_data = nii_image.get_fdata()  # Extract the 3D image data
            
            # Convert the 3D volume into a list of 2D slices (assuming axial view)
            self.slices = [nii_data[:, :, i] for i in range(nii_data.shape[2])]
            self.total_frames = len(self.slices)
            self.current_frame_index = 0

            # Normalize the pixel values for visualization (0-255)
            self.slices = [(slice_ - slice_.min()) / (slice_.max() - slice_.min()) * 255 for slice_ in self.slices]

            print(f"Loaded .nii file: {file_path}, Total Slices: {self.total_frames}")

            # Configure the scrollbar
            self.scrollbar.config(to=self.total_frames - 1)

            # Display the first slice
            self.show_frame(0)
        except Exception as e:
            print(f"Error loading .nii file: {e}")


    def load_video(self, video_path):
        """Load a video file and initialize frame navigation."""
        if self.video:
            self.video.release()

        self.video = cv2.VideoCapture(video_path)
        if not self.video.isOpened():
            print(f"Error: Couldn't open the video {video_path}.")
            return

        # Get video details
        self.video_width = int(self.video.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.video_height = int(self.video.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = int(self.video.get(cv2.CAP_PROP_FPS)) or 30
        self.delay = int(1000 / self.fps)
        self.total_frames = int(self.video.get(cv2.CAP_PROP_FRAME_COUNT))

        # Configure the scrollbar
        self.scrollbar.config(to=self.total_frames - 1)

        print(f"Loaded video: {video_path}, Dimensions: {self.video_width}x{self.video_height}, Total Frames: {self.total_frames}")

        # Show the first frame
        self.show_frame(0)

        

    def play_video(self):
        """Play video frames sequentially."""
        if not self.is_playing:
            return  # Stop playback if not in play mode

        ret, frame = self.video.read()
        if not ret:
            # Stop playback if we reach the end of the video
            self.is_playing = False
            self.start_stop_button.config(text="Start")
            return

        # Display the current frame
        frame_index = int(self.video.get(cv2.CAP_PROP_POS_FRAMES)) - 1
        self.show_frame(frame_index)

        # Update the scrollbar position
        self.scrollbar.set(frame_index)

        # Schedule the next frame based on the video FPS
        self.master.after(self.delay, self.play_video)


    def toggle_playback(self):
        """Toggle between Start and Stop."""
        self.is_playing = not self.is_playing  # Toggle play state
        if self.is_playing:
            self.start_stop_button.config(text="Stop")
            self.play_video()  # Start playback
        else:
            self.start_stop_button.config(text="Start")


    def on_scroll(self, value):
        """Handle scrollbar movement."""
        frame_index = int(float(value))
        self.show_frame(frame_index)
        self.is_playing = False  # Pause playback when seeking
        self.start_stop_button.config(text="Start")  # Update the button to reflect paused state


    def resize_frame(self, frame):
        """Resize the frame to fit the screen while maintaining aspect ratio."""
        # Calculate the screen size (80% of the screen for better visibility)
        max_width = int(self.master.winfo_screenwidth() * 0.8)
        max_height = int(self.master.winfo_screenheight() * 0.8)

        # Get the original aspect ratio
        aspect_ratio = self.video_width / self.video_height

        # Calculate the new dimensions while maintaining the aspect ratio
        if max_width / aspect_ratio <= max_height:
            new_width = max_width
            new_height = int(max_width / aspect_ratio)
        else:
            new_height = max_height
            new_width = int(max_height * aspect_ratio)

        # Resize the frame
        return cv2.resize(frame, (new_width, new_height)), new_width, new_height


    def show_frame(self, frame_index):
        """Show the frame (or slice) at the specified index."""
        if 0 <= frame_index < self.total_frames:
            if hasattr(self, 'slices'):  # Check if it's a .nii file with slices
                slice_ = self.slices[frame_index]
                img = Image.fromarray(slice_.astype('uint8')).convert('L')  # Convert to grayscale image
                new_width, new_height = img.size  # Get dimensions for layout adjustment
            else:
                # Regular video frame handling
                self.video.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                ret, frame = self.video.read()
                if not ret:
                    print(f"Failed to read frame at index {frame_index}.")
                    return
                frame_resized, new_width, new_height = self.resize_frame(frame)
                frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb)

            # Adjust the layout window size based on the frame size
            self.master.geometry(f"{new_width}x{new_height + 150}")  # Add space for buttons and scrollbar

            # Display the image on the canvas
            self.current_frame_image = ImageTk.PhotoImage(image=img)
            self.canvas.config(width=new_width, height=new_height)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.current_frame_image)
            self.current_frame_index = frame_index
        else:
            print("Frame index out of range.")



    def show_next_frame(self):
        """Show the next frame."""
        if self.current_frame_index + 1 < self.total_frames:
            self.show_frame(self.current_frame_index + 1)
        else:
            print("Already at the last frame.")

    def show_previous_frame(self):
        """Show the previous frame."""
        if self.current_frame_index > 0:
            self.show_frame(self.current_frame_index - 1)
        else:
            print("Already at the first frame.")


class DirectoryWatcher(FileSystemEventHandler):
    def __init__(self, directory):
        self.directory = directory
        self.tk_instance = None
        self.video_player = None

    def is_file_ready(self, file_path):
        """Check if the file is fully written and ready to be opened."""
        try:
            with open(file_path, 'rb'):
                return True
        except IOError:
            return False

    def on_created(self, event):
        """Triggered when a new file is created in the directory."""
        if event.is_directory:
            return
        _, ext = os.path.splitext(event.src_path)
        if ext.lower() in [".mp4", ".avi", ".mov", ".mkv", ".nii"]:  # Add .nii extension
            print(f"New file detected: {event.src_path}")
            for _ in range(10):  # Retry up to 10 times
                if self.is_file_ready(event.src_path):
                    self.show_file(event.src_path)
                    return
                time.sleep(1)
            print(f"Error: The file {event.src_path} is not ready or is corrupted.")


    def show_file(self, file_path):
        """Create or update the frame loader with a new video or .nii file."""
        if not self.tk_instance:
            self.tk_instance = tk.Tk()
            self.video_player = VideoPlayer(self.tk_instance, file_path)
            self.tk_instance.mainloop()
        else:
            _, ext = os.path.splitext(file_path)
            if ext.lower() == ".nii":
                self.video_player.load_nii_file(file_path)
            else:
                self.video_player.load_video(file_path)


def main():
    """Main function to start watching the directory."""
    # Hardcoded directory path to watch
    directory = "/home/hagai-stavi/Desktop/PythonProjects/VideoScrolling"
    print(f"Watching directory: {directory}")

    # Start watching the directory
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
    main()
