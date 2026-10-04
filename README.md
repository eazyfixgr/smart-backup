# Smart Backup

A simple, reliable backup tool for Windows — copy your important folders to an external drive or USB with one click.

> **Download:** grab the latest `SmartBackup.exe` from the [Releases](https://github.com/eazyfixgr/smart-backup/releases) page. No installation required.

## Features

- Choose any folders/files to back up
- Back up to USB, external drive or another disk
- Progress feedback and safe threaded copying
- Lightweight single-file executable (no dependencies)
- Clean tkinter interface

## Getting started (run from source)

```bash
python easy_backup.py
```

## Build a standalone EXE

```bash
python -m pip install pyinstaller
python -m PyInstaller --onefile --windowed --name SmartBackup easy_backup.py
```

The executable is created in `dist/SmartBackup.exe`.

## License

Released under the [MIT License](LICENSE).

---

# Smart Backup (Ελληνικά)

Απλό και αξιόπιστο εργαλείο δημιουργίας αντιγράφων ασφαλείας για Windows. Αντιγράφει επιλεγμένους φακέλους σε USB ή εξωτερικό δίσκο με ένα κλικ.

> **Λήψη:** κατεβάστε το `SmartBackup.exe` από τη σελίδα [Releases](https://github.com/eazyfixgr/smart-backup/releases).

## Δυνατότητες

- Επιλογή φακέλων/αρχείων για backup
- Αντιγραφή σε USB, εξωτερικό δίσκο ή άλλο δίσκο
- Εμφάνιση προόδου με ασφαλή αντιγραφή (threading)
- Ελαφρύ εκτελέσιμο χωρίς εξαρτήσεις
