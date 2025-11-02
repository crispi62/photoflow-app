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
            badge.set_halign(Gtk.Align.END); badge.set_valign(Gtk.Align.END)
            badge.set_margin_end(4); badge.set_margin_bottom(4)
            overlay.add_overlay(badge)
        filename_label = Gtk.Label.new(filename)
        filename_label.set_wrap(True)
        self.append(overlay)
        self.append(filename_label)
    
    def set_display_size(self, size):
        self.get_first_child().get_child().set_pixel_size(size)

class ReviewWindow(Gtk.Window):
    def __init__(self, parent, selection_data, common_tags):
        super().__init__(title="Individual Review", transient_for=parent, modal=True)
        self.selection_data = selection_data
        self.common_tags = common_tags
        self.current_index = 0
        self.set_default_size(1000, 700)
        main_grid = Gtk.Grid(margin_start=12, margin_end=12, margin_top=12, margin_bottom=12, row_spacing=12, column_spacing=12)
        self.set_child(main_grid)
        self.preview_image = Gtk.Picture()
        self.preview_image.set_hexpand(True); self.preview_image.set_vexpand(True)
        self.preview_image.set_css_classes(['view'])
        main_grid.attach(self.preview_image, 0, 0, 1, 1)
        right_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, width_request=300)
        main_grid.attach(right_panel, 1, 0, 1, 1)
        filename_frame = Gtk.Frame(label="Filename")
        self.filename_entry = Gtk.Entry()
        filename_frame.set_child(self.filename_entry)
        right_panel.append(filename_frame)
        tags_frame = Gtk.Frame(label="Tags")
        tags_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_start=12, margin_end=12, margin_top=6, margin_bottom=12)
        tags_box.append(Gtk.Label.new(f"Common: {', '.join(common_tags)}"))
        tags_box.append(Gtk.Entry(placeholder_text="Add specific tags..."))
        tags_frame.set_child(tags_box)
        right_panel.append(tags_frame)
        location_frame = Gtk.Frame(label="Location")
        location_grid = Gtk.Grid(margin_start=12, margin_end=12, margin_top=6, margin_bottom=12, row_spacing=6, column_spacing=6)
        location_grid.attach(Gtk.Label.new("Latitude:"), 0, 0, 1, 1)
        location_grid.attach(Gtk.Label.new("Longitude:"), 0, 1, 1, 1)
        lat_entry = Gtk.Entry()
        lon_entry = Gtk.Entry()
        lat_entry.add_css_class("missing-data"); lon_entry.add_css_class("missing-data")
        location_grid.attach(lat_entry, 1, 0, 1, 1); location_grid.attach(lon_entry, 1, 1, 1, 1)
        location_frame.set_child(location_grid)
        right_panel.append(location_frame)
        comment_frame = Gtk.Frame(label="Markdown Comment (JPG only)")
        scrolled_comment = Gtk.ScrolledWindow(vexpand=True)
        scrolled_comment.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.comment_view = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self.comment_view.set_margin_start(6); self.comment_view.set_margin_end(6)
        self.comment_view.set_margin_top(6); self.comment_view.set_margin_bottom(6)
        scrolled_comment.set_child(self.comment_view)
        comment_frame.set_child(scrolled_comment)
        right_panel.append(comment_frame)
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, halign=Gtk.Align.END)
        prev_button = Gtk.Button(label="Previous"); next_button = Gtk.Button(label="Next")
        finish_button = Gtk.Button(label="Finish", css_classes=['suggested-action'])
        button_box.append(prev_button); button_box.append(next_button); button_box.append(finish_button)
        main_grid.attach(button_box, 0, 1, 2, 1)
        self.filename_entry.grab_focus()

class PhotoFlowWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.last_source_folder_path = None
        
        self.set_title("PhotoFlow")
        self.set_default_size(1200, 800)
        header = Gtk.HeaderBar()
        self.set_titlebar(header)
        menu = Gio.Menu()
        menu.append("Preferences", "app.preferences"); menu.append("About", "app.about")
        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
        self.spinner = Gtk.Spinner()
        header.pack_start(self.spinner)
        self.size_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 64, 256, 8)
        self.size_slider.set_value(128); self.size_slider.set_draw_value(False)
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
        
        main_grid.attach(scrolled_window, 0, 1, 3, 1)
        
        self.source_button = Gtk.Button(label="Select Source Folder...")
        self.dest_button = Gtk.Button(label="Select Destination Folder...")
        self.source_button.connect('clicked', self.on_select_source_folder)
        main_grid.attach(self.source_button, 0, 0, 1, 1)
        main_grid.attach(self.dest_button, 1, 0, 1, 1)
        
        self.deselect_button = Gtk.Button(label="Deselect All")
        self.deselect_button.connect('clicked', self.on_deselect_all_clicked)
        main_grid.attach(self.deselect_button, 2, 0, 1, 1)
        
        right_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, width_request=300)
        main_grid.attach(right_panel, 3, 0, 1, 2)
        
        selection_info_frame = Gtk.Frame(label="Selection Info")
        self.selection_label = Gtk.Label.new("No images selected.")
        self.selection_label.set_wrap(True); self.selection_label.set_margin_start(12); self.selection_label.set_margin_end(12)
        self.selection_label.set_margin_top(6); self.selection_label.set_margin_bottom(12)
        selection_info_frame.set_child(self.selection_label)
        rename_frame = Gtk.Frame(label="Batch Renaming")
        rename_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_start=12, margin_end=12, margin_top=6, margin_bottom=12)
        self.rename_entry = Gtk.Entry(placeholder_text="Base Name (e.g., Belgium_Trip_)")
        self.rename_spinner = Gtk.SpinButton.new_with_range(1, 10000, 1)
        self.batch_process_button = Gtk.Button(label="Process Batch Only")
        self.batch_process_button.connect('clicked', self.on_process_files_clicked)
        rename_box.append(self.rename_entry); rename_box.append(self.rename_spinner); rename_box.append(self.batch_process_button)
        rename_frame.set_child(rename_box)
        tags_frame = Gtk.Frame(label="Common Tags")
        tags_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_start=12, margin_end=12, margin_top=6, margin_bottom=12)
        self.tags_entry = Gtk.Entry(placeholder_text="Enter tags, comma-separated..."); tags_box.append(self.tags_entry)
        tags_frame.set_child(tags_box)
        location_frame = Gtk.Frame(label="Batch Location")
        self.gps_button = Gtk.Button(label="Add GPS Data...", margin_start=12, margin_end=12, margin_top=6, margin_bottom=6)
        location_frame.set_child(self.gps_button)
        self.obsidian_check = Gtk.CheckButton(label="Add to Obsidian Vault"); self.obsidian_check.set_active(True)
        self.review_button = Gtk.Button(label="Review & Process Individually...", css_classes=['suggested-action'])
        self.review_button.set_valign(Gtk.Align.END); self.review_button.set_vexpand(True)
        self.review_button.connect('clicked', self.on_review_files_clicked)
        right_panel.append(selection_info_frame); right_panel.append(rename_frame); right_panel.append(tags_frame); right_panel.append(location_frame)
        right_panel.append(self.obsidian_check); right_panel.append(self.review_button)
        
    def on_review_files_clicked(self, widget):
        selected_flowbox_children = self.thumbnail_view.get_selected_children()
        if not selected_flowbox_children: return
        selection_data = []
        for child in selected_flowbox_children:
            thumb_widget = child.get_child()
            selection_data.append({'base_name': Path(thumb_widget.jpg_path or thumb_widget.raw_path).stem, 'jpg_path': thumb_widget.jpg_path, 'raw_path': thumb_widget.raw_path})
        common_tags = [tag.strip() for tag in self.tags_entry.get_text().split(',') if tag.strip()]
        review_window = ReviewWindow(self, selection_data, common_tags)
        review_window.present()
        
    def on_process_files_clicked(self, widget):
        selected_flowbox_children = self.thumbnail_view.get_selected_children()
        if not selected_flowbox_children: return
        selection_data = []
        for child in selected_flowbox_children:
            thumb_widget = child.get_child()
            selection_data.append({'jpg_path': thumb_widget.jpg_path, 'raw_path': thumb_widget.raw_path})
        config = configparser.ConfigParser()
        script_dir = Path(__file__).parent.resolve()
        config_file_path = script_dir / 'config.ini'
        if not config_file_path.exists(): return
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
        self.batch_process_button.set_sensitive(False)
        self.review_button.set_sensitive(False)
        thread = threading.Thread(target=self.processing_thread_worker, args=(selection_data, settings))
        thread.start()
        
    def processing_thread_worker(self, selection_data, settings):
        core_engine.process_photos(selection_data, settings)
        GLib.idle_add(self.on_processing_finished)

    def on_processing_finished(self):
        self.spinner.stop()
        self.batch_process_button.set_sensitive(True)
        self.review_button.set_sensitive(True)
        if self.last_source_folder_path:
            print(f"Refreshing source folder: {self.last_source_folder_path}")
            thread = threading.Thread(target=self.load_thumbnails, args=(self.last_source_folder_path,))
            thread.start()
        else:
            self.clear_thumbnails()
        print("UI updated after processing.")

    def on_selection_changed(self, flowbox, *args):
        selected_widgets = flowbox.get_selected_children()
        count = len(selected_widgets)
        if count == 0: self.selection_label.set_text("No images selected.")
        elif count == 1:
            thumb_widget = selected_widgets[0].get_child()
            info_text = f"<b>Selected: {Path(thumb_widget.jpg_path or thumb_widget.raw_path).stem}</b>\n"
            if thumb_widget.jpg_path: info_text += f"\nJPG: {Path(thumb_widget.jpg_path).name}"
            if thumb_widget.raw_path: info_text += f"\nRAW: {Path(thumb_widget.raw_path).name}"
            self.selection_label.set_markup(info_text)
        else: self.selection_label.set_markup(f"<b>{count} images selected.</b>")

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
            folder = dialog.get_file()
            self.last_source_folder_path = folder.get_path()
            thread = threading.Thread(target=self.load_thumbnails, args=(self.last_source_folder_path,))
            thread.start()
        dialog.destroy()
        
    def on_deselect_all_clicked(self, widget):
        self.thumbnail_view.unselect_all()
        print("Selection cleared.")
        
    def add_thumbnail_to_view(self, pixbuf, filename, badge_text, jpg_path, raw_path):
        thumbnail = ThumbnailWidget(pixbuf, filename, badge_text, jpg_path, raw_path)
        thumbnail.set_display_size(int(self.size_slider.get_value()))
        
        click_gesture = Gtk.GestureClick.new()
        click_gesture.connect("released", self.on_thumbnail_pressed)
        thumbnail.add_controller(click_gesture)
        
        self.thumbnail_view.insert(thumbnail, -1)

    def on_thumbnail_pressed(self, gesture, n_press, x, y):
        modifiers = gesture.get_current_event_state()
        ctrl_pressed = bool(modifiers & Gdk.ModifierType.CONTROL_MASK)
        
        if ctrl_pressed:
            thumb_widget = gesture.get_widget()
            flowbox_child = thumb_widget.get_parent()
            
            if flowbox_child.is_selected():
                self.thumbnail_view.unselect_child(flowbox_child)
                gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        
    def clear_thumbnails(self):
        while child := self.thumbnail_view.get_child_at_index(0):
            self.thumbnail_view.remove(child)
            
    def load_thumbnails(self, folder_path):
        GLib.idle_add(self.clear_thumbnails)
        image_groups = {}
        for entry in os.scandir(folder_path):
            if entry.is_file():
                path = Path(entry.path)
                ext = path.suffix.lower()
                if ext in SUPPORTED_EXTENSIONS:
                    base_name = path.stem
                    if base_name not in image_groups: image_groups[base_name] = {'jpg_path': None, 'raw_path': None}
                    if ext in RAW_EXTENSIONS: image_groups[base_name]['raw_path'] = str(path)
                    else: image_groups[base_name]['jpg_path'] = str(path)
        for base_name, paths in image_groups.items():
            path_to_load, badge_text, jpg_path, raw_path = None, None, paths['jpg_path'], paths['raw_path']
            if jpg_path and raw_path: path_to_load, badge_text = jpg_path, "RAW+JPG"
            elif raw_path: path_to_load, badge_text = raw_path, "RAW"
            elif jpg_path: path_to_load = jpg_path
            
            if path_to_load:
                try:
                    pixbuf = self.create_pixbuf_from_file(path_to_load)
                    if pixbuf: GLib.idle_add(self.add_thumbnail_to_view, pixbuf, base_name, badge_text, jpg_path, raw_path)
                except Exception as e:
                    print(f"Failed to create thumbnail for {base_name}: {e}")
                    
    def create_pixbuf_from_file(self, file_path, initial_size=256):
        path = Path(file_path)
        img_data = None
        if path.suffix.lower() in RAW_EXTENSIONS:
            try:
                command = ['exiftool', '-b', '-PreviewImage', str(file_path)]
                result = subprocess.run(command, capture_output=True, check=True)
                img_data = result.stdout
                if not img_data:
                    command = ['exiftool', '-b', '-JpgFromRaw', str(file_path)]
                    result = subprocess.run(command, capture_output=True, check=True)
                    img_data = result.stdout
            except Exception: return None
        else:
            with open(file_path, 'rb') as f: img_data = f.read()
        if img_data:
            img = Image.open(io.BytesIO(img_data))
            img = ImageOps.exif_transpose(img)
            img.thumbnail((initial_size, initial_size))
            byte_stream = io.BytesIO()
            img.save(byte_stream, format='PNG')
            final_data = byte_stream.getvalue()
            loader = GdkPixbuf.PixbufLoader.new_with_type('png')
            loader.write(final_data)
            loader.close()
            return loader.get_pixbuf()
        return None

