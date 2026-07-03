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
            # 1. Convert to WAL mode for high concurrency
            cursor.execute("PRAGMA journal_mode;")
            mode = cursor.fetchone()[0]
            if mode.lower() != "wal":
                print(f"Converting {os.path.basename(db_path)} to WAL mode...")
                cursor.execute("PRAGMA journal_mode=WAL;")
                conn.commit()
            
            # 2. Align trajectory_id with cascade_id to fix on-demand load failure
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trajectory_meta';")
            if cursor.fetchone():
                cursor.execute("UPDATE trajectory_meta SET trajectory_id = cascade_id WHERE trajectory_id != cascade_id;")
                if conn.total_changes > 0:
                    print(f"Aligned trajectory_id with cascade_id in {os.path.basename(db_path)}")
                    conn.commit()
                    
            conn.close()
        except Exception as e:
            print(f"Error processing {db_path}: {e}")

if __name__ == "__main__":
    main()
