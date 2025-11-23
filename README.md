# Terminal Video Player

## What is it?

Terminal Video Player is a Python-based application that allows you to play videos directly in your terminal. The application will try to play the video at its original framerate, but don't be surprised if the video plays at a slower speed. The terminal is not designed to play videos after all. This project is an experiment.

## How to use it

To play a video, run the `main.py` script from your terminal and provide the path to your video file.

### Basic Usage
```bash
python main.py /path/to/your/video.mp4
```

### Options

- **Size**: Adjust the size of the video element. Defaults to 32.
  ```bash
  python main.py /path/to/your/video.mp4 --size 64
  ```

- **Mute Audio**: Mute the audio playback.
  ```bash
  python main.py /path/to/your/video.mp4 --muted
  ```

- **Video Compression**: How much the colors are compressed in the video playback. Improves playback performance but degrades video quality. Defaults to 150.
  ```bash
  python main.py /path/to/your/video.mp4 --compression 100
  ```

- **Debug Mode**: Opens a second terminal that shows debug information and runs the program with the profiler enabled.
  ```bash
  python main.py /path/to/your/video.mp4 --debug
  ```
