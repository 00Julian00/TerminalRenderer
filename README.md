# Terminal Video Player

## What is it?

Terminal Video Player is a Python-based application that allows you to play videos directly in your terminal. Includes an optional ASCII mode. The application will try to play the video at its original framerate, but
don't be surprised if the video plays at a slower speed. The terminal is not designed to play videos after all. This project is an experiment and is under active development.

## How to use it

To play a video, run the `main.py` script from your terminal and provide the path to your video file. IMPORTANT: You need to have a C compiler installed for this project to run.

### Basic Usage
```bash
python main.py /path/to/your/video.mp4
```

### Options

- **ASCII Mode**: Render the video using ASCII characters instead of colored blocks.
  ```bash
  python main.py /path/to/your/video.mp4 --ascii
  ```

- **Size**: Adjust the size of the video element. The default is 32.
  ```bash
  python main.py /path/to/your/video.mp4 --size 64
  ```

- **Debug Overlay**: Show a debug overlay with coordinates and FPS. Also opens a second terminal that shows additional debug information.
  ```bash
  python main.py /path/to/your/video.mp4 --debug
  ```

You can also combine these options:
```bash
python main.py /path/to/your/video.mp4 --ascii --size 64 --debug
```

## Video Preprocessing

For improved playback performance, you can preprocess videos before playing them. Preprocessing converts the video into an optimized format that contains precomputed terminal rendering sequences, significantly reducing CPU usage during playback, allowing for playing back videos at a much higher resolution at the original refresh rate.

### How to Preprocess a Video

Use the `video_preprocessor.py` script to preprocess your video:

```bash
python video_preprocessor.py /path/to/your/video.mp4
```

This will create a `processed_video.pkl` file in the same directory as your source video.

### Preprocessing Options

The preprocessor accepts the same options as the main player:

- **ASCII Mode**: Preprocess the video with ASCII rendering
  ```bash
  python video_preprocessor.py /path/to/your/video.mp4 --ascii
  ```

- **Size**: Set the video width during preprocessing (default: 32)
  ```bash
  python video_preprocessor.py /path/to/your/video.mp4 --size 64
  ```

You can combine these options:
```bash
python video_preprocessor.py /path/to/your/video.mp4 --ascii --size 64
```

### Playing Preprocessed Videos

Once preprocessed, simply pass the `.pkl` file to the main player:

```bash
python main.py /path/to/processed_video.pkl
```

The player automatically detects preprocessed videos and plays them using the optimized rendering path. Note that `--ascii` and `--size` options are not applicable when playing preprocessed videos, as these settings are baked into the preprocessed file.
The `--debug` option will furthermore not show the debug overlay when playing back a preprocessed video, instead just launching the debug terminal and running the profiler.

### Benefits of Preprocessing

- **Better Performance**: Reduced CPU usage during playback since frames are precomputed
- **Smoother Playback**: More consistent frame timing, especially for complex videos
- **Trade-off**: Preprocessing takes time upfront and creates larger files, but provides much faster playback
