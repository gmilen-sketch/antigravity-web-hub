#!/usr/bin/env python3
import glob
import os
import sqlite3

CONVS_DIR = os.path.expanduser("~/.gemini/antigravity/conversations")

def main():
    db_files = glob.glob(os.path.join(CONVS_DIR, "*.db"))
    for db_path in db_files:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode;")
            mode = cursor.fetchone()[0]
            if mode.lower() != "wal":
                print(f"Converting {os.path.basename(db_path)} to WAL mode...")
                cursor.execute("PRAGMA journal_mode=WAL;")
                conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error checking/converting {db_path}: {e}")

if __name__ == "__main__":
    main()
