import logging
import os
import subprocess

logger = logging.getLogger(__name__)


class ScreenAndAudioRecorder:
    def __init__(self, file_location):
        self.file_location = file_location
        self.ffmpeg_proc = None
        # Get actual screen dimensions instead of hardcoding
        import platform
        if platform.system() == "Windows":
            # On Windows, use a more reliable way to get screen dimensions
            try:
                import ctypes
                user32 = ctypes.windll.user32
                self.screen_dimensions = (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
                logger.info(f"Detected screen dimensions: {self.screen_dimensions}")
            except Exception as e:
                logger.error(f"Failed to get screen dimensions: {e}")
                # Fallback to a safe default for Windows
                self.screen_dimensions = (1280, 720)
        else:
            # Default for non-Windows systems
            self.screen_dimensions = (1920, 1080)

    def start_recording(self, display_var):
        logger.info(f"Starting screen recorder with dimensions {self.screen_dimensions} and file location {self.file_location}")
        
        # Create a test file to ensure the directory is writable
        try:
            os.makedirs(os.path.dirname(self.file_location), exist_ok=True)
            with open(self.file_location + ".test", "w") as f:
                f.write("test")
            os.remove(self.file_location + ".test")
            logger.info(f"Successfully verified that the directory is writable")
        except Exception as e:
            logger.error(f"Error verifying directory is writable: {e}")
        
        # Check operating system and use appropriate FFmpeg command
        import platform
        if platform.system() == "Windows":
            # Windows screen capture using gdigrab - with audio
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-thread_queue_size", "4096", 
                "-f", "gdigrab", "-framerate", "30", 
                "-video_size", f"{self.screen_dimensions[0]}x{self.screen_dimensions[1]}", 
                "-i", "desktop", 
                "-f", "dshow", "-i", "audio=Microphone (Realtek High Definition Audio)",
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", 
                "-g", "30", "-c:a", "aac", "-strict", "experimental", "-b:a", "128k",
                self.file_location
            ]
            
            # Note: We're removing the audio input and crop filter to ensure recording works
            # If you want to try with audio later, you can add these lines back:
            # "-f", "dshow", "-i", "audio=Microphone (Realtek High Definition Audio)",
            # "-c:a", "aac", "-strict", "experimental", "-b:a", "128k",
        else:
            # Original Linux x11grab command
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-thread_queue_size", "4096", "-framerate", "30", 
                "-video_size", f"{self.screen_dimensions[0]}x{self.screen_dimensions[1]}", 
                "-f", "x11grab", "-draw_mouse", "0", "-probesize", "32", 
                "-i", display_var, "-thread_queue_size", "4096", 
                "-f", "pulse", "-i", "default", 
                "-vf", "crop=1920:1080:10:10", 
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", 
                "-g", "30", "-c:a", "aac", "-strict", "experimental", "-b:a", "128k", 
                self.file_location
            ]

        logger.info(f"Starting FFmpeg command: {' '.join(ffmpeg_cmd)}")
        
        try:
            # Use subprocess.PIPE for stderr to capture FFmpeg output
            # In the start_recording method, modify the subprocess.Popen call:
            self.ffmpeg_proc = subprocess.Popen(
                ffmpeg_cmd, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,  # Add this line to make stdin accessible
                text=True,
                bufsize=1
            )
            
            # Start a thread to read and log FFmpeg output
            import threading
            def log_ffmpeg_output():
                for line in self.ffmpeg_proc.stderr:
                    logger.info(f"FFmpeg: {line.strip()}")
            
            threading.Thread(target=log_ffmpeg_output, daemon=True).start()
            
            # Check if process started successfully
            if self.ffmpeg_proc.poll() is not None:
                logger.error(f"FFmpeg process failed to start or exited immediately with code {self.ffmpeg_proc.returncode}")
            else:
                logger.info("FFmpeg process started successfully")
                
        except Exception as e:
            logger.error(f"Error starting FFmpeg: {e}")
            self.ffmpeg_proc = None

    def stop_recording(self):
        if not self.ffmpeg_proc:
            return
        
        # Send 'q' to FFmpeg to gracefully stop recording
        try:
            # Check if process is still running
            if self.ffmpeg_proc.poll() is None:
                # On Windows, we need to use communicate to send input
                import platform
                if platform.system() == "Windows":
                    # Create a thread to send 'q' to FFmpeg
                    import threading
                    def send_quit():
                        try:
                            # Send 'q' to stdin if possible
                            if hasattr(self.ffmpeg_proc, 'stdin') and self.ffmpeg_proc.stdin:
                                self.ffmpeg_proc.stdin.write('q')
                                self.ffmpeg_proc.stdin.flush()
                        except Exception as e:
                            logger.error(f"Error sending quit signal to FFmpeg: {e}")
                            # Fall back to terminate if sending 'q' fails
                            self.ffmpeg_proc.terminate()
                        
                    # Start thread to send quit signal
                    threading.Thread(target=send_quit).start()
                    
                    # Wait for process to exit with timeout
                    try:
                        self.ffmpeg_proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        logger.warning("FFmpeg didn't exit after 5 seconds, terminating")
                        self.ffmpeg_proc.terminate()
                        self.ffmpeg_proc.wait()
                else:
                    # On Unix systems, we can send SIGINT which is equivalent to pressing 'q'
                    import signal
                    self.ffmpeg_proc.send_signal(signal.SIGINT)
                    try:
                        self.ffmpeg_proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        logger.warning("FFmpeg didn't exit after 5 seconds, terminating")
                        self.ffmpeg_proc.terminate()
                        self.ffmpeg_proc.wait()
        except Exception as e:
            logger.error(f"Error stopping FFmpeg gracefully: {e}")
            # Fall back to terminate
            if self.ffmpeg_proc and self.ffmpeg_proc.poll() is None:
                self.ffmpeg_proc.terminate()
                self.ffmpeg_proc.wait()
        
        logger.info(f"Stopped debug screen recorder for display with dimensions {self.screen_dimensions} and file location {self.file_location}")

    def get_seekable_path(self, path):
        """Transform a file path to include '.seekable' before the extension.
        Example: /tmp/file.webm -> /tmp/file.seekable.webm
        """
        base, ext = os.path.splitext(path)
        return f"{base}.seekable{ext}"

    def cleanup(self):
        input_path = self.file_location

        # Check if input file exists
        if not os.path.exists(input_path):
            logger.info(f"Input file does not exist at {input_path}, creating empty file")
            with open(input_path, "wb"):
                pass  # Create empty file
            return

        # if input file is greater than 3 GB, we will skip seekability
        if os.path.getsize(input_path) > 3 * 1024 * 1024 * 1024:
            logger.info("Input file is greater than 3 GB, skipping seekability")
            return

        output_path = self.get_seekable_path(self.file_location)
        # the file is seekable, so we don't need to make it seekable
        try:
            self.make_file_seekable(input_path, output_path)
        except Exception as e:
            logger.error(f"Failed to make file seekable: {e}")
            return

    def make_file_seekable(self, input_path, tempfile_path):
        """Use ffmpeg to move the moov atom to the beginning of the file."""
        logger.info(f"Making file seekable: {input_path} -> {tempfile_path}")
        # log how many bytes are in the file
        logger.info(f"File size: {os.path.getsize(input_path)} bytes")
        command = [
            "ffmpeg",
            "-i",
            str(input_path),  # Input file
            "-c",
            "copy",  # Copy streams without re-encoding
            "-avoid_negative_ts",
            "make_zero",  # Optional: Helps ensure timestamps start at or after 0
            "-movflags",
            "+faststart",  # Optimize for web playback
            "-y",  # Overwrite output file without asking
            str(tempfile_path),  # Output file
        ]

        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed to make file seekable: {result.stderr}")

        # Replace the original file with the seekable version
        try:
            os.replace(str(tempfile_path), str(input_path))
            logger.info(f"Replaced original file with seekable version: {input_path}")
        except Exception as e:
            logger.error(f"Failed to replace original file with seekable version: {e}")
            raise RuntimeError(f"Failed to replace original file: {e}")