class PhotoFlowApp(Gtk.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect('activate', self.on_activate)
    def on_activate(self, app):
        self.load_css()
        self.win = PhotoFlowWindow(application=app)
        self.win.present()
    def load_css(self):
        css_provider = Gtk.CssProvider()
        css = """
        headerbar label.title { font-size: 1.2em; font-weight: bold; }
        .thumbnail-widget { border: 1px solid rgba(0, 0, 0, 0.4); border-radius: 4px; padding: 4px; background-color: rgba(0, 0, 0, 0.1); }
        button { color: #E67E22; border: 1px solid rgba(0, 0, 0, 0.2); border-radius: 5px; box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2); background-image: none; }
        button:hover { box-shadow: 0 0 1px rgba(0, 0, 0, 0.2); background-color: rgba(255, 255, 255, 0.05); }
        scale trough { background-color: #E67E22; }
        .thumbnail-badge { background-color: rgba(0, 0, 0, 0.7); color: white; font-size: 0.8em; font-weight: bold; padding: 1px 4px; border-radius: 3px; }
        entry.missing-data { border: 1px solid rgba(220, 50, 50, 0.6); background-color: rgba(220, 50, 50, 0.05); }
        """
        css_provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

if __name__ == "__main__":
    app = PhotoFlowApp(application_id="com.crispi.photoflow")
    app.run(None)
