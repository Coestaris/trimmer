# Trimmer utility

This is a small frontend for the 'ffmpeg' utility for batch processing of the video files.
It allows you to select streams you want to keep (using manual section or filters)
and then transcode them to a new file.
By default, utility will try to re-encode video streams to H.265/HEVC codec
using 'libx265' or any available hardware encoder (e.g. 'hevc_nvenc' for NVIDIA GPUs).

Requirements:
- Python 3.8 or newer with pip: https://www.python.org/downloads/
- ffmpeg/ffprobe (should be available in the system PATH): https://ffmpeg.org/download.html

Supported containers:
- MKV (tested)
- MP4 (not tested)
- AVI (not tested)
- MOV (not tested)

Supported codecs:
- libx265 (tested)
- hevc_nvenc (tested)

### Linux/MacOS setup guide:

1. Install Python 3.8 or newer and 'ffmpeg' utility (using your package manager or directly from the website)
2. Clone the repository and install the dependencies:
```bash
git clone https://github.com/Coestaris/trimmer
cd trimmer
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
3. Run the utility:
```bash
python __main__.py
```
### Windows 10 or newer setup guide:

1. Download and install Python 3.8 or newer from the official website 
2. Download the 'ffmpeg' utility from the official website
3. Download the utility from the repository: https://github.com/Coestaris/trimmer/archive/refs/heads/main.zip
4. Extract the archive to any folder
5. Open the folder in the file manager
6. Hold 'Shift' and right-click on the empty space in the folder to open the context menu and select 'Open PowerShell window here'
7. Run the following commands in the PowerShell window:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
8. Run the utility:
```powershell
python __main__.py
```
or double-click on the `__main__.py` file