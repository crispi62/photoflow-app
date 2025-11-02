#!/usr/bin/env python3
import subprocess
import json
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageOps
import shutil
import io
import os # Import os for os.remove

RAW_EXTENSIONS = ['.dng']

def run_exiftool(args):
    try:
        command = ['exiftool'] + args
        command.insert(1, "-m") # Ignore minor errors
        subprocess.run(command, check=True, text=True, capture_output=True)
        return True
    except FileNotFoundError:
        print("❌ ERROR: 'exiftool' command not found.")
        return False
    except subprocess.CalledProcessError as e:
        if "Warning:" in e.stderr and "Error:" not in e.stderr:
            print(f"✅ ExifTool completed with warnings.")
            return True
        print(f"❗️ ExifTool Error: {e.stderr}")
        return False

def get_exif_date(file_path):
    try:
        command = ['exiftool', '-json', '-DateTimeOriginal', str(file_path)]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        metadata = json.loads(result.stdout)[0]
        date_str = metadata.get('DateTimeOriginal')
        if date_str:
            return datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
    except Exception:
        return datetime.fromtimestamp(file_path.stat().st_mtime)
    return datetime.now()

def safe_move(src_path, dest_path):
    """Safely moves a file, even across different filesystems."""
    try:
        shutil.copy(src_path, dest_path)
        os.remove(src_path)
    except Exception as e:
        print(f"❗️ Error moving file {src_path.name}: {e}")

def process_photos(selection_data, settings):
    """Processes photos using only the main batch settings."""
    print("\n--- Starting Batch Processing Workflow ---")
    
    base_name = settings['base_name']
    start_number = settings['start_number']
    tags = settings['tags']
    
    dest_dir = Path(settings['dest_dir'].strip(' "'))
    obsidian_dir = Path(settings['obsidian_dir'].strip(' "'))
    
    for i, item in enumerate(selection_data):
        current_number = start_number + i
        path_for_meta = Path(item['raw_path'] or item['jpg_path'])
        print(f"\nProcessing {path_for_meta.name}...")

        creation_date = get_exif_date(path_for_meta)
        year = creation_date.strftime('%Y')
        month_name = creation_date.strftime('%B')
        day_folder = creation_date.strftime('%d-%A')

        new_base_name = f"{base_name}{current_number:03d}"
        final_dest_dir = dest_dir / year / month_name / day_folder
        obsidian_dest_dir = obsidian_dir / year / month_name / day_folder
        final_dest_dir.mkdir(parents=True, exist_ok=True)
        obsidian_dest_dir.mkdir(parents=True, exist_ok=True)
        
        resized_name = f"{new_base_name}-R.jpg"
        resized_path_obsidian = obsidian_dest_dir / resized_name
        
        try:
            img_data = None
            if path_for_meta.suffix.lower() in RAW_EXTENSIONS:
                command = ['exiftool', '-b', '-PreviewImage', str(path_for_meta)]
                result = subprocess.run(command, capture_output=True, check=True)
                img_data = result.stdout
            else:
                with open(path_for_meta, 'rb') as f: img_data = f.read()
            if img_data:
                with Image.open(io.BytesIO(img_data)) as img:
                    img = ImageOps.exif_transpose(img)
                    img.thumbnail((settings['resize_w'], settings['resize_h']))
                    img.save(resized_path_obsidian, 'JPEG', quality=85)
                    print(f"🖼️  Created Obsidian file: {resized_path_obsidian}")
            else: raise ValueError("Could not extract image data.")
        except Exception as e:
            print(f"❗️ Error resizing {path_for_meta.name}: {e}")
            continue

        files_to_tag = []
        if item['jpg_path']: files_to_tag.append(item['jpg_path'])
        if item['raw_path']: files_to_tag.append(item['raw_path'])
        
        if tags and files_to_tag:
            print(f"✍️  Writing tags: {', '.join(tags)}")
            for file_to_tag in files_to_tag:
                tag_args = ['-overwrite_original']
                for tag in tags:
                    tag_args.append(f'-xmp:subject+={tag}')
                tag_args.append(file_to_tag)
                run_exiftool(tag_args)

        print("✍️  Copying metadata to resized file...")
        copy_meta_args = ['-overwrite_original', '-tagsFromFile', str(path_for_meta), '-all:all', str(resized_path_obsidian)]
        run_exiftool(copy_meta_args)

        print("🚚 Moving files to final destination...")
        if item['jpg_path']:
            p = Path(item['jpg_path'])
            safe_move(p, final_dest_dir / f"{new_base_name}{p.suffix}")
        if item['raw_path']:
            p = Path(item['raw_path'])
            safe_move(p, final_dest_dir / f"{new_base_name}{p.suffix}")
        shutil.copy(resized_path_obsidian, final_dest_dir / resized_path_obsidian.name)

    print("\n🎉 Workflow complete!")

