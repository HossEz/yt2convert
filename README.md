# yt2convert - YouTube to Audio & Video Converter

![yt2convert Screenshot](https://i.imgur.com/Wu1VBn9.png)

A modern desktop application to download and convert YouTube videos to high-quality audio files (MP3/WAV) or MP4 videos.

---

## Features

- **Easy to Use**: Just paste a URL and click download  
- **Multiple Formats**: Convert to MP3 (64-320 kbps), lossless WAV (16-32 bit), or MP4 (H.264, VP9 & AV1)  
- **Themes**: Choose from several themes (Midnight Blue, Pure Light, Forest)  
- **Download History**: Keep track of your converted files  
- **Metadata Tagging**: Automatic ID3 tags for MP3 files  
- **Auto Updates**: Get notified when new versions are available  

---

## Download

Get the latest version from the [Releases page](https://github.com/HossEz/yt2convert/releases).

---

## System Requirements
  
- Windows 10/11
- Internet connection
- Python 3.9 or newer
  - `.exe` version does not require a Python installation

---

## How to Use

1. Download & open the latest yt2convert.exe  
2. Paste a YouTube URL in the input field  
3. Select your preferred format and quality  
4. Click the Download button  
5. Find your converted files in the output folder  

---

## How This Works

This app uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) to download and extract audio or video from YouTube videos. It’s a reliable tool that handles most of the heavy lifting.

Also, yt-dlp needs `ffmpeg` to convert the files, but `ffmpeg` is already included with the `.exe` release, so you don’t have to install anything extra.

**Settings and history files** (`settings.json` and `history.json`) are saved in `%appdata%/yt2convert`.

---

## Setup and Build Instructions

For those who want to run the project directly with Python, or build their own `.exe`:

### Using `start.bat`

- Run `start.bat` to launch the Python script and install all required dependencies automatically.  
- During `start.bat` execution, make sure you have an `ffmpeg` executable in your system PATH or place `ffmpeg.exe` in the project folder. Both methods work fine when running the script this way.

### Using `build.bat`

- The `build.bat` script compiles the project into a standalone `.exe` file using PyInstaller.  
- To **include `ffmpeg.exe` inside the bundled executable**, you must have `ffmpeg.exe` present in the root project folder **before** running `build.bat`.  
- Merely having `ffmpeg` in your system PATH is **not sufficient** for bundling `ffmpeg` into the executable.  
- Running `start.bat` first *(just once)* is required to ensure the virtual environment and dependencies are set up correctly for building.

---

## License

This project is licensed under the MIT License. See the [LICENSE](./LICENSE.txt) file for details.
