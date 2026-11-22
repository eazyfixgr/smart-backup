#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
easy_backup.py - Εφαρμογή Backup για εξωτερικό USB drive
Δημιουργήθηκε για εύκολη χρήση από ηλικιωμένους
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
import shutil
import time
import threading
import string
from datetime import datetime
import ctypes
from ctypes import wintypes, byref, create_string_buffer, sizeof, WinError

# ============================================================
# ΡΥΘΜΙΣΕΙΣ
# ============================================================
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

# Φάκελοι που δεν πρέπει να αντιγράφονται (σύστημα, κρυφοί, προσωρινοί)
EXCLUDED_FOLDERS = {
    "System Volume Information",
    "$Recycle.Bin",
    "RECYCLER",
    "RECYCLED",
    "Windows",
    "Program Files",
    "Program Files (x86)",
    "boot",
    "EFI",
    "$SysReset",
    "System32",
    "SysWOW64",
    "Config.Msi",
    "Cache",
    "Temp",
    "Temporary Internet Files",
    "MSOCache",
    "PerfLogs",
    "Recovery",
    "System",
    "AppData",  # αν θέλετε να το αντιγράφετε, σβήστε το
}

# ============================================================
# Windows API για έλεγχο σφαλμάτων δίσκου & ανίχνευση USB
# ============================================================

SEM_FAILCRITICALERRORS = 0x0001
SEM_NOGPFAULTERRORBOX = 0x0002
SEM_NOALIGNMENTFAULTEXCEPT = 0x0004
SEM_NOOPENFILEERRORBOX = 0x8000

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

SetErrorMode = kernel32.SetErrorMode
SetErrorMode.argtypes = [wintypes.UINT]
SetErrorMode.restype = wintypes.UINT

# Για DeviceIoControl
IOCTL_STORAGE_QUERY_PROPERTY = 0x2D1400
STORAGE_DEVICE_PROPERTY = 0   # StorageDeviceProperty
PROPERTY_STANDARD_QUERY = 0   # PropertyStandardQuery
BUS_TYPE_USB = 7

class STORAGE_PROPERTY_QUERY(ctypes.Structure):
    _fields_ = [
        ('PropertyId', ctypes.c_ulong),
        ('QueryType', ctypes.c_ulong),
        ('AdditionalParameters', ctypes.c_byte * 1)
    ]

class STORAGE_DEVICE_DESCRIPTOR(ctypes.Structure):
    _fields_ = [
        ('Version', ctypes.c_ulong),
        ('Size', ctypes.c_ulong),
        ('DeviceType', ctypes.c_byte),
        ('DeviceTypeModifier', ctypes.c_byte),
        ('RemovableMedia', ctypes.c_byte),
        ('CommandQueueing', ctypes.c_byte),
        ('VendorIdOffset', ctypes.c_ulong),
        ('ProductIdOffset', ctypes.c_ulong),
        ('ProductRevisionOffset', ctypes.c_ulong),
        ('SerialNumberOffset', ctypes.c_ulong),
        ('BusType', ctypes.c_ulong),          # Το πεδίο που μας ενδιαφέρει
        ('RawPropertiesLength', ctypes.c_ulong),
        ('RawDeviceProperties', ctypes.c_byte * 1)
    ]

def disable_drive_error_dialogs():
    old_mode = SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOOPENFILEERRORBOX)
    return old_mode

def restore_error_mode(old_mode):
    SetErrorMode(old_mode)

