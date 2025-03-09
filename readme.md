# Trimmer utility

This is a small frontend for the `ffmpeg` utility for batch processing of the video files.
It allows you to select streams you want to keep (using manual section or filters)
and then transcode them to a new file.
By default, utility will try to re-encode video streams to H.265/HEVC codec
using `libx265` or any available hardware encoder (e.g. `hevc_nvenc` for NVIDIA GPUs).

<details>
  <summary>Screenshots</summary>
  <p align="center">
    <img src=https://github.com/Coestaris/trimmer/blob/main/screenshots/1.png width="350">
    <img src=https://github.com/Coestaris/trimmer/blob/main/screenshots/2.png width="350">
    <img src=https://github.com/Coestaris/trimmer/blob/main/screenshots/3.png width="350">
  </p>
</details>

Requirements:
- Python 3.8 or newer with pip: https://www.python.org/downloads/
- ffmpeg/ffprobe (should be available in the system PATH): https://ffmpeg.org/download.html

Supported containers:
- MKV (tested)
- MP4 (not tested)
- AVI (not tested)
- MOV (not tested)
- M2TS (tested)

Supported codecs:
- libx265 (tested)
- hevc_nvenc (tested)
- hevc_videotoolbox (tested)

### Linux/MacOS setup guide:

1. Install Python 3.8 or newer and `ffmpeg` utility (using your package manager or directly from the website)
2. Clone the repository and install the dependencies:
```bash
git clone https://github.com/Coestaris/trimmer
cd trimmer
python3 -m venv .venv
.venv/bin/pip3 install -r requirements.txt
```
3. Run the utility:
```bash
.venv/bin/python __main__.py
```
### Windows 10 or newer setup guide:

1. Download and install Python 3.8 or newer from the official website. Make sure to check the 'Add Python to the environment variables' option during the installation 
2. Download and install `ffmpeg` utility from the official website
3. Download the utility from the repository: https://github.com/Coestaris/trimmer/archive/refs/heads/main.zip
4. Run the `trimmer.bat` file. Note that the first run may take some time to install the dependencies
