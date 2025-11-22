# Terminal Video Player

## What is it?

Terminal Video Player is a Python-based application that allows you to play videos directly in your terminal. The application will try to play the video at its original framerate, but don't be surprised if the video plays at a slower speed. The terminal is not designed to play videos after all. This project is an experiment and is under active development.

## How to use it

To play a video, run the `main.py` script from your terminal and provide the path to your video file. IMPORTANT: You need to have a C compiler installed for this project to run.

### Basic Usage
```bash
python main.py /path/to/your/video.mp4
```

### Options

- **Size**: Adjust the size of the video element. The default is 32.
  ```bash
  python main.py /path/to/your/video.mp4 --size 64
  ```

- **Debug Mode**: Opens a second terminal that shows debug information and runs the program with the profiler enabled.
  ```bash
  python main.py /path/to/your/video.mp4 --debug
  ```