def is_usb_drive(drive_letter):
    """
    Επιστρέφει True αν η μονάδα drive_letter (π.χ. 'D:') είναι συνδεδεμένη μέσω USB,
    χρησιμοποιώντας το IOCTL_STORAGE_QUERY_PROPERTY.
    """
    old_mode = disable_drive_error_dialogs()
    handle = None
    try:
        # Άνοιγμα handle για τη μονάδα
        drive_path = f"\\\\.\\{drive_letter[0]}:"
        handle = kernel32.CreateFileW(
            drive_path,
            0x80000000,          # GENERIC_READ
            0x00000003,          # FILE_SHARE_READ | FILE_SHARE_WRITE
            None,
            3,                   # OPEN_EXISTING
            0,
            None
        )
        if handle == -1 or handle is None:   # INVALID_HANDLE_VALUE = -1
            return False

        # Προετοιμασία ερωτήματος
        query = STORAGE_PROPERTY_QUERY()
        query.PropertyId = STORAGE_DEVICE_PROPERTY
        query.QueryType = PROPERTY_STANDARD_QUERY

        # Buffer για την απάντηση (αρκετά μεγάλο)
        buffer_size = 1024
        buffer = create_string_buffer(buffer_size)
        bytes_returned = wintypes.DWORD(0)

        # Κλήση DeviceIoControl
        success = kernel32.DeviceIoControl(
            handle,
            IOCTL_STORAGE_QUERY_PROPERTY,
            byref(query), sizeof(query),
            buffer, buffer_size,
            byref(bytes_returned),
            None
        )
        if not success:
            return False

        # Ανάλυση της δομής STORAGE_DEVICE_DESCRIPTOR
        # Το buffer περιέχει την πλήρη δομή, αρχίζοντας με STORAGE_DEVICE_DESCRIPTOR
        # Πρέπει να αντιστοιχίσουμε το buffer σε δομή, αλλά η δομή έχει μεταβλητό μέγεθος.
        # Θα αποσπάσουμε το πεδίο BusType.
        # Η δομή ξεκινάει με Version (4 bytes) και Size (4 bytes). Μετά έρχεται το BusType σε offset 40;
        # Ωστόσο, χρησιμοποιούμε ctypes για να την αποκωδικοποιήσουμε σωστά.
        # Θα δημιουργήσουμε ένα αντίγραφο της δομής πάνω στο buffer.
        # Επειδή η δομή είναι μεταβλητού μεγέθους, θα πάρουμε μόνο τα πρώτα bytes που χρειαζόμαστε.
        # Μπορούμε να κάνουμε cast το buffer σε pointer της δομής.
        desc_ptr = ctypes.cast(buffer, ctypes.POINTER(STORAGE_DEVICE_DESCRIPTOR))
        desc = desc_ptr.contents
        # Ελέγχουμε αν το size είναι έγκυρο
        if desc.Size < sizeof(STORAGE_DEVICE_DESCRIPTOR):
            return False
        # Ο BusType είναι στο πεδίο BusType
        bus_type = desc.BusType
        return bus_type == BUS_TYPE_USB
    except Exception:
        return False
    finally:
        if handle is not None and handle != -1:
            kernel32.CloseHandle(handle)
        restore_error_mode(old_mode)

# ============================================================
# ΒΟΗΘΗΤΙΚΕΣ ΣΥΝΑΡΤΗΣΕΙΣ
# ============================================================

def load_settings():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"source_folders": [], "copy_mode": "with_folder", "direction": "to_usb"}
    return {"source_folders": [], "copy_mode": "with_folder", "direction": "to_usb"}

def save_settings(settings):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)

def is_drive_ready(drive):
    old_mode = disable_drive_error_dialogs()
    try:
        if os.path.exists(drive):
            with os.scandir(drive) as it:
                next(it, None)
            return True
        return False
    except (OSError, PermissionError, FileNotFoundError):
        return False
    finally:
        restore_error_mode(old_mode)

def find_usb_drives():
    """
    Επιστρέφει λίστα με drive letters (π.χ. ['D:\\', 'E:\\']) που είναι USB (flash ή εξωτερικός δίσκος)
    και είναι έτοιμες.
    """
    old_mode = disable_drive_error_dialogs()
    drives = []
    system_drive = os.environ.get('SystemDrive', 'C:') + '\\'
    try:
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if not os.path.exists(drive):
                continue
            if drive == system_drive:
                # Αποκλείουμε τον δίσκο του συστήματος (συνήθως C:)
                continue
            if not is_drive_ready(drive):
                continue
            drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive)
            if drive_type == 2:  # DRIVE_REMOVABLE -> συνήθως USB flash
                drives.append(drive)
            elif drive_type == 3:  # DRIVE_FIXED -> μπορεί να είναι USB external
                if is_usb_drive(drive):
                    drives.append(drive)
    except Exception:
        pass
    finally:
        restore_error_mode(old_mode)
    return drives

def format_time(seconds):
    if seconds < 60:
        return f"{int(seconds)} δευτερόλεπτα"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes} λεπτά και {secs} δευτερόλεπτα"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours} ώρες και {minutes} λεπτά"

def get_file_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

def count_files_in_folders(folders):
    total = 0
    for folder in folders:
        if os.path.exists(folder):
            try:
                for root_dir, dirs, files in os.walk(folder):
                    dirs[:] = [d for d in dirs if d not in EXCLUDED_FOLDERS]
                    total += len(files)
            except (OSError, PermissionError):
                continue
    return total

def count_files_in_usb(usb_drive, folders, copy_mode):
    total = 0
    old_mode = disable_drive_error_dialogs()
    try:
        for folder in folders:
            folder_name = os.path.basename(folder)
            if copy_mode == "with_folder":
                search_path = os.path.join(usb_drive, folder_name)
            else:
                search_path = usb_drive
            if os.path.exists(search_path):
                try:
                    for root_dir, dirs, files in os.walk(search_path):
                        dirs[:] = [d for d in dirs if d not in EXCLUDED_FOLDERS]
                        total += len(files)
                except (OSError, PermissionError):
                    continue
    finally:
        restore_error_mode(old_mode)
    return total

# ============================================================
# ΚΥΡΙΑ ΕΦΑΡΜΟΓΗ
# ============================================================

class BackupApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Easy Backup")
        self.root.geometry("700x600")
        self.root.resizable(True, True)
        self.root.minsize(600, 500)
        self.root.configure(bg="#f0f0f0")
        
        self.settings = load_settings()
        self.cancel_flag = False
        self.is_running = False
        self.error_count = 0

        self.create_widgets()
        self.update_button_appearance()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        top_frame = tk.Frame(self.root, bg="#f0f0f0")
        top_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        settings_btn = tk.Button(top_frame, text="⚙ Ρυθμίσεις", font=("Arial", 12),
                                 bg="#e0e0e0", fg="#333333", relief=tk.RAISED, bd=2,
                                 padx=15, pady=5, command=self.open_settings)
        settings_btn.pack(side=tk.LEFT)

        self.folders_label = tk.Label(top_frame, text=self.get_folders_text(),
                                      font=("Arial", 10), bg="#f0f0f0", fg="#555555",
                                      wraplength=500, justify=tk.LEFT)
        self.folders_label.pack(side=tk.LEFT, padx=(15, 0))

        self.status_label = tk.Label(self.root, text=self.get_status_text(),
                                     font=("Arial", 11), bg="#f0f0f0", fg="#333333",
                                     wraplength=650, justify=tk.CENTER)
        self.status_label.pack(pady=(5, 5))

        center_frame = tk.Frame(self.root, bg="#f0f0f0")
        center_frame.pack(expand=True, fill=tk.BOTH, padx=20, pady=5)

        btn_frame = tk.Frame(center_frame, bg="#f0f0f0")
        btn_frame.pack(pady=(20, 10))
        self.copy_btn = tk.Button(btn_frame, text="", font=("Arial", 20, "bold"),
                                  bg="#4CAF50", fg="white", activebackground="#45a049",
                                  activeforeground="white", relief=tk.RAISED, bd=4,
                                  padx=40, pady=15, cursor="hand2",
                                  command=self.confirm_and_start)
        self.copy_btn.pack()

        progress_frame = tk.Frame(center_frame, bg="#f0f0f0")
        progress_frame.pack(fill=tk.X, pady=(15, 5))
        self.progress_label = tk.Label(progress_frame, text="", font=("Arial", 11),
                                       bg="#f0f0f0", fg="#333333")
        self.progress_label.pack(anchor=tk.W)
        self.progress = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL,
                                        length=600, mode='determinate')
        self.progress.pack(fill=tk.X, pady=(5, 5))
        self.time_label = tk.Label(progress_frame, text="", font=("Arial", 10),
                                   bg="#f0f0f0", fg="#666666")
        self.time_label.pack(anchor=tk.W)

        self.cancel_btn = tk.Button(center_frame, text="✖ Ακύρωση", font=("Arial", 12),
                                    bg="#f44336", fg="white", activebackground="#d32f2f",
                                    activeforeground="white", relief=tk.RAISED, bd=2,
                                    padx=20, pady=8, state=tk.DISABLED,
                                    command=self.cancel_backup)
        self.cancel_btn.pack(pady=(5, 10))

        result_frame = tk.Frame(center_frame, bg="#f0f0f0")
        result_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        self.result_text = tk.Text(result_frame, font=("Arial", 11), bg="#ffffff",
                                   fg="#333333", relief=tk.SUNKEN, bd=2,
                                   wrap=tk.WORD, height=6, state=tk.DISABLED)
        self.result_text.pack(fill=tk.BOTH, expand=True)
        scrollbar = tk.Scrollbar(self.result_text)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.result_text.yview)

    def get_folders_text(self):
        folders = self.settings.get("source_folders", [])
        if not folders:
            return "Δεν έχουν επιλεγεί φάκελοι"
        elif len(folders) == 1:
            return f"Επιλεγμένος φάκελος: {folders[0]}"
        else:
            text = "Επιλεγμένοι φάκελοι:\n"
            for f in folders:
                text += f"  • {f}\n"
            return text.strip()

    def get_status_text(self):
        direction = self.settings.get("direction", "to_usb")
        copy_mode = self.settings.get("copy_mode", "with_folder")
        folders = self.settings.get("source_folders", [])
        if not folders:
            return "Παρακαλώ ορίστε τις ρυθμίσεις σας"
        mode_text = "μαζί με τον φάκελο" if copy_mode == "with_folder" else "χωρίς τον φάκελο (τα περιεχόμενά του με την εσωτερική δομή)"
        if direction == "to_usb":
            return f"📤 Αντιγραφή από Υπολογιστή → USB drive ({mode_text})"
        else:
            return f"📥 Αντιγραφή από USB drive → Υπολογιστή ({mode_text})"

    def update_button_appearance(self):
        direction = self.settings.get("direction", "to_usb")
        if direction == "to_usb":
            self.copy_btn.config(text="📁 Αντιγραφή σε USB", bg="#4CAF50",
                                 activebackground="#45a049", highlightbackground="#2E7D32")
        else:
            self.copy_btn.config(text="📁 Αντιγραφή σε Υπολογιστή", bg="#2196F3",
                                 activebackground="#1976D2", highlightbackground="#0D47A1")

    def log_result(self, message):
        self.result_text.config(state=tk.NORMAL)
        self.result_text.insert(tk.END, message + "\n")
        self.result_text.see(tk.END)
        self.result_text.config(state=tk.DISABLED)

    # ============================================================
    # POPUP ΕΠΙΒΕΒΑΙΩΣΗΣ
    # ============================================================

    def confirm_and_start(self):
        if self.is_running:
            return
        folders = self.settings.get("source_folders", [])
        if not folders:
            messagebox.showwarning("Προσοχή", "Παρακαλώ επιλέξτε πρώτα φακέλους προς αντιγραφή από τις Ρυθμίσεις.")
            return
        direction = self.settings.get("direction", "to_usb")
        copy_mode = self.settings.get("copy_mode", "with_folder")
        if copy_mode == "without_folder" and len(folders) > 1:
            messagebox.showerror("Αδυναμία εκτέλεσης",
                "Η επιλογή 'Χωρίς φάκελο' μπορεί να χρησιμοποιηθεί μόνο με έναν επιλεγμένο φάκελο.\n\n"
                "Παρακαλώ επιλέξτε μόνο έναν φάκελο ή αλλάξτε τον τρόπο αντιγραφής.")
            return

        confirm = tk.Toplevel(self.root)
        confirm.title("Επιβεβαίωση")
        confirm.geometry("550x400")
        confirm.resizable(False, False)
        confirm.configure(bg="#f0f0f0")
        confirm.transient(self.root)
        confirm.grab_set()
        confirm.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width()//2) - (confirm.winfo_width()//2)
        y = self.root.winfo_y() + (self.root.winfo_height()//2) - (confirm.winfo_height()//2)
        confirm.geometry(f"+{x}+{y}")

        tk.Label(confirm, text="Παρακαλώ επιβεβαιώστε:", font=("Arial", 16, "bold"),
                 bg="#f0f0f0", fg="#333333").pack(pady=(20, 15))

        details_frame = tk.Frame(confirm, bg="#ffffff", relief=tk.SUNKEN, bd=2)
        details_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 15))
        details_text = tk.Text(details_frame, font=("Arial", 12), bg="#ffffff",
                               fg="#333333", wrap=tk.WORD, height=10,
                               relief=tk.FLAT, padx=10, pady=10)
        details_text.pack(fill=tk.BOTH, expand=True)

        if direction == "to_usb":
            details_text.insert(tk.END, "📤 Αντιγραφή από Υπολογιστή προς USB\n\n")
            details_text.insert(tk.END, "Θα αντιγραφούν:\n")
            for folder in folders:
                details_text.insert(tk.END, f"  • {folder} ({count_files_in_folders([folder])} αρχεία)\n")
            usb_drives = find_usb_drives()
            details_text.insert(tk.END, f"\n📍 Προορισμός: {usb_drives[0] if usb_drives else 'USB drive'}")
            details_text.insert(tk.END, "\n📁 Τρόπος: " + ("Με τους φακέλους" if copy_mode=="with_folder" else "Χωρίς τους φακέλους (μόνο τα περιεχόμενά τους)"))
        else:
            details_text.insert(tk.END, "📥 Αντιγραφή από USB προς Υπολογιστή\n\n")
            details_text.insert(tk.END, "Θα αντιγραφούν πίσω:\n")
            for folder in folders:
                details_text.insert(tk.END, f"  • {os.path.basename(folder)} → {folder}\n")
            usb_drives = find_usb_drives()
            details_text.insert(tk.END, f"\n📍 Προέλευση: {usb_drives[0] if usb_drives else 'USB drive'}")
            details_text.insert(tk.END, "\n📁 Τρόπος: " + ("Με τους φακέλους" if copy_mode=="with_folder" else "Χωρίς τους φακέλους (μόνο τα περιεχόμενά τους)"))

        details_text.insert(tk.END, "\n\n⚠ ΣΗΜΑΝΤΙΚΟ: Κανένα αρχείο δεν θα διαγραφεί.")
        details_text.config(state=tk.DISABLED)

        btn_frame = tk.Frame(confirm, bg="#f0f0f0")
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        tk.Button(btn_frame, text="✖ Ακύρωση", font=("Arial", 14), bg="#f44336",
                  fg="white", activebackground="#d32f2f", activeforeground="white",
                  relief=tk.RAISED, bd=2, padx=30, pady=10,
                  command=confirm.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        tk.Button(btn_frame, text="✓ ΟΚ, Ξεκίνα", font=("Arial", 14, "bold"),
                  bg="#4CAF50", fg="white", activebackground="#45a049",
                  activeforeground="white", relief=tk.RAISED, bd=2, padx=30, pady=10,
                  command=lambda: self.on_confirm(confirm)).pack(side=tk.RIGHT)

    def on_confirm(self, confirm_window):
        confirm_window.destroy()
        self.start_backup()

    # ============================================================
    # ΡΥΘΜΙΣΕΙΣ
    # ============================================================

    def open_settings(self):
        if self.is_running:
            messagebox.showwarning("Προσοχή", "Δεν μπορείτε να αλλάξετε ρυθμίσεις ενώ γίνεται αντιγραφή.")
            return
        SettingsWindow(self.root, self.settings, self.on_settings_saved)

    def on_settings_saved(self, new_settings):
        self.settings = new_settings
        save_settings(self.settings)
        self.folders_label.config(text=self.get_folders_text())
        self.status_label.config(text=self.get_status_text())
        self.update_button_appearance()
        self.log_result("✓ Οι ρυθμίσεις αποθηκεύτηκαν επιτυχώς.")

    # ============================================================
    # BACKUP
    # ============================================================

    def start_backup(self):
        folders = self.settings.get("source_folders", [])
        direction = self.settings.get("direction", "to_usb")
        copy_mode = self.settings.get("copy_mode", "with_folder")
        if copy_mode == "without_folder" and len(folders) > 1:
            return

        old_mode = disable_drive_error_dialogs()
        try:
            usb_drives = find_usb_drives()
            if not usb_drives:
                messagebox.showerror("Σφάλμα", "Δεν βρέθηκε έτοιμο USB drive.\nΠαρακαλώ συνδέστε ένα USB drive.")
                return
            if len(usb_drives) > 1:
                messagebox.showerror("Σφάλμα", f"Βρέθηκαν πολλά USB drives: {', '.join(usb_drives)}\n"
                                     "Παρακαλώ κρατήστε μόνο ένα.")
                return
            self.target_drive = usb_drives[0]
        finally:
            restore_error_mode(old_mode)

        self.copy_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.NORMAL)
        self.is_running = True
        self.cancel_flag = False
        self.error_count = 0
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)
        self.result_text.config(state=tk.DISABLED)

        self.log_result(f"🔄 Έναρξη αντιγραφής {'προς' if direction=='to_usb' else 'από'}: {self.target_drive}")
        self.log_result(f"📂 Φάκελοι: {len(folders)}")

        self.backup_thread = threading.Thread(target=self.run_backup, args=(folders, direction), daemon=True)
        self.backup_thread.start()

    def run_backup(self, folders, direction):
        start_time = time.time()
        copy_mode = self.settings.get("copy_mode", "with_folder")

        def safe_stat(path):
            try:
                return os.path.getsize(path), os.path.getmtime(path)
            except (OSError, PermissionError, FileNotFoundError):
                return None

        def is_same_file(src, dest, direction):
            src_stat = safe_stat(src)
            dest_stat = safe_stat(dest)
            if src_stat is None or dest_stat is None:
                return False
            src_size, src_mtime = src_stat
            dest_size, dest_mtime = dest_stat
            if src_size != dest_size:
                return False
            tolerance = 2.0 if direction == "to_usb" else 1.0
            return abs(src_mtime - dest_mtime) <= tolerance

        old_mode = disable_drive_error_dialogs()
        try:
            all_files = []
            if direction == "to_usb":
                for folder in folders:
                    if self.cancel_flag:
                        break
                    if not os.path.exists(folder):
                        self.root.after(0, self.log_result, f"⚠ Ο φάκελος {folder} δεν βρέθηκε.")
                        continue
                    try:
                        for root_dir, dirs, files in os.walk(folder):
                            # Αποκλεισμός κρυφών/συστημικών φακέλων
                            dirs[:] = [d for d in dirs if d not in EXCLUDED_FOLDERS]
                            if self.cancel_flag:
                                break
                            for file in files:
                                all_files.append((os.path.join(root_dir, file), folder, "pc_to_usb"))
                    except (OSError, PermissionError) as e:
                        self.root.after(0, self.log_result, f"⚠ Σφάλμα πρόσβασης: {e}")
            else:
                for folder in folders:
                    if self.cancel_flag:
                        break
                    folder_name = os.path.basename(folder)
                    usb_source = os.path.join(self.target_drive, folder_name) if copy_mode=="with_folder" else self.target_drive
                    if not os.path.exists(usb_source):
                        self.root.after(0, self.log_result, f"⚠ Δεν βρέθηκε ο φάκελος {folder_name} στο USB.")
                        continue
                    try:
                        for root_dir, dirs, files in os.walk(usb_source):
                            dirs[:] = [d for d in dirs if d not in EXCLUDED_FOLDERS]
                            if self.cancel_flag:
                                break
                            for file in files:
                                all_files.append((os.path.join(root_dir, file), folder, "usb_to_pc"))
                    except (OSError, PermissionError) as e:
                        self.root.after(0, self.log_result, f"⚠ Σφάλμα πρόσβασης στο USB: {e}")
                        if "no disk" in str(e).lower() or "device not ready" in str(e).lower():
                            self.root.after(0, self.log_result, "❌ Το USB αποσυνδέθηκε ή δεν είναι έτοιμο.")
                            self.root.after(0, self.backup_finished, 0, 0, 0, time.time()-start_time, "USB_ERROR")
                            return

            total_files = len(all_files)
            if total_files == 0:
                self.root.after(0, self.backup_finished, 0, 0, 0, start_time, "Δεν βρέθηκαν αρχεία προς αντιγραφή.")
                return

            copied = skipped = bytes_copied = 0
            for idx, (src_path, folder, file_type) in enumerate(all_files):
                if self.cancel_flag:
                    self.root.after(0, self.log_result, "⏹ Η αντιγραφή ακυρώθηκε.")
                    break

                if file_type == "pc_to_usb":
                    rel = os.path.relpath(src_path, os.path.dirname(folder) if copy_mode=="with_folder" else folder)
                    dest_path = os.path.join(self.target_drive, rel)
                else:
                    if copy_mode == "with_folder":
                        usb_source = os.path.join(self.target_drive, os.path.basename(folder))
                        rel = os.path.relpath(src_path, usb_source)
                    else:
                        rel = os.path.relpath(src_path, self.target_drive)
                    dest_path = os.path.join(folder, rel)

                self.root.after(0, self.update_progress,
                                int((idx+1)/total_files*100), idx+1, total_files,
                                ((time.time()-start_time)/(idx+1)*(total_files-idx-1)) if idx>0 else 0)

                if os.path.exists(dest_path) and is_same_file(src_path, dest_path, direction):
                    skipped += 1
                    continue

                try:
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    shutil.copy2(src_path, dest_path)
                    copied += 1
                    bytes_copied += os.path.getsize(src_path)
                except (OSError, PermissionError, shutil.Error) as e:
                    self.error_count += 1
                    self.root.after(0, self.log_result, f"⚠ Σφάλμα αντιγραφής: {os.path.basename(src_path)} - {e}")
                    if "no disk" in str(e).lower() or "device not ready" in str(e).lower():
                        self.root.after(0, self.log_result, "❌ Το USB αποσυνδέθηκε.")
                        self.root.after(0, self.backup_finished, copied, skipped, bytes_copied, time.time()-start_time, "USB_ERROR")
                        return

            duration = time.time() - start_time
            if self.error_count > 5 and copied == 0:
                self.root.after(0, self.backup_finished, copied, skipped, bytes_copied, duration, "USB_ERROR")
            elif self.cancel_flag:
                self.root.after(0, self.backup_finished, copied, skipped, bytes_copied, duration, "ΑΚΥΡΩΘΗΚΕ")
            else:
                self.root.after(0, self.backup_finished, copied, skipped, bytes_copied, duration, "ΟΛΟΚΛΗΡΩΘΗΚΕ")

        except Exception as e:
            self.root.after(0, self.log_result, f"❌ Σφάλμα: {str(e)}")
            self.root.after(0, self.backup_finished, 0, 0, 0, time.time()-start_time, "ΣΦΑΛΜΑ")
        finally:
            restore_error_mode(old_mode)

    def update_progress(self, pct, current, total, remaining):
        self.progress['value'] = pct
        self.progress_label.config(text=f"Αντιγραφή: {current} από {total} αρχεία ({pct}%)")
        self.time_label.config(text=f"Υπολειπόμενος χρόνος: {format_time(remaining)}" if remaining>0 else "")
        self.root.update_idletasks()

    def backup_finished(self, copied, skipped, bytes_copied, duration, status):
        self.is_running = False
        self.cancel_btn.config(state=tk.DISABLED)
        self.copy_btn.config(state=tk.NORMAL)
        self.progress['value'] = 100
        self.progress_label.config(text="")
        self.time_label.config(text="")

        direction = self.settings.get("direction", "to_usb")
        self.log_result("=" * 50)
        if status == "ΟΛΟΚΛΗΡΩΘΗΚΕ":
            self.log_result(f"✅ Η αντιγραφή ολοκληρώθηκε επιτυχώς!")
            self.log_result(f"📊 Αντιγράφηκαν: {copied} αρχεία ({get_file_size(bytes_copied)})")
            if skipped:
                self.log_result(f"⏭ Παραλείφθηκαν (ήδη υπάρχουν): {skipped} αρχεία")
            if self.error_count:
                self.log_result(f"⚠ Απέτυχαν: {self.error_count} αρχεία")
                if self.error_count >= 3:
                    messagebox.showwarning("Προσοχή", f"Απέτυχαν {self.error_count} αρχεία.\n"
                                         "Μπορεί να οφείλεται σε αποσύνδεση USB, ανοιχτά αρχεία ή γεμάτο δίσκο.")
            self.log_result(f"⏱ Χρόνος: {format_time(duration)}")
            self.log_result(f"📍 {'Προορισμός' if direction=='to_usb' else 'Προέλευση'}: {self.target_drive}")
        elif status == "ΑΚΥΡΩΘΗΚΕ":
            self.log_result(f"⏹ Η αντιγραφή ακυρώθηκε.")
            self.log_result(f"📊 Αντιγράφηκαν: {copied} αρχεία ({get_file_size(bytes_copied)})")
            self.log_result(f"⏱ Χρόνος: {format_time(duration)}")
        elif status == "USB_ERROR":
            self.log_result("❌ Το USB drive αποσυνδέθηκε ή δεν ήταν έτοιμο!")
            self.log_result(f"📊 Αντιγράφηκαν: {copied} αρχεία ({get_file_size(bytes_copied)})")
            self.log_result("💡 Την επόμενη φορά θα συνεχίσει από εκεί που έμεινε.")
            messagebox.showerror("Σφάλμα", "Το USB drive αποσυνδέθηκε ή δεν είναι έτοιμο.\n\nΕλέγξτε τη σύνδεση και δοκιμάστε ξανά.")
        else:
            self.log_result(f"❌ Η αντιγραφή απέτυχε.")
        self.log_result("=" * 50)
        self.root.after(2000, self.reset_progress)

    def reset_progress(self):
        self.progress['value'] = 0

    def cancel_backup(self):
        self.cancel_flag = True
        self.cancel_btn.config(state=tk.DISABLED, text="Ακύρωση...")
        self.log_result("⏹ Ακύρωση σε εξέλιξη...")

    def on_close(self):
        if self.is_running:
            if messagebox.askyesno("Επιβεβαίωση", "Γίνεται αντιγραφή αρχείων. Θέλετε σίγουρα να κλείσετε;"):
                self.cancel_flag = True
                self.root.destroy()
        else:
            self.root.destroy()


