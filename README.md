PhotoFlow

"Because your photos weren't going to tag and rename themselves."

What Is This Thing?

PhotoFlow is a (surprisingly functional) GTK desktop application for Linux, born from a maddening series of bugs and a whole lot of exiftool. It's designed to be the first step in a serious photography workflow.

It ingests new photos (JPEGs and RAWs) from a source folder, lets you batch-rename and tag them, and then intelligently moves them to a final archive. As a bonus, it creates resized, auto-rotated, and tagged copies specifically for use in an Obsidian vault.

This application was forged in the fiery crucible of countless AttributeErrors, file corruptions, and one very stubborn PixbufLoader bug. It stands as a testament to the fact that if you debug something long enough, it might, eventually, work.

Core Features

Smart Grouping: Automatically detects and groups RAW+JPG pairs, displaying them as a single item in the UI.

Thumbnail Previews: Generates correctly-oriented thumbnails for all images, including tricky smartphone DNGs.

Dual Workflow:

Batch Process: Rename, tag, and process all selected photos in one go.

Individual Review: A step-by-step review window for adding individual filenames, tags, and (eventually) comments.

Persistent Tagging: Remembers all your tags and provides an auto-complete dropdown for faster, more consistent tagging.

Metadata Engine: Uses exiftool to robustly write metadata (Tags, Comments) to JPG, DNG, and the resized JPG copies.

Obsidian Integration: Creates date-based folders in your vault and copies a resized, auto-rotated, and tagged JPEG into them, ready to be linked in your notes.

Safe File Handling: Safely moves files across different hard drives (e.g., from an SSD to an external archive drive) without crashing.

Installation (For the "Eventual User")

This app was built on Pop!_OS (Ubuntu-based).

1. Dependencies (The System Stuff)

You need to install the core libraries this app depends on.

sudo apt update
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0
sudo apt install libimage-exiftool-perl imagemagick libheif-dev
sudo apt install python3-pip


2. Python Libraries

Next, install the required Python packages using pip.

cd ~/apps/PhotoFlow
pip install -r requirements.txt


(This will install Pillow, rawpy, and pillow-heif.)

3. Configuration (The config.ini)

This app is useless without a config.ini file. This file is ignored by Git for your safety. You must create it yourself in the ~/apps/PhotoFlow directory.

File: config.ini

[Paths]
# The folder where your new photos are (e.g., /home/user/Downloads).
SourceDirectory = /home/crispi/Downloads

# Your main photo archive (e.g., an external drive).
DestinationDirectory = /media/crispi/Seagate/Photo Archive

# The target folder inside your Obsidian vault.
ObsidianVaultPicturesDirectory = /home/crispi/Documents/Obsidian/Encyclopedia Crispianus/99_Attachments/Pictures/Daily

[Settings]
# The maximum width and height for the resized JPEGs for Obsidian.
ResizeWidth = 1600
ResizeHeight = 1600


4. Desktop Integration (The Icon)

To make it a "real" app:

Copy the Icon:

sudo cp ~/apps/PhotoFlow/assets/photoflow.svg /usr/share/icons/hicolor/scalable/apps/com.crispi.photoflow.svg


Update the Cache:

sudo gtk-update-icon-cache /usr/share/icons/hicolor/


Copy the Launcher:

cp ~/apps/PhotoFlow/photoflow.desktop ~/.local/share/applications/


How to Run

After installing, you can find "PhotoFlow" in your "Show Applications" menu.

To run it from the terminal for debugging:

cd ~/apps/PhotoFlow
python3 gui.py


Credits

Forged by: Crispi

With the reluctant assistance of: a slightly cynical AI (Gemini)

© 2025 Crispi