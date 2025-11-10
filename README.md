# PhotoFlow v2.0.0

A robust photo ingestion and processing utility for photographers using Linux.

---

## What is PhotoFlow?

PhotoFlow is a GTK4 desktop application designed to streamline the first, most tedious step of a photography workflow: getting photos off your camera card and into your archive.

It ingests new photos (JPEGs and RAWs), lets you rename and tag them, and then intelligently moves them to a final archive directory. As a bonus, it creates resized, auto-rotated, and tagged copies specifically for use in an [Obsidian](https://obsidian.md/) vault, perfect for daily journaling.

This application was forged in the fiery crucible of countless bugs and a whole lot of `exiftool`. It stands as a testament to the fact that if you debug something long enough, it might, eventually, work.

## Core Features

*   **Smart RAW+JPG Pairing**: Automatically detects and groups RAW and JPG files of the same photo, displaying them as a single item in the UI.
*   **Dual Workflow System**:
    *   **Batch Process**: Quickly rename, tag, and process a large selection of photos with common settings.
    *   **Individual Review**: A powerful, step-by-step window for assigning unique filenames, tags, comments, and GPS data to each photo.
*   **Obsidian Integration**: Creates date-based folders in your vault and copies a resized, auto-rotated, and fully tagged JPEG into them, ready to be linked in your notes.
*   **Robust Metadata Engine**: Uses `exiftool` to reliably write metadata (Tags, Comments, GPS) to JPG and DNG files.
*   **Persistent Tag History**: Remembers all your previously used tags and provides an auto-complete dropdown for faster, more consistent tagging.
*   **Modern GTK4 Interface**: A clean, theme-aware interface that looks great in both light and dark modes.
*   **Safe & Reliable File Handling**: Built with a robust processing pipeline that moves files to a temporary location first, ensuring no data is lost even if an error occurs.

---

## Installation

Tested on Pop!_OS 22.04 (Ubuntu-based).

### 1. System Dependencies

First, install the core libraries and tools the application depends on.

```bash
sudo apt update
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0
sudo apt install libimage-exiftool-perl
sudo apt install python3-pip
```

### 2. Python Libraries

Next, install the required Python packages using `pip`. It's recommended to do this from the project directory.

```bash
cd /path/to/PhotoFlow
pip install -r requirements.txt
```

### 3. Configuration (`config.ini`)

PhotoFlow requires a `config.ini` file in the root of the project directory. This file is ignored by Git for your safety. You must create it yourself.

Here is a template:
```ini
[Paths]
# Your main photo archive (e.g., an external drive).
DestinationDirectory = /media/user/PhotoArchive
# The target folder inside your Obsidian vault for pictures.
ObsidianVaultPicturesDirectory = /home/user/Documents/Obsidian/Vault/Attachments/Pictures
[Settings]
# The maximum width and height for the resized JPEGs for Obsidian.
ResizeWidth = 1600
ResizeHeight = 1600
```

### 4. Desktop Integration (Optional)

To make PhotoFlow appear as a native application in your desktop environment:

```bash
# Copy the icon
sudo cp /path/to/PhotoFlow/assets/photoflow.svg /usr/share/icons/hicolor/scalable/apps/com.crispi.photoflow.svg
# Update the icon cache
sudo gtk-update-icon-cache /usr/share/icons/hicolor/
# Copy the launcher to your local applications folder
cp /path/to/PhotoFlow/photoflow.desktop ~/.local/share/applications/
```

## How to Run

*   **From the App Menu**: After desktop integration, you can find "PhotoFlow" in your system's application launcher.
*   **From the Terminal**: For development or debugging, run:
    ```bash
    cd /path/to/PhotoFlow
    python3 gui.py
    ```

## Credits

*   **Forged by**: Crispi
*   **With the reluctant assistance of**: a slightly cynical AI (Gemini)
*   **License**: GPL-3.0
*   **© 2025 Crispi**