# ============================================================
# ΠΑΡΑΘΥΡΟ ΡΥΘΜΙΣΕΩΝ
# ============================================================

class SettingsWindow:
    def __init__(self, parent, settings, callback):
        self.settings = settings.copy()
        self.callback = callback
        self.window = tk.Toplevel(parent)
        self.window.title("Ρυθμίσεις - Επιλογή φακέλων")
        self.window.geometry("600x600")  # λίγο μεγαλύτερο για την ενημέρωση USB
        self.window.resizable(True, True)
        self.window.minsize(500, 500)
        self.window.configure(bg="#f0f0f0")
        self.window.transient(parent)
        self.window.grab_set()
        self.create_widgets()
        self.window.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width()//2) - (self.window.winfo_width()//2)
        y = parent.winfo_y() + (parent.winfo_height()//2) - (self.window.winfo_height()//2)
        self.window.geometry(f"+{x}+{y}")

    def create_widgets(self):
        tk.Label(self.window, text="Επιλέξτε τους φακέλους που θέλετε να αντιγράφονται:",
                 font=("Arial", 12), bg="#f0f0f0", fg="#333333",
                 wraplength=550, justify=tk.LEFT).pack(pady=(15,10), padx=15, anchor=tk.W)

        list_frame = tk.Frame(self.window, bg="#f0f0f0")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0,10))
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.folders_listbox = tk.Listbox(list_frame, font=("Arial", 11),
                                          selectmode=tk.SINGLE, yscrollcommand=scrollbar.set,
                                          relief=tk.SUNKEN, bd=2, bg="#ffffff")
        self.folders_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.folders_listbox.yview)
        for folder in self.settings.get("source_folders", []):
            self.folders_listbox.insert(tk.END, folder)

        btn_frame = tk.Frame(self.window, bg="#f0f0f0")
        btn_frame.pack(fill=tk.X, padx=15, pady=(0,10))
        tk.Button(btn_frame, text="➕ Προσθήκη φακέλου", font=("Arial", 11),
                  bg="#2196F3", fg="white", activebackground="#1976D2",
                  activeforeground="white", relief=tk.RAISED, bd=2, padx=15, pady=5,
                  command=self.add_folder).pack(side=tk.LEFT, padx=(0,10))
        tk.Button(btn_frame, text="✖ Αφαίρεση επιλεγμένου", font=("Arial", 11),
                  bg="#FF9800", fg="white", activebackground="#F57C00",
                  activeforeground="white", relief=tk.RAISED, bd=2, padx=15, pady=5,
                  command=self.remove_folder).pack(side=tk.LEFT)

        ttk.Separator(self.window, orient='horizontal').pack(fill=tk.X, padx=15, pady=5)

        tk.Label(self.window, text="Ρυθμίσεις αντιγραφής:", font=("Arial", 12, "bold"),
                 bg="#f0f0f0", fg="#333333", anchor=tk.W).pack(pady=(10,5), padx=15, anchor=tk.W)

        mode_frame = tk.Frame(self.window, bg="#f0f0f0")
        mode_frame.pack(fill=tk.X, padx=15, pady=(0,5))
        tk.Label(mode_frame, text="Τρόπος αντιγραφής:", font=("Arial", 11),
                 bg="#f0f0f0", fg="#333333").pack(side=tk.LEFT, padx=(0,10))
        self.copy_mode_var = tk.StringVar(value=self.settings.get("copy_mode", "with_folder"))
        tk.Radiobutton(mode_frame, text="Μαζί με τον φάκελο", font=("Arial", 11),
                       variable=self.copy_mode_var, value="with_folder",
                       bg="#f0f0f0", activebackground="#f0f0f0").pack(side=tk.LEFT, padx=(0,15))
        tk.Radiobutton(mode_frame, text="Χωρίς φάκελο (τα περιεχόμενά του)", font=("Arial", 11),
                       variable=self.copy_mode_var, value="without_folder",
                       bg="#f0f0f0", activebackground="#f0f0f0").pack(side=tk.LEFT)

        dir_frame = tk.Frame(self.window, bg="#f0f0f0")
        dir_frame.pack(fill=tk.X, padx=15, pady=(5,10))
        tk.Label(dir_frame, text="Κατεύθυνση:", font=("Arial", 11),
                 bg="#f0f0f0", fg="#333333").pack(side=tk.LEFT, padx=(0,10))
        self.direction_var = tk.StringVar(value=self.settings.get("direction", "to_usb"))
        tk.Radiobutton(dir_frame, text="Αντιγραφή σε USB", font=("Arial", 11),
                       variable=self.direction_var, value="to_usb",
                       bg="#f0f0f0", activebackground="#f0f0f0").pack(side=tk.LEFT, padx=(0,15))
        tk.Radiobutton(dir_frame, text="Αντιγραφή σε Υπολογιστή", font=("Arial", 11),
                       variable=self.direction_var, value="to_pc",
                       bg="#f0f0f0", activebackground="#f0f0f0").pack(side=tk.LEFT)

        # ===== ΠΡΟΣΘΗΚΗ: Ενημέρωση για ανιχνευμένες USB συσκευές =====
        ttk.Separator(self.window, orient='horizontal').pack(fill=tk.X, padx=15, pady=5)
        usb_info_frame = tk.Frame(self.window, bg="#f0f0f0")
        usb_info_frame.pack(fill=tk.X, padx=15, pady=(5,10))
        tk.Label(usb_info_frame, text="🔌 Ανιχνευμένες USB συσκευές:", font=("Arial", 11, "bold"),
                 bg="#f0f0f0", fg="#333333").pack(anchor=tk.W)
        usb_drives = find_usb_drives()
        if usb_drives:
            usb_text = ", ".join(usb_drives)
            tk.Label(usb_info_frame, text=usb_text, font=("Arial", 11),
                     bg="#f0f0f0", fg="#0066cc").pack(anchor=tk.W, padx=(10,0))
        else:
            tk.Label(usb_info_frame, text="⚠ Δεν βρέθηκε καμία USB συσκευή. Συνδέστε ένα USB drive.",
                     font=("Arial", 11), bg="#f0f0f0", fg="#cc0000").pack(anchor=tk.W, padx=(10,0))

        bottom_frame = tk.Frame(self.window, bg="#f0f0f0")
        bottom_frame.pack(fill=tk.X, padx=15, pady=(10,15))
        tk.Button(bottom_frame, text="✓ Αποθήκευση", font=("Arial", 12, "bold"),
                  bg="#4CAF50", fg="white", activebackground="#45a049",
                  activeforeground="white", relief=tk.RAISED, bd=2, padx=20, pady=8,
                  command=self.save).pack(side=tk.RIGHT, padx=(10,0))
        tk.Button(bottom_frame, text="✖ Ακύρωση", font=("Arial", 12),
                  bg="#f44336", fg="white", activebackground="#d32f2f",
                  activeforeground="white", relief=tk.RAISED, bd=2, padx=20, pady=8,
                  command=self.window.destroy).pack(side=tk.RIGHT)

    def add_folder(self):
        folder = filedialog.askdirectory(title="Επιλέξτε φάκελο για backup", mustexist=True)
        if folder and folder not in self.folders_listbox.get(0, tk.END):
            self.folders_listbox.insert(tk.END, folder)
        elif folder:
            messagebox.showinfo("Πληροφορία", "Ο φάκελος υπάρχει ήδη στη λίστα.")

    def remove_folder(self):
        sel = self.folders_listbox.curselection()
        if sel:
            self.folders_listbox.delete(sel[0])
        else:
            messagebox.showwarning("Προσοχή", "Παρακαλώ επιλέξτε έναν φάκελο από τη λίστα.")

    def save(self):
        folders = list(self.folders_listbox.get(0, tk.END))
        if not folders and not messagebox.askyesno("Επιβεβαίωση",
            "Δεν έχετε επιλέξει κανέναν φάκελο. Θέλετε να συνεχίσετε;"):
            return
        self.settings["source_folders"] = folders
        self.settings["copy_mode"] = self.copy_mode_var.get()
        self.settings["direction"] = self.direction_var.get()
        self.callback(self.settings)
        self.window.destroy()


# ============================================================
# ΕΚΚΙΝΗΣΗ
# ============================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = BackupApp(root)
    root.mainloop()