#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio, GdkPixbuf, GLib, Gdk
import os
from pathlib import Path
import threading
from PIL import Image, ImageOps
import io
import subprocess
import configparser

# Import our backend engine
import photoflow as core_engine

SUPPORTED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.dng']
RAW_EXTENSIONS = ['.dng']

class ThumbnailWidget(Gtk.Box):
    def __init__(self, pixbuf, filename, badge_text=None, jpg_path=None, raw_path=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add_css_class("thumbnail-widget")
        self.jpg_path = jpg_path
        self.raw_path = raw_path
        overlay = Gtk.Overlay()
        image = Gtk.Image.new_from_pixbuf(pixbuf)
        overlay.set_child(image)
        if badge_text:
            badge = Gtk.Label.new(badge_text)
            badge.add_css_class("thumbnail-badge")
            badge.set_halign(Gtk.Align.END)
            badge.set_valign(Gtk.Align.END)
            badge.set_margin_end(4)
            badge.set_margin_bottom(4)
            overlay.add_overlay(badge)
        filename_label = Gtk.Label.new(filename)
        filename_label.set_wrap(True)
        self.append(overlay)
        self.append(filename_label)
    
    def set_display_size(self, size):
        self.get_first_child().get_child().set_pixel_size(size)

class PhotoFlowWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title("PhotoFlow")
        self.set_default_size(1200, 800)
        
        header = Gtk.HeaderBar()
        self.set_titlebar(header)
        
        menu = Gio.Menu()
        menu.append("Preferences", "app.preferences")
        menu.append("About", "app.about")
        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
        
        self.spinner = Gtk.Spinner()
        header.pack_start(self.spinner)
        
        self.size_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 64, 256, 8)
        self.size_slider.set_value(128)
        self.size_slider.set_draw_value(False)
        self.size_slider.set_size_request(150, -1)
        self.size_slider.connect("value-changed", self.on_thumbnail_size_changed)
        
        header.pack_start(self.size_slider)
        header.pack_end(menu_button)
        
        main_grid = Gtk.Grid(margin_start=12, margin_end=12, margin_top=12, margin_bottom=12, row_spacing=12, column_spacing=12)
        self.set_child(main_grid)
        
        scrolled_window = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.thumbnail_view = Gtk.FlowBox(valign=Gtk.Align.START, max_children_per_line=10, min_children_per_line=3, selection_mode=Gtk.SelectionMode.MULTIPLE)
        self.thumbnail_view.connect("selected-children-changed", self.on_selection_changed)
        scrolled_window.set_child(self.thumbnail_view)
        main_grid.attach(scrolled_window, 0, 1, 2, 1)
        
        self.source_button = Gtk.Button(label="Select Source Folder...")
        self.dest_button = Gtk.Button(label="Select Destination Folder...")
        self.source_button.connect('clicked', self.on_select_source_folder)
        main_grid.attach(self.source_button, 0, 0, 1, 1)
        main_grid.attach(self.dest_button, 1, 0, 1, 1)
        
        right_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, width_request=300)
        
        selection_info_frame = Gtk.Frame(label="Selection Info")
        self.selection_label = Gtk.Label.new("No images selected.")
        self.selection_label.set_wrap(True)
        self.selection_label.set_margin_start(12); self.selection_label.set_margin_end(12)
        self.selection_label.set_margin_top(6); self.selection_label.set_margin_bottom(12)
        selection_info_frame.set_child(self.selection_label)
        
        rename_frame = Gtk.Frame(label="Batch Renaming")
        rename_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_start=12, margin_end=12, margin_top=6, margin_bottom=12)
        self.rename_entry = Gtk.Entry(placeholder_text="Base Name (e.g., Belgium_Trip_)")
        self.rename_spinner = Gtk.SpinButton.new_with_range(1, 10000, 1)
        rename_box.append(self.rename_entry)
        rename_box.append(self.rename_spinner)
        rename_frame.set_child(rename_box)
        
        tags_frame = Gtk.Frame(label="Common Tags & Location")
        tags_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_start=12, margin_end=12, margin_top=6, margin_bottom=12)
        self.tags_entry = Gtk.Entry(placeholder_text="Enter tags, comma-separated...")
        self.gps_button = Gtk.Button(label="Add GPS Data...")
        tags_box.append(self.tags_entry)
        tags_box.append(self.gps_button)
        tags_frame.set_child(tags_box)
        
        self.obsidian_check = Gtk.CheckButton(label="Add to Obsidian Vault")
        self.obsidian_check.set_active(True)
        
        self.process_button = Gtk.Button(label="Process Files", css_classes=['suggested-action'])
        self.process_button.set_valign(Gtk.Align.END)
        self.process_button.set_vexpand(True)
        self.process_button.connect('clicked', self.on_process_files_clicked)
        
        right_panel.append(selection_info_frame)
        right_panel.append(rename_frame)
        right_panel.append(tags_frame)
        right_panel.append(self.obsidian_check)
        right_panel.append(self.process_button)
        main_grid.attach(right_panel, 2, 0, 1, 2)
        
    def on_process_files_clicked(self, widget):
        selected_flowbox_children = self.thumbnail_view.get_selected_children()
        if not selected_flowbox_children:
            print("No images selected to process.")
            return

        selection_data = []
        for child in selected_flowbox_children:
            thumb_widget = child.get_child()
            selection_data.append({
                'jpg_path': thumb_widget.jpg_path,
                'raw_path': thumb_widget.raw_path
            })
            
        config = configparser.ConfigParser()
        script_dir = Path(__file__).parent.resolve()
        config_file_path = script_dir / 'config.ini'
        
        if not config_file_path.exists():
            print(f"FATAL ERROR: config.ini not found at {config_file_path}")
            return
            
        config.read(config_file_path)
        
        settings = {
            'dest_dir': config.get('Paths', 'DestinationDirectory'),
            'obsidian_dir': config.get('Paths', 'ObsidianVaultPicturesDirectory'),
            'resize_w': config.getint('Settings', 'ResizeWidth'),
            'resize_h': config.getint('Settings', 'ResizeHeight'),
            'base_name': self.rename_entry.get_text(),
            'start_number': int(self.rename_spinner.get_value()),
            'tags': [tag.strip() for tag in self.tags_entry.get_text().split(',') if tag.strip()]
        }

        self.spinner.start()
        self.process_button.set_sensitive(False)
        thread = threading.Thread(target=self.processing_thread_worker, args=(selection_data, settings))
        thread.start()
        
    def processing_thread_worker(self, selection_data, settings):
        core_engine.process_photos(selection_data, settings)
        GLib.idle_add(self.on_processing_finished)

    def on_processing_finished(self):
        self.spinner.stop()
        self.process_button.set_sensitive(True)
        self.clear_thumbnails()
        print("UI updated after processing.")

    def on_selection_changed(self, flowbox, *args):
        selected_widgets = flowbox.get_selected_children()
        count = len(selected_widgets)
        if count == 0: 
            self.selection_label.set_text("No images selected.")
        elif count == 1:
            thumb_widget = selected_widgets[0].get_child()
            info_text = f"<b>Selected: {Path(thumb_widget.jpg_path or thumb_widget.raw_path).stem}</b>\\n"
            if thumb_widget.jpg_path: info_text += f"\\nJPG: {Path(thumb_widget.jpg_path).name}"
            if thumb_widget.raw_path: info_text += f"\\nRAW: {Path(thumb_widget.raw_path).name}"
            self.selection_label.set_markup(info_text)
        else: 
            self.selection_label.set_markup(f"<b>{count} images selected.</b>")

    def on_thumbnail_size_changed(self, slider):
        new_size = int(slider.get_value())
        i = 0
        while True:
            child = self.thumbnail_view.get_child_at_index(i)
            if not child: break
            thumbnail_widget = child.get_child()
            if isinstance(thumbnail_widget, ThumbnailWidget):
                thumbnail_widget.set_display_size(new_size)
            i += 1
            
    def on_select_source_folder(self, widget):
        dialog = Gtk.FileChooserDialog(title="Please choose a source folder", transient_for=self, action=Gtk.FileChooserAction.SELECT_FOLDER)
        dialog.add_buttons("_Cancel", Gtk.ResponseType.CANCEL, "_Open", Gtk.ResponseType.OK)
        dialog.connect("response", self.on_folder_dialog_response)
        dialog.present()
    
    def on_folder_dialog_response(self, dialog, response):
        if response == Gtk.ResponseType.OK:
            folder = dialog.get_file().get_path()
            self.load_thumbnails(folder)
        dialog.destroy()
    
    def load_thumbnails(self, folder_path):
        """Load and display thumbnails from the selected folder"""
        self.clear_thumbnails()
        
        # Start spinner to indicate loading
        self.spinner.start()
        
        # Load thumbnails in a separate thread to avoid blocking the UI
        thread = threading.Thread(target=self._load_thumbnails_worker, args=(folder_path,))
        thread.start()
    
    def _load_thumbnails_worker(self, folder_path):
        """Worker thread to load thumbnails"""
        try:
            image_files = []
            folder = Path(folder_path)
            
            # Find all supported image files
            for ext in SUPPORTED_EXTENSIONS:
                image_files.extend(folder.glob(f'*{ext}'))
                image_files.extend(folder.glob(f'*{ext.upper()}'))
            
            # Group files by base name (for JPG+RAW pairs)
            file_groups = {}
            for file_path in image_files:
                base_name = file_path.stem
                if base_name not in file_groups:
                    file_groups[base_name] = {'jpg': None, 'raw': None}
                
                if file_path.suffix.lower() in ['.jpg', '.jpeg']:
                    file_groups[base_name]['jpg'] = file_path
                elif file_path.suffix.lower() in RAW_EXTENSIONS:
                    file_groups[base_name]['raw'] = file_path
            
            # Create thumbnails for each group
            for base_name, files in file_groups.items():
                # Use JPG for thumbnail if available, otherwise RAW
                display_file = files['jpg'] or files['raw']
                if display_file:
                    try:
                        # Create thumbnail
                        pixbuf = self._create_thumbnail(display_file)
                        
                        # Determine badge text
                        badge_text = None
                        if files['jpg'] and files['raw']:
                            badge_text = "JPG+RAW"
                        elif files['raw']:
                            badge_text = "RAW"
                        
                        # Create thumbnail widget and add to UI (must be done in main thread)
                        GLib.idle_add(self._add_thumbnail_to_ui, pixbuf, base_name, badge_text, 
                                    str(files['jpg']) if files['jpg'] else None,
                                    str(files['raw']) if files['raw'] else None)
                    except Exception as e:
                        print(f"Error creating thumbnail for {display_file}: {e}")
            
            # Stop spinner when done
            GLib.idle_add(self.spinner.stop)
            
        except Exception as e:
            print(f"Error loading thumbnails: {e}")
            GLib.idle_add(self.spinner.stop)
    
    def _create_thumbnail(self, image_path, size=128):
        """Create a thumbnail pixbuf from an image file"""
        try:
            # Use PIL to create thumbnail
            with Image.open(image_path) as img:
                # Auto-orient the image
                img = ImageOps.exif_transpose(img)
                
                # Create thumbnail
                img.thumbnail((size, size), Image.Resampling.LANCZOS)
                
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Convert PIL image to GdkPixbuf
                img_bytes = io.BytesIO()
                img.save(img_bytes, format='PNG')
                img_bytes.seek(0)
                
                pixbuf = GdkPixbuf.Pixbuf.new_from_stream(
                    Gio.MemoryInputStream.new_from_bytes(GLib.Bytes(img_bytes.getvalue())),
                    None
                )
                return pixbuf
        except Exception as e:
            print(f"Error creating thumbnail: {e}")
            # Return a default pixbuf or None
            return None
    
    def _add_thumbnail_to_ui(self, pixbuf, filename, badge_text, jpg_path, raw_path):
        """Add thumbnail widget to the UI (called from main thread)"""
        if pixbuf:
            thumbnail_widget = ThumbnailWidget(pixbuf, filename, badge_text, jpg_path, raw_path)
            self.thumbnail_view.append(thumbnail_widget)
    
    def clear_thumbnails(self):
        """Clear all thumbnails from the view"""
        while True:
            child = self.thumbnail_view.get_first_child()
            if not child:
                break
            self.thumbnail_view.remove(child)


class PhotoFlowApp(Gtk.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect('activate', self.on_activate)
    
    def on_activate(self, app):
        self.win = PhotoFlowWindow(application=app)
        self.win.present()


if __name__ == '__main__':
    app = PhotoFlowApp()
    app.run()