def process_photos_individual(review_data, settings):
    """Processes photos using the detailed data from the Review Window."""
    print("\n--- Starting Individual Processing Workflow ---")
    
    common_tags = settings['tags']
    dest_dir = Path(settings['dest_dir'].strip(' "'))
    obsidian_dir = Path(settings['obsidian_dir'].strip(' "'))
    
    for item in review_data:
        path_for_meta = Path(item['raw_path'] or item['jpg_path'])
        print(f"\nProcessing {path_for_meta.name}...")

        creation_date = get_exif_date(path_for_meta)
        year = creation_date.strftime('%Y')
        month_name = creation_date.strftime('%B')
        day_folder = creation_date.strftime('%d-%A')

        new_base_name = item['user_filename']
        final_dest_dir = dest_dir / year / month_name / day_folder
        obsidian_dest_dir = obsidian_dir / year / month_name / day_folder
        final_dest_dir.mkdir(parents=True, exist_ok=True)
        obsidian_dest_dir.mkdir(parents=True, exist_ok=True)
        
        resized_name = f"{new_base_name}-R.jpg"
        resized_path_obsidian = obsidian_dest_dir / resized_name
        
        try:
            img_data = None
            if path_for_meta.suffix.lower() in RAW_EXTENSIONS:
                command = ['exiftool', '-b', '-PreviewImage', str(path_for_meta)]
                result = subprocess.run(command, capture_output=True, check=True)
                img_data = result.stdout
            else:
                with open(path_for_meta, 'rb') as f: img_data = f.read()
            if img_data:
                with Image.open(io.BytesIO(img_data)) as img:
                    img = ImageOps.exif_transpose(img)
                    img.thumbnail((settings['resize_w'], settings['resize_h']))
                    img.save(resized_path_obsidian, 'JPEG', quality=85)
                    print(f"🖼️  Created Obsidian file: {resized_path_obsidian}")
            else: raise ValueError("Could not extract image data.")
        except Exception as e:
            print(f"❗️ Error resizing {path_for_meta.name}: {e}")
            continue

        specific_tags = [t.strip() for t in item['user_tags'].split(',') if t.strip()]
        all_tags = list(set(common_tags + specific_tags))
        user_comment = item['user_comment']

        files_to_process_meta = []
        if item['jpg_path']: files_to_process_meta.append(item['jpg_path'])
        if item['raw_path']: files_to_process_meta.append(item['raw_path'])
        
        for file_to_process in files_to_process_meta:
            meta_args = ['-m', '-overwrite_original']
            if all_tags:
                print(f"✍️  Writing tags to {Path(file_to_process).name}: {', '.join(all_tags)}")
                for tag in all_tags:
                    meta_args.append(f'-xmp:subject+={tag}')
            
            if user_comment and Path(file_to_process).suffix.lower() in ['.jpg', '.jpeg']:
                print(f"✍️  Writing comment to {Path(file_to_process).name}...")
                meta_args.append(f'-XMP:UserComment={user_comment}')

            if len(meta_args) > 2: 
                meta_args.append(file_to_process)
                run_exiftool(meta_args)

        print("✍️  Copying metadata to resized file...")
        copy_meta_args = ['-m', '-overwrite_original', '-tagsFromFile', str(path_for_meta), '-all:all', str(resized_path_obsidian)]
        run_exiftool(copy_meta_args)

        print("🚚 Moving files to final destination...")
        if item['jpg_path']:
            p = Path(item['jpg_path'])
            safe_move(p, final_dest_dir / f"{new_base_name}{p.suffix}")
        if item['raw_path']:
            p = Path(item['raw_path'])
            safe_move(p, final_dest_dir / f"{new_base_name}{p.suffix}")
        shutil.copy(resized_path_obsidian, final_dest_dir / resized_path_obsidian.name)

    print("\n🎉 Workflow complete!")