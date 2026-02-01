#!/usr/bin/env python3
"""
NaniLabs Database Backup Script
Backup all SQLite databases with timestamp
"""

import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
import json
import gzip

# Configuration
ROOT_DIR = Path(__file__).parent.parent
BACKUP_DIR = ROOT_DIR / "backups"
MAX_BACKUPS = 10  # Keep only last N backups

DATABASES = {
    "aura_infra": ROOT_DIR / "aura-infra" / "src" / "aura_infra.db",
    "nexus_mail": ROOT_DIR / "nexus-mail" / "src" / "nexus_mail.db",
    "aura_agent": ROOT_DIR / "autonomous-agents" / "data" / "aura.db"
}


def get_db_stats(db_path: Path) -> dict:
    """Get statistics from a database"""
    if not db_path.exists():
        return {"exists": False}
    
    stats = {
        "exists": True,
        "size_bytes": db_path.stat().st_size,
        "size_mb": round(db_path.stat().st_size / (1024 * 1024), 2)
    }
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        stats["tables"] = tables
        
        # Get row counts
        stats["row_counts"] = {}
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats["row_counts"][table] = cursor.fetchone()[0]
            except:
                pass
        
        conn.close()
    except Exception as e:
        stats["error"] = str(e)
    
    return stats


def backup_database(name: str, db_path: Path, backup_dir: Path, compress: bool = True) -> dict:
    """Backup a single database"""
    if not db_path.exists():
        return {"success": False, "error": f"Database not found: {db_path}"}
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{name}_{timestamp}.db"
    if compress:
        backup_name += ".gz"
    
    backup_path = backup_dir / backup_name
    
    try:
        if compress:
            # Compress while copying
            with open(db_path, 'rb') as f_in:
                with gzip.open(backup_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            shutil.copy2(db_path, backup_path)
        
        stats = get_db_stats(db_path)
        
        return {
            "success": True,
            "backup_path": str(backup_path),
            "original_size": stats.get("size_bytes", 0),
            "backup_size": backup_path.stat().st_size,
            "compression_ratio": round(backup_path.stat().st_size / stats.get("size_bytes", 1), 2) if compress else 1.0,
            "stats": stats
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def cleanup_old_backups(backup_dir: Path, max_backups: int = MAX_BACKUPS):
    """Remove old backups, keeping only the most recent ones"""
    if not backup_dir.exists():
        return
    
    # Group backups by database name
    backups_by_db = {}
    for f in backup_dir.iterdir():
        if f.is_file() and (f.suffix == '.db' or f.name.endswith('.db.gz')):
            # Extract database name (everything before the timestamp)
            parts = f.stem.replace('.db', '').rsplit('_', 2)
            if len(parts) >= 2:
                db_name = '_'.join(parts[:-2]) if len(parts) > 2 else parts[0]
                if db_name not in backups_by_db:
                    backups_by_db[db_name] = []
                backups_by_db[db_name].append(f)
    
    # For each database, keep only the most recent backups
    for db_name, files in backups_by_db.items():
        files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        for old_file in files[max_backups:]:
            old_file.unlink()
            print(f"  Removed old backup: {old_file.name}")


def run_backup(compress: bool = True, verbose: bool = True):
    """Run full backup of all databases"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if verbose:
        print("\n" + "=" * 60)
        print("  🗄️  NaniLabs Database Backup")
        print("=" * 60)
        print(f"  Time: {timestamp}")
        print(f"  Backup dir: {BACKUP_DIR}")
        print("-" * 60)
    
    # Create backup directory
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    results = {}
    total_original = 0
    total_backup = 0
    
    for name, db_path in DATABASES.items():
        if verbose:
            print(f"\n  📦 Backing up {name}...")
        
        result = backup_database(name, db_path, BACKUP_DIR, compress)
        results[name] = result
        
        if result["success"]:
            total_original += result["original_size"]
            total_backup += result["backup_size"]
            
            if verbose:
                print(f"     ✓ Saved to: {Path(result['backup_path']).name}")
                print(f"     Size: {result['original_size']:,} → {result['backup_size']:,} bytes")
                if result.get("stats", {}).get("row_counts"):
                    for table, count in result["stats"]["row_counts"].items():
                        print(f"     - {table}: {count:,} rows")
        else:
            if verbose:
                print(f"     ✗ Failed: {result['error']}")
    
    # Cleanup old backups
    if verbose:
        print(f"\n  🧹 Cleaning up old backups...")
    cleanup_old_backups(BACKUP_DIR)
    
    # Summary
    if verbose:
        print("\n" + "-" * 60)
        print(f"  Total backed up: {total_original:,} → {total_backup:,} bytes")
        if total_original > 0:
            print(f"  Compression: {round(total_backup/total_original*100, 1)}%")
        print("=" * 60 + "\n")
    
    # Save backup manifest
    manifest = {
        "timestamp": timestamp,
        "results": results,
        "total_original_bytes": total_original,
        "total_backup_bytes": total_backup
    }
    
    manifest_path = BACKUP_DIR / "manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2, default=str)
    
    return results


def list_backups():
    """List all available backups"""
    if not BACKUP_DIR.exists():
        print("No backups found.")
        return
    
    print("\n" + "=" * 60)
    print("  📋 Available Backups")
    print("=" * 60)
    
    backups = sorted(BACKUP_DIR.glob("*.db*"), key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not backups:
        print("  No backups found.")
        return
    
    for backup in backups:
        size_kb = round(backup.stat().st_size / 1024, 1)
        mtime = datetime.fromtimestamp(backup.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"  {backup.name:<40} {size_kb:>8} KB  {mtime}")
    
    print("=" * 60 + "\n")


def restore_backup(backup_file: str, target_db: str = None):
    """Restore a database from backup"""
    backup_path = BACKUP_DIR / backup_file
    
    if not backup_path.exists():
        print(f"Backup file not found: {backup_file}")
        return False
    
    # Determine target database
    if target_db is None:
        # Try to infer from filename
        for name, db_path in DATABASES.items():
            if backup_file.startswith(name):
                target_db = name
                break
    
    if target_db is None or target_db not in DATABASES:
        print(f"Could not determine target database. Specify with --target")
        return False
    
    target_path = DATABASES[target_db]
    
    print(f"\n⚠️  This will overwrite: {target_path}")
    confirm = input("Are you sure? (yes/no): ")
    
    if confirm.lower() != 'yes':
        print("Restore cancelled.")
        return False
    
    try:
        # Backup current database first
        if target_path.exists():
            current_backup = target_path.with_suffix('.db.pre-restore')
            shutil.copy2(target_path, current_backup)
            print(f"  Current database backed up to: {current_backup.name}")
        
        # Restore
        if backup_file.endswith('.gz'):
            with gzip.open(backup_path, 'rb') as f_in:
                with open(target_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            shutil.copy2(backup_path, target_path)
        
        print(f"  ✓ Restored {backup_file} to {target_db}")
        return True
        
    except Exception as e:
        print(f"  ✗ Restore failed: {e}")
        return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="NaniLabs Database Backup Tool")
    parser.add_argument("action", choices=["backup", "list", "restore"], 
                       help="Action to perform")
    parser.add_argument("--file", help="Backup file to restore (for restore action)")
    parser.add_argument("--target", help="Target database (for restore action)")
    parser.add_argument("--no-compress", action="store_true", help="Don't compress backups")
    
    args = parser.parse_args()
    
    if args.action == "backup":
        run_backup(compress=not args.no_compress)
    elif args.action == "list":
        list_backups()
    elif args.action == "restore":
        if not args.file:
            print("Please specify backup file with --file")
            return
        restore_backup(args.file, args.target)


if __name__ == "__main__":
    main()
