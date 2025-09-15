# yt2convert - YouTube to Audio Converter

![yt2convert Screenshot](https://i.imgur.com/Wu1VBn9.png)

A modern desktop application to download and convert YouTube videos to high-quality audio files (MP3/WAV).

## Features

- **Easy to Use**: Just paste a URL and click download
- **Multiple Formats**: Convert to MP3 (64-320 kbps) or lossless WAV (16-32 bit)
- **Themes**: Choose from a few themes (Midnight Blue, Pure Light, Forest)
- **Auto Updates**: Get notified when new versions are available
- **Download History**: Keep track of your converted files
- **Metadata Tagging**: Automatic ID3 tags for MP3 files

## Download

Get the latest version from the [Releases page](https://github.com/HossEz/yt2convert/releases).

## How to Use

1. Download & open the latest yt2convert.exe
2. Paste a YouTube URL in the input field
3. Select your preferred format and quality
4. Click the Download button
5. Find your converted files in the output folder

## How This Works

This app uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) to download and extract audio from YouTube videos. It’s a reliable tool that handles most of the heavy lifting.  
Also, yt-dlp needs `ffmpeg` to convert the files, but `ffmpeg` is already included with the `.exe` release, so you don’t have to install anything extra.


## Additional

If you want to build it yourself, just run the build.bat file. You can also use start.bat to start the Python script; it will install all the required dependencies and launch the script. Make sure ffmpeg is either in your system PATH or in the same folder as the script. *(Note: Ffmpeg is already bundled with the .exe version.)*
