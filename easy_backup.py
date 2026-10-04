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

# ============================================================
# ΡΥΘΜΙΣΕΙΣ
# ============================================================
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

# ============================================================
# ΒΟΗΘΗΤΙΚΕΣ ΣΥΝΑΡΤΗΣΕΙΣ
# ============================================================

def load_settings():
    """Φορτώνει τις ρυθμίσεις από το αρχείο JSON."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"source_folders": [], "copy_mode": "with_folder", "direction": "to_usb"}
    return {"source_folders": [], "copy_mode": "with_folder", "direction": "to_usb"}

def save_settings(settings):
    """Αποθηκεύει τις ρυθμίσεις στο αρχείο JSON."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)

def find_usb_drives():
    """
    Βρίσκει όλους τους αφαιρούμενους δίσκους (USB) στο σύστημα.
    Επιστρέφει λίστα με τα γράμματα των δίσκων (π.χ. ['D:', 'E:']).
    """
    drives = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            try:
                import ctypes
                drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive)
                # DRIVE_REMOVABLE = 2
                if drive_type == 2:
                    drives.append(drive)
            except:
                pass
    return drives

def format_time(seconds):
    """Μετατρέπει δευτερόλεπτα σε readable μορφή."""
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
    """Μετατρέπει bytes σε readable μορφή."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

def count_files_in_folders(folders):
    """Μετράει πόσα αρχεία υπάρχουν συνολικά στους φακέλους."""
    total = 0
    for folder in folders:
        if os.path.exists(folder):
            for root_dir, dirs, files in os.walk(folder):
                total += len(files)
    return total

def count_files_in_usb(usb_drive, folders, copy_mode):
    """Μετράει πόσα αρχεία υπάρχουν στο USB για αντιγραφή προς υπολογιστή."""
    total = 0
    for folder in folders:
        folder_name = os.path.basename(folder)
        if copy_mode == "with_folder":
            search_path = os.path.join(usb_drive, folder_name)
        else:
            search_path = usb_drive
        
        if os.path.exists(search_path):
            for root_dir, dirs, files in os.walk(search_path):
                total += len(files)
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

        # Κεντρικό χρώμα και στυλ
        self.root.configure(bg="#f0f0f0")
        
        # Μεταβλητές
        self.settings = load_settings()
        self.cancel_flag = False
        self.is_running = False
        self.error_count = 0

        # Δημιουργία UI
        self.create_widgets()
        self.update_button_appearance()

        # Κλείσιμο παραθύρου
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        """Δημιουργεί όλα τα widgets του παραθύρου."""
        
        # ===== Πάνω μπάρα με κουμπί Ρυθμίσεις =====
        top_frame = tk.Frame(self.root, bg="#f0f0f0")
        top_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        settings_btn = tk.Button(
            top_frame,
            text="⚙ Ρυθμίσεις",
            font=("Arial", 12),
            bg="#e0e0e0",
            fg="#333333",
            relief=tk.RAISED,
            bd=2,
            padx=15,
            pady=5,
            command=self.open_settings
        )
        settings_btn.pack(side=tk.LEFT)

        # Ετικέτα με επιλεγμένους φακέλους
        self.folders_label = tk.Label(
            top_frame,
            text=self.get_folders_text(),
            font=("Arial", 10),
            bg="#f0f0f0",
            fg="#555555",
            wraplength=500,
            justify=tk.LEFT
        )
        self.folders_label.pack(side=tk.LEFT, padx=(15, 0))

        # ===== Ετικέτα κατάστασης (τι θα γίνει) =====
        self.status_label = tk.Label(
            self.root,
            text=self.get_status_text(),
            font=("Arial", 11),
            bg="#f0f0f0",
            fg="#333333",
            wraplength=650,
            justify=tk.CENTER
        )
        self.status_label.pack(pady=(5, 5))

        # ===== Κεντρικό πλαίσιο =====
        center_frame = tk.Frame(self.root, bg="#f0f0f0")
        center_frame.pack(expand=True, fill=tk.BOTH, padx=20, pady=5)

        # Κουμπί αντιγραφής - μεγάλο
        btn_frame = tk.Frame(center_frame, bg="#f0f0f0")
        btn_frame.pack(pady=(20, 10))

        self.copy_btn = tk.Button(
            btn_frame,
            text="",
            font=("Arial", 20, "bold"),
            bg="#4CAF50",
            fg="white",
            activebackground="#45a049",
            activeforeground="white",
            relief=tk.RAISED,
            bd=4,
            padx=40,
            pady=15,
            cursor="hand2",
            command=self.confirm_and_start
        )
        self.copy_btn.pack()

        # ===== Progress Bar =====
        progress_frame = tk.Frame(center_frame, bg="#f0f0f0")
        progress_frame.pack(fill=tk.X, pady=(15, 5))

        self.progress_label = tk.Label(
            progress_frame,
            text="",
            font=("Arial", 11),
            bg="#f0f0f0",
            fg="#333333"
        )
        self.progress_label.pack(anchor=tk.W)

        self.progress = ttk.Progressbar(
            progress_frame,
            orient=tk.HORIZONTAL,
            length=600,
            mode='determinate'
        )
        self.progress.pack(fill=tk.X, pady=(5, 5))

        # Εκτίμηση χρόνου
        self.time_label = tk.Label(
            progress_frame,
            text="",
            font=("Arial", 10),
            bg="#f0f0f0",
            fg="#666666"
        )
        self.time_label.pack(anchor=tk.W)

        # ===== Κουμπί Ακύρωσης =====
        self.cancel_btn = tk.Button(
            center_frame,
            text="✖ Ακύρωση",
            font=("Arial", 12),
            bg="#f44336",
            fg="white",
            activebackground="#d32f2f",
            activeforeground="white",
            relief=tk.RAISED,
            bd=2,
            padx=20,
            pady=8,
            state=tk.DISABLED,
            command=self.cancel_backup
        )
        self.cancel_btn.pack(pady=(5, 10))

        # ===== Περιοχή αποτελεσμάτων =====
        result_frame = tk.Frame(center_frame, bg="#f0f0f0")
        result_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        self.result_text = tk.Text(
            result_frame,
            font=("Arial", 11),
            bg="#ffffff",
            fg="#333333",
            relief=tk.SUNKEN,
            bd=2,
            wrap=tk.WORD,
            height=6,
            state=tk.DISABLED
        )
        self.result_text.pack(fill=tk.BOTH, expand=True)

        # Scrollbar για το text
        scrollbar = tk.Scrollbar(self.result_text)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.result_text.yview)

    def get_folders_text(self):
        """Επιστρέφει κείμενο με τους επιλεγμένους φακέλους."""
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
        """Επιστρέφει κείμενο που περιγράφει τι θα γίνει."""
        direction = self.settings.get("direction", "to_usb")
        copy_mode = self.settings.get("copy_mode", "with_folder")
        folders = self.settings.get("source_folders", [])

        if not folders:
            return "Παρακαλώ ορίστε τις ρυθμίσεις σας"

        if direction == "to_usb":
            dest = "USB drive"
            mode_text = "μαζί με τον φάκελο" if copy_mode == "with_folder" else "χωρίς τον φάκελο (τα περιεχόμενά του με την εσωτερική δομή)"
            return f"📤 Αντιγραφή από Υπολογιστή → USB drive ({mode_text})"
        else:
            dest = "Υπολογιστή"
            mode_text = "μαζί με τον φάκελο" if copy_mode == "with_folder" else "χωρίς τον φάκελο (τα περιεχόμενά του με την εσωτερική δομή)"
            return f"📥 Αντιγραφή από USB drive → Υπολογιστή ({mode_text})"

    def update_button_appearance(self):
        """Ενημερώνει το κουμπί ανάλογα με την κατεύθυνση."""
        direction = self.settings.get("direction", "to_usb")
        
        if direction == "to_usb":
            self.copy_btn.config(
                text="📁 Αντιγραφή σε USB",
                bg="#4CAF50",
                activebackground="#45a049",
                highlightbackground="#2E7D32"
            )
        else:
            self.copy_btn.config(
                text="📁 Αντιγραφή σε Υπολογιστή",
                bg="#2196F3",
                activebackground="#1976D2",
                highlightbackground="#0D47A1"
            )

    def log_result(self, message):
        """Γράφει μήνυμα στην περιοχή αποτελεσμάτων."""
        self.result_text.config(state=tk.NORMAL)
        self.result_text.insert(tk.END, message + "\n")
        self.result_text.see(tk.END)
        self.result_text.config(state=tk.DISABLED)

    # ============================================================
    # POPUP ΕΠΙΒΕΒΑΙΩΣΗΣ
    # ============================================================

    def confirm_and_start(self):
        """Εμφανίζει popup επιβεβαίωσης πριν ξεκινήσει."""
        if self.is_running:
            return

        folders = self.settings.get("source_folders", [])
        if not folders:
            messagebox.showwarning("Προσοχή", "Παρακαλώ επιλέξτε πρώτα φακέλους προς αντιγραφή από τις Ρυθμίσεις.")
            return

        direction = self.settings.get("direction", "to_usb")
        copy_mode = self.settings.get("copy_mode", "with_folder")

        # Έλεγχος: η λειτουργία "χωρίς φάκελο" υποστηρίζεται μόνο με έναν φάκελο
        if copy_mode == "without_folder" and len(folders) > 1:
            messagebox.showerror(
                "Αδυναμία εκτέλεσης",
                "Η επιλογή 'Χωρίς φάκελο (αρχεία χύμα)' μπορεί να χρησιμοποιηθεί μόνο με έναν επιλεγμένο φάκελο.\n\n"
                "Παρακαλώ επιλέξτε μόνο έναν φάκελο ή αλλάξτε τον τρόπο αντιγραφής σε 'Μαζί με τον φάκελο'."
            )
            return

        # Δημιουργία popup επιβεβαίωσης
        confirm = tk.Toplevel(self.root)
        confirm.title("Επιβεβαίωση")
        confirm.geometry("550x400")
        confirm.resizable(False, False)
        confirm.configure(bg="#f0f0f0")
        confirm.transient(self.root)
        confirm.grab_set()

        # Κέντρο παραθύρου
        confirm.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (confirm.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (confirm.winfo_height() // 2)
        confirm.geometry(f"+{x}+{y}")

        # Τίτλος
        title_label = tk.Label(
            confirm,
            text="Παρακαλώ επιβεβαιώστε:",
            font=("Arial", 16, "bold"),
            bg="#f0f0f0",
            fg="#333333"
        )
        title_label.pack(pady=(20, 15))

        # Πλαίσιο με λεπτομέρειες
        details_frame = tk.Frame(confirm, bg="#ffffff", relief=tk.SUNKEN, bd=2)
        details_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 15))

        details_text = tk.Text(
            details_frame,
            font=("Arial", 12),
            bg="#ffffff",
            fg="#333333",
            wrap=tk.WORD,
            height=10,
            relief=tk.FLAT,
            padx=10,
            pady=10
        )
        details_text.pack(fill=tk.BOTH, expand=True)

        # Σύνταξη λεπτομερειών
        if direction == "to_usb":
            details_text.insert(tk.END, "📤 Αντιγραφή από Υπολογιστή προς USB\n\n")
            details_text.insert(tk.END, "Θα αντιγραφούν:\n")
            for folder in folders:
                file_count = count_files_in_folders([folder])
                details_text.insert(tk.END, f"  • {folder} ({file_count} αρχεία)\n")
            
            usb_drives = find_usb_drives()
            if len(usb_drives) == 1:
                details_text.insert(tk.END, f"\n📍 Προορισμός: {usb_drives[0]}")
            else:
                details_text.insert(tk.END, f"\n📍 Προορισμός: USB drive")
            
            if copy_mode == "with_folder":
                details_text.insert(tk.END, "\n📁 Τρόπος: Με τους φακέλους (ολόκληροι οι φάκελοι)")
            else:
                details_text.insert(tk.END, "\n📁 Τρόπος: Χωρίς τους φακέλους (μόνο τα περιεχόμενά τους, με την εσωτερική δομή)")
        else:
            details_text.insert(tk.END, "📥 Αντιγραφή από USB προς Υπολογιστή\n\n")
            details_text.insert(tk.END, "Θα αντιγραφούν πίσω:\n")
            for folder in folders:
                folder_name = os.path.basename(folder)
                details_text.insert(tk.END, f"  • {folder_name} → {folder}\n")
            
            usb_drives = find_usb_drives()
            if len(usb_drives) == 1:
                details_text.insert(tk.END, f"\n📍 Προέλευση: {usb_drives[0]}")
            else:
                details_text.insert(tk.END, f"\n📍 Προέλευση: USB drive")
            
            if copy_mode == "with_folder":
                details_text.insert(tk.END, "\n📁 Τρόπος: Με τους φακέλους (ολόκληροι οι φάκελοι)")
            else:
                details_text.insert(tk.END, "\n📁 Τρόπος: Χωρίς τους φακέλους (μόνο τα περιεχόμενά τους, με την εσωτερική δομή)")

        details_text.insert(tk.END, "\n\n⚠ ΣΗΜΑΝΤΙΚΟ: Κανένα αρχείο δεν θα διαγραφεί.")
        details_text.config(state=tk.DISABLED)

        # Κουμπιά
        btn_frame = tk.Frame(confirm, bg="#f0f0f0")
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        cancel_btn = tk.Button(
            btn_frame,
            text="✖ Ακύρωση",
            font=("Arial", 14),
            bg="#f44336",
            fg="white",
            activebackground="#d32f2f",
            activeforeground="white",
            relief=tk.RAISED,
            bd=2,
            padx=30,
            pady=10,
            command=confirm.destroy
        )
        cancel_btn.pack(side=tk.RIGHT, padx=(10, 0))

        ok_btn = tk.Button(
            btn_frame,
            text="✓ ΟΚ, Ξεκίνα",
            font=("Arial", 14, "bold"),
            bg="#4CAF50",
            fg="white",
            activebackground="#45a049",
            activeforeground="white",
            relief=tk.RAISED,
            bd=2,
            padx=30,
            pady=10,
            command=lambda: self.on_confirm(confirm)
        )
        ok_btn.pack(side=tk.RIGHT)

    def on_confirm(self, confirm_window):
        """Καλείται όταν ο χρήστης πατήσει ΟΚ στο popup."""
        confirm_window.destroy()
        self.start_backup()

    # ============================================================
    # ΡΥΘΜΙΣΕΙΣ
    # ============================================================

    def open_settings(self):
        """Ανοίγει το παράθυρο ρυθμίσεων."""
        if self.is_running:
            messagebox.showwarning("Προσοχή", "Δεν μπορείτε να αλλάξετε ρυθμίσεις ενώ γίνεται αντιγραφή.")
            return

        SettingsWindow(self.root, self.settings, self.on_settings_saved)

    def on_settings_saved(self, new_settings):
        """Καλείται όταν αποθηκεύονται οι ρυθμίσεις."""
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
        """Ξεκινά τη διαδικασία backup σε ξεχωριστό thread."""
        folders = self.settings.get("source_folders", [])
        direction = self.settings.get("direction", "to_usb")
        copy_mode = self.settings.get("copy_mode", "with_folder")

        # Έλεγχος: λειτουργία χωρίς φάκελο μόνο με ένα φάκελο (ήδη έγινε στο confirm)
        if copy_mode == "without_folder" and len(folders) > 1:
            return

        if direction == "to_usb":
            # Έλεγχος USB drives
            usb_drives = find_usb_drives()
            if len(usb_drives) == 0:
                messagebox.showerror("Σφάλμα", "Δεν βρέθηκε USB drive.\n\nΠαρακαλώ συνδέστε ένα USB drive στον υπολογιστή.")
                return
            elif len(usb_drives) > 1:
                drives_text = ", ".join(usb_drives)
                messagebox.showerror("Σφάλμα", 
                    f"Βρέθηκαν πολλά USB drives: {drives_text}\n\n"
                    "Παρακαλώ αποσυνδέστε τα επιπλέον USB drives και κρατήστε μόνο ένα.")
                return
            self.target_drive = usb_drives[0]
        else:
            # Αντιγραφή προς υπολογιστή - έλεγχος USB
            usb_drives = find_usb_drives()
            if len(usb_drives) == 0:
                messagebox.showerror("Σφάλμα", "Δεν βρέθηκε USB drive.\n\nΠαρακαλώ συνδέστε το USB drive που περιέχει τα αρχεία.")
                return
            elif len(usb_drives) > 1:
                drives_text = ", ".join(usb_drives)
                messagebox.showerror("Σφάλμα", 
                    f"Βρέθηκαν πολλά USB drives: {drives_text}\n\n"
                    "Παρακαλώ αποσυνδέστε τα επιπλέον USB drives και κρατήστε μόνο ένα.")
                return
            self.target_drive = usb_drives[0]

        # Απενεργοποίηση κουμπιών
        self.copy_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.NORMAL)
        self.is_running = True
        self.cancel_flag = False
        self.error_count = 0

        # Καθαρισμός προηγούμενων αποτελεσμάτων
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)
        self.result_text.config(state=tk.DISABLED)

        if direction == "to_usb":
            self.log_result(f"🔄 Έναρξη αντιγραφής προς: {self.target_drive}")
        else:
            self.log_result(f"🔄 Έναρξη αντιγραφής από: {self.target_drive}")
        self.log_result(f"📂 Φάκελοι: {len(folders)}")

        # Ξεκινάμε το backup σε ξεχωριστό thread
        self.backup_thread = threading.Thread(target=self.run_backup, args=(folders, direction), daemon=True)
        self.backup_thread.start()

    def run_backup(self, folders, direction):
        """Εκτελεί το backup (τρέχει σε background thread)."""
        start_time = time.time()
        copy_mode = self.settings.get("copy_mode", "with_folder")

        # Βοηθητική συνάρτηση για σύγκριση αρχείων
        def is_same_file(src, dest, direction):
            """Επιστρέφει True αν τα αρχεία είναι ίδια (μέγεθος και ημερομηνία με ανοχή)."""
            try:
                src_size = os.path.getsize(src)
                dest_size = os.path.getsize(dest)
                if src_size != dest_size:
                    return False
                # Το μέγεθος είναι ίδιο, ελέγχουμε ημερομηνία
                src_mtime = os.path.getmtime(src)
                dest_mtime = os.path.getmtime(dest)
                diff = abs(src_mtime - dest_mtime)
                if direction == "to_usb":
                    # Για USB (συνήθως FAT32) ανάλυση 2 δευτερολέπτων
                    tolerance = 2.0
                else:
                    # Για υπολογιστή (NTFS) ανάλυση 1 δευτερολέπτου
                    tolerance = 1.0
                return diff <= tolerance
            except:
                return False

        try:
            # Υπολογισμός συνολικών αρχείων για progress bar
            all_files = []
            
            if direction == "to_usb":
                # Αντιγραφή από υπολογιστή προς USB
                for folder in folders:
                    if self.cancel_flag:
                        break
                    if not os.path.exists(folder):
                        self.root.after(0, self.log_result, f"⚠ Ο φάκελος {folder} δεν βρέθηκε. Παρακαλώ ελέγξτε τις Ρυθμίσεις.")
                        continue
                    for root_dir, dirs, files in os.walk(folder):
                        if self.cancel_flag:
                            break
                        for file in files:
                            src_path = os.path.join(root_dir, file)
                            all_files.append((src_path, folder, "pc_to_usb"))
            else:
                # Αντιγραφή από USB προς υπολογιστή
                for folder in folders:
                    if self.cancel_flag:
                        break
                    folder_name = os.path.basename(folder)
                    
                    if copy_mode == "with_folder":
                        usb_source = os.path.join(self.target_drive, folder_name)
                    else:
                        usb_source = self.target_drive
                    
                    if not os.path.exists(usb_source):
                        self.root.after(0, self.log_result, f"⚠ Δεν βρέθηκε ο φάκελος {folder_name} στο USB drive.")
                        continue
                    
                    for root_dir, dirs, files in os.walk(usb_source):
                        if self.cancel_flag:
                            break
                        for file in files:
                            src_path = os.path.join(root_dir, file)
                            all_files.append((src_path, folder, "usb_to_pc"))

            total_files = len(all_files)
            if total_files == 0:
                self.root.after(0, self.backup_finished, 0, 0, 0, start_time, "Δεν βρέθηκαν αρχεία προς αντιγραφή.")
                return

            # Αντιγραφή αρχείων
            copied_count = 0
            skipped_count = 0
            bytes_copied = 0

            for idx, (src_path, folder, file_type) in enumerate(all_files):
                if self.cancel_flag:
                    self.root.after(0, self.log_result, "⏹ Η αντιγραφή ακυρώθηκε από τον χρήστη.")
                    break

                # ===== ΥΠΟΛΟΓΙΣΜΟΣ ΠΡΟΟΡΙΣΜΟΥ =====
                if file_type == "pc_to_usb":
                    if copy_mode == "with_folder":
                        # Με φάκελο: κρατάμε το σχετικό μονοπάτι από τον γονικό του επιλεγμένου φακέλου
                        rel_path = os.path.relpath(src_path, os.path.dirname(folder))
                        dest_path = os.path.join(self.target_drive, rel_path)
                    else:
                        # Χωρίς φάκελο: το σχετικό μονοπάτι ΜΕΣΑ στον επιλεγμένο φάκελο
                        rel_path = os.path.relpath(src_path, folder)
                        dest_path = os.path.join(self.target_drive, rel_path)
                else:
                    # usb_to_pc
                    if copy_mode == "with_folder":
                        folder_name = os.path.basename(folder)
                        usb_source = os.path.join(self.target_drive, folder_name)
                        rel_path = os.path.relpath(src_path, usb_source)
                        dest_path = os.path.join(folder, rel_path)
                    else:
                        # Χωρίς φάκελο: τα αρχεία βρίσκονται στη ρίζα του USB
                        usb_source = self.target_drive
                        rel_path = os.path.relpath(src_path, usb_source)
                        dest_path = os.path.join(folder, rel_path)

                # Ενημέρωση progress
                progress_pct = int((idx + 1) / total_files * 100)
                elapsed = time.time() - start_time
                if idx > 0:
                    avg_time_per_file = elapsed / (idx + 1)
                    remaining = avg_time_per_file * (total_files - idx - 1)
                else:
                    remaining = 0

                self.root.after(0, self.update_progress, progress_pct, idx + 1, total_files, remaining)

                # ========== ΕΛΕΓΧΟΣ ΥΠΑΡΞΗΣ ==========
                if os.path.exists(dest_path):
                    if is_same_file(src_path, dest_path, direction):
                        skipped_count += 1
                        continue

                # Αντιγραφή αρχείου
                try:
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    shutil.copy2(src_path, dest_path)
                    copied_count += 1
                    bytes_copied += os.path.getsize(src_path)
                except Exception as e:
                    self.error_count += 1
                    error_msg = f"⚠ Σφάλμα αντιγραφής: {os.path.basename(src_path)} - {str(e)}"
                    self.root.after(0, self.log_result, error_msg)

            # Τέλος backup
            end_time = time.time()
            duration = end_time - start_time
            
            # Έλεγχος αν το USB αποσυνδέθηκε
            if self.error_count > 5 and copied_count == 0:
                self.root.after(0, self.log_result, "❌ Το USB drive αποσυνδέθηκε ή παρουσιάστηκε σφάλμα.")
                self.root.after(0, self.backup_finished, copied_count, skipped_count, bytes_copied, duration, "USB_ERROR")
            elif self.cancel_flag:
                self.root.after(0, self.backup_finished, copied_count, skipped_count, bytes_copied, duration, "ΑΚΥΡΩΘΗΚΕ")
            else:
                self.root.after(0, self.backup_finished, copied_count, skipped_count, bytes_copied, duration, "ΟΛΟΚΛΗΡΩΘΗΚΕ")

        except Exception as e:
            self.root.after(0, self.log_result, f"❌ Σφάλμα: {str(e)}")
            self.root.after(0, self.backup_finished, 0, 0, 0, time.time() - start_time, "ΣΦΑΛΜΑ")

    def update_progress(self, pct, current, total, remaining):
        """Ενημερώνει το progress bar και τις ετικέτες."""
        self.progress['value'] = pct
        self.progress_label.config(text=f"Αντιγραφή: {current} από {total} αρχεία ({pct}%)")
        
        if remaining > 0:
            self.time_label.config(text=f"Υπολειπόμενος χρόνος: {format_time(remaining)}")
        else:
            self.time_label.config(text="")

        self.root.update_idletasks()

    def backup_finished(self, copied, skipped, bytes_copied, duration, status):
        """Καλείται όταν ολοκληρωθεί το backup."""
        self.is_running = False
        self.cancel_btn.config(state=tk.DISABLED)
        self.copy_btn.config(state=tk.NORMAL)
        self.progress['value'] = 100
        self.progress_label.config(text="")
        self.time_label.config(text="")

        direction = self.settings.get("direction", "to_usb")

        if status == "ΟΛΟΚΛΗΡΩΘΗΚΕ":
            self.log_result("=" * 50)
            self.log_result(f"✅ Η αντιγραφή ολοκληρώθηκε επιτυχώς!")
            self.log_result(f"📊 Αντιγράφηκαν: {copied} αρχεία ({get_file_size(bytes_copied)})")
            if skipped > 0:
                self.log_result(f"⏭ Παραλείφθηκαν (ήδη υπάρχουν): {skipped} αρχεία")
            if self.error_count > 0:
                self.log_result(f"⚠ Απέτυχαν: {self.error_count} αρχεία")
                if self.error_count >= 3:
                    messagebox.showwarning("Προσοχή", 
                        f"Απέτυχαν {self.error_count} αρχεία. Μπορεί να οφείλεται σε:\n"
                        "- Αποσύνδεση USB κατά τη διάρκεια\n"
                        "- Αρχεία που είναι ανοιχτά από άλλο πρόγραμμα\n"
                        "- Το USB είναι γεμάτο")
            self.log_result(f"⏱ Χρόνος: {format_time(duration)}")
            if direction == "to_usb":
                self.log_result(f"📍 Προορισμός: {self.target_drive}")
            else:
                self.log_result(f"📍 Προέλευση: {self.target_drive}")
            self.log_result("=" * 50)
        elif status == "ΑΚΥΡΩΘΗΚΕ":
            self.log_result("=" * 50)
            self.log_result(f"⏹ Η αντιγραφή ακυρώθηκε.")
            self.log_result(f"📊 Αντιγράφηκαν: {copied} αρχεία ({get_file_size(bytes_copied)})")
            self.log_result(f"⏱ Χρόνος: {format_time(duration)}")
            self.log_result("=" * 50)
        elif status == "USB_ERROR":
            self.log_result("=" * 50)
            self.log_result("❌ Το USB drive αποσυνδέθηκε κατά τη διάρκεια της αντιγραφής!")
            self.log_result(f"📊 Αντιγράφηκαν: {copied} αρχεία ({get_file_size(bytes_copied)})")
            self.log_result("💡 Την επόμενη φορά θα συνεχίσει από εκεί που έμεινε.")
            self.log_result("=" * 50)
            messagebox.showerror("Σφάλμα", 
                "Το USB drive αποσυνδέθηκε κατά τη διάρκεια της αντιγραφής!\n\n"
                "Μην ανησυχείτε, την επόμενη φορά που θα πατήσετε Αντιγραφή,\n"
                "θα συνεχίσει από εκεί που έμεινε.")
        elif status == "ΣΦΑΛΜΑ":
            self.log_result("=" * 50)
            self.log_result("❌ Η αντιγραφή απέτυχε.")
            self.log_result("=" * 50)
        else:
            self.log_result(status)

        # Επαναφορά progress bar
        self.root.after(2000, self.reset_progress)

    def reset_progress(self):
        """Επαναφέρει το progress bar."""
        self.progress['value'] = 0

    def cancel_backup(self):
        """Ακυρώνει τη διαδικασία backup."""
        self.cancel_flag = True
        self.cancel_btn.config(state=tk.DISABLED, text="Ακύρωση...")
        self.log_result("⏹ Ακύρωση σε εξέλιξη...")

    def on_close(self):
        """Κλείσιμο εφαρμογής."""
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
        self.window.geometry("600x550")
        self.window.resizable(True, True)
        self.window.minsize(500, 450)
        self.window.configure(bg="#f0f0f0")
        self.window.transient(parent)
        self.window.grab_set()

        self.create_widgets()

        # Κέντρο παραθύρου
        self.window.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.window.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.window.winfo_height() // 2)
        self.window.geometry(f"+{x}+{y}")

    def create_widgets(self):
        """Δημιουργεί τα widgets του παραθύρου ρυθμίσεων."""
        
        # Επεξήγηση
        header = tk.Label(
            self.window,
            text="Επιλέξτε τους φακέλους που θέλετε να αντιγράφονται:",
            font=("Arial", 12),
            bg="#f0f0f0",
            fg="#333333",
            wraplength=550,
            justify=tk.LEFT
        )
        header.pack(pady=(15, 10), padx=15, anchor=tk.W)

        # Πλαίσιο λίστας φακέλων
        list_frame = tk.Frame(self.window, bg="#f0f0f0")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))

        # Listbox με scrollbar
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.folders_listbox = tk.Listbox(
            list_frame,
            font=("Arial", 11),
            selectmode=tk.SINGLE,
            yscrollcommand=scrollbar.set,
            relief=tk.SUNKEN,
            bd=2,
            bg="#ffffff"
        )
        self.folders_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.folders_listbox.yview)

        # Γέμισμα λίστας με τους αποθηκευμένους φακέλους
        for folder in self.settings.get("source_folders", []):
            self.folders_listbox.insert(tk.END, folder)

        # Κουμπιά διαχείρισης φακέλων
        btn_frame = tk.Frame(self.window, bg="#f0f0f0")
        btn_frame.pack(fill=tk.X, padx=15, pady=(0, 10))

        add_btn = tk.Button(
            btn_frame,
            text="➕ Προσθήκη φακέλου",
            font=("Arial", 11),
            bg="#2196F3",
            fg="white",
            activebackground="#1976D2",
            activeforeground="white",
            relief=tk.RAISED,
            bd=2,
            padx=15,
            pady=5,
            command=self.add_folder
        )
        add_btn.pack(side=tk.LEFT, padx=(0, 10))

        remove_btn = tk.Button(
            btn_frame,
            text="✖ Αφαίρεση επιλεγμένου",
            font=("Arial", 11),
            bg="#FF9800",
            fg="white",
            activebackground="#F57C00",
            activeforeground="white",
            relief=tk.RAISED,
            bd=2,
            padx=15,
            pady=5,
            command=self.remove_folder
        )
        remove_btn.pack(side=tk.LEFT)

        # ===== Διαχωριστική γραμμή =====
        sep = ttk.Separator(self.window, orient='horizontal')
        sep.pack(fill=tk.X, padx=15, pady=5)

        # ===== Ρυθμίσεις αντιγραφής =====
        settings_header = tk.Label(
            self.window,
            text="Ρυθμίσεις αντιγραφής:",
            font=("Arial", 12, "bold"),
            bg="#f0f0f0",
            fg="#333333",
            anchor=tk.W
        )
        settings_header.pack(pady=(10, 5), padx=15, anchor=tk.W)

        # 1. Τρόπος αντιγραφής (με ή χωρίς φάκελο)
        mode_frame = tk.Frame(self.window, bg="#f0f0f0")
        mode_frame.pack(fill=tk.X, padx=15, pady=(0, 5))

        mode_label = tk.Label(
            mode_frame,
            text="Τρόπος αντιγραφής:",
            font=("Arial", 11),
            bg="#f0f0f0",
            fg="#333333"
        )
        mode_label.pack(side=tk.LEFT, padx=(0, 10))

        self.copy_mode_var = tk.StringVar(value=self.settings.get("copy_mode", "with_folder"))

        with_folder_rb = tk.Radiobutton(
            mode_frame,
            text="Μαζί με τον φάκελο",
            font=("Arial", 11),
            variable=self.copy_mode_var,
            value="with_folder",
            bg="#f0f0f0",
            activebackground="#f0f0f0"
        )
        with_folder_rb.pack(side=tk.LEFT, padx=(0, 15))

        without_folder_rb = tk.Radiobutton(
            mode_frame,
            text="Χωρίς φάκελο (τα περιεχόμενά του)",
            font=("Arial", 11),
            variable=self.copy_mode_var,
            value="without_folder",
            bg="#f0f0f0",
            activebackground="#f0f0f0"
        )
        without_folder_rb.pack(side=tk.LEFT)

        # 2. Κατεύθυνση αντιγραφής
        dir_frame = tk.Frame(self.window, bg="#f0f0f0")
        dir_frame.pack(fill=tk.X, padx=15, pady=(5, 10))

        dir_label = tk.Label(
            dir_frame,
            text="Κατεύθυνση:",
            font=("Arial", 11),
            bg="#f0f0f0",
            fg="#333333"
        )
        dir_label.pack(side=tk.LEFT, padx=(0, 10))

        self.direction_var = tk.StringVar(value=self.settings.get("direction", "to_usb"))

        to_usb_rb = tk.Radiobutton(
            dir_frame,
            text="Αντιγραφή σε USB",
            font=("Arial", 11),
            variable=self.direction_var,
            value="to_usb",
            bg="#f0f0f0",
            activebackground="#f0f0f0"
        )
        to_usb_rb.pack(side=tk.LEFT, padx=(0, 15))

        to_pc_rb = tk.Radiobutton(
            dir_frame,
            text="Αντιγραφή σε Υπολογιστή",
            font=("Arial", 11),
            variable=self.direction_var,
            value="to_pc",
            bg="#f0f0f0",
            activebackground="#f0f0f0"
        )
        to_pc_rb.pack(side=tk.LEFT)

        # ===== Κουμπιά αποθήκευσης/ακύρωσης =====
        bottom_frame = tk.Frame(self.window, bg="#f0f0f0")
        bottom_frame.pack(fill=tk.X, padx=15, pady=(10, 15))

        save_btn = tk.Button(
            bottom_frame,
            text="✓ Αποθήκευση",
            font=("Arial", 12, "bold"),
            bg="#4CAF50",
            fg="white",
            activebackground="#45a049",
            activeforeground="white",
            relief=tk.RAISED,
            bd=2,
            padx=20,
            pady=8,
            command=self.save
        )
        save_btn.pack(side=tk.RIGHT, padx=(10, 0))

        cancel_btn = tk.Button(
            bottom_frame,
            text="✖ Ακύρωση",
            font=("Arial", 12),
            bg="#f44336",
            fg="white",
            activebackground="#d32f2f",
            activeforeground="white",
            relief=tk.RAISED,
            bd=2,
            padx=20,
            pady=8,
            command=self.window.destroy
        )
        cancel_btn.pack(side=tk.RIGHT)

    def add_folder(self):
        """Ανοίγει διάλογο για επιλογή φακέλου."""
        folder = filedialog.askdirectory(
            title="Επιλέξτε φάκελο για backup",
            mustexist=True
        )
        if folder:
            existing = self.folders_listbox.get(0, tk.END)
            if folder not in existing:
                self.folders_listbox.insert(tk.END, folder)
            else:
                messagebox.showinfo("Πληροφορία", "Ο φάκελος υπάρχει ήδη στη λίστα.")

    def remove_folder(self):
        """Αφαιρεί τον επιλεγμένο φάκελο από τη λίστα."""
        selected = self.folders_listbox.curselection()
        if selected:
            self.folders_listbox.delete(selected[0])
        else:
            messagebox.showwarning("Προσοχή", "Παρακαλώ επιλέξτε έναν φάκελο από τη λίστα για αφαίρεση.")

    def save(self):
        """Αποθηκεύει τις ρυθμίσεις και κλείνει το παράθυρο."""
        folders = list(self.folders_listbox.get(0, tk.END))
        if not folders:
            if not messagebox.askyesno("Επιβεβαίωση", 
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