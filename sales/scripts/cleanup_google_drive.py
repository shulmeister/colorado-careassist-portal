#!/usr/bin/env python3
"""
Google Drive Cleanup Script for Colorado Care Assist

This script:
1. Scans all files in Google Drive (excluding trash)
2. Identifies duplicates by name and size
3. Identifies poorly named files (IMG_xxxx, Screenshot, etc.)
4. Creates an "Archive - Duplicates" folder
5. Moves duplicates and weirdly named files to archive

Usage:
    python sales/scripts/cleanup_google_drive.py --dry-run  # Preview only
    python sales/scripts/cleanup_google_drive.py           # Actually move files

Or via Mac Mini (Local):
    mac-mini run python sales/scripts/cleanup_google_drive.py --app careassist-unified
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from typing import List, Dict, Set, Tuple
from collections import defaultdict
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Patterns for "weird" filenames that should be archived
WEIRD_PATTERNS = [
    'IMG_',
    'Screenshot',
    'Screen Shot',
    'Untitled',
    'image',
    'Copy of',
    'download',
    'temp',
    'tmp',
    '(1)',
    '(2)',
    '(3)',
]

# Skip these folders (don't scan inside them)
SKIP_FOLDERS = [
    'Archive - Duplicates',
    'Archive',
    'Trash',
    '.Trash',
]


class DriveCleanupService:
    """Google Drive cleanup service with write permissions"""

    def __init__(self, dry_run=False):
        self.creds = None
        self.service = None
        self.enabled = False
        self.dry_run = dry_run

        try:
            # Check for service account key in environment variable
            creds_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_KEY')
            if not creds_json:
                raise Exception("GOOGLE_SERVICE_ACCOUNT_KEY not found in environment")

            creds_dict = json.loads(creds_json)
            # NOTE: Using full Drive access to enable file moving/organization
            self.creds = service_account.Credentials.from_service_account_info(
                creds_dict,
                scopes=['https://www.googleapis.com/auth/drive']  # Full access for cleanup
            )
            self.service = build('drive', 'v3', credentials=self.creds)
            self.enabled = True
            logger.info("✅ Google Drive service initialized with write permissions")

            if dry_run:
                logger.info("🔍 DRY RUN MODE: No files will actually be moved")

        except Exception as e:
            logger.error(f"❌ Failed to initialize Google Drive service: {str(e)}")
            raise

    def list_all_files(self, skip_folders: List[str] = None) -> List[Dict]:
        """
        List all files in Drive (excluding trash and specified folders)
        Returns: List of file dicts with id, name, mimeType, size, parents, createdTime
        """
        if skip_folders is None:
            skip_folders = SKIP_FOLDERS

        logger.info("📂 Scanning all files in Google Drive...")

        # First, get IDs of folders to skip
        skip_folder_ids = set()
        for folder_name in skip_folders:
            query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            results = self.service.files().list(
                q=query,
                fields='files(id, name)',
                pageSize=10
            ).execute()

            for folder in results.get('files', []):
                skip_folder_ids.add(folder['id'])
                logger.info(f"  ⏭️  Skipping folder: {folder['name']} ({folder['id']})")

        # Get all non-folder files
        all_files = []
        query = "trashed = false and mimeType != 'application/vnd.google-apps.folder'"
        page_token = None

        while True:
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='nextPageToken, files(id, name, mimeType, size, parents, createdTime, modifiedTime, owners)',
                pageToken=page_token,
                pageSize=100
            ).execute()

            files = results.get('files', [])

            # Filter out files in skip folders
            for file in files:
                parents = file.get('parents', [])
                # Skip if any parent is in skip_folder_ids
                if not any(parent in skip_folder_ids for parent in parents):
                    all_files.append(file)

            page_token = results.get('nextPageToken')
            if not page_token:
                break

        logger.info(f"✅ Found {len(all_files)} files (excluding skipped folders)")
        return all_files

    def find_duplicates(self, files: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Find duplicate files by name and size
        Returns: Dict mapping (name, size) -> List of file dicts
        """
        logger.info("🔍 Analyzing for duplicates...")

        # Group by (name, size)
        groups = defaultdict(list)
        for file in files:
            name = file.get('name', '')
            size = file.get('size', '0')  # Google Docs don't have size
            key = (name, size)
            groups[key].append(file)

        # Filter to only groups with 2+ files (duplicates)
        duplicates = {k: v for k, v in groups.items() if len(v) > 1}

        total_duplicate_files = sum(len(v) - 1 for v in duplicates.values())  # Keep oldest, count rest as dupes
        logger.info(f"📊 Found {len(duplicates)} sets of duplicates ({total_duplicate_files} duplicate files)")

        return duplicates

    def find_weird_names(self, files: List[Dict]) -> List[Dict]:
        """
        Find files with weird/generic names
        Returns: List of file dicts
        """
        logger.info("🔍 Analyzing for weird filenames...")

        weird_files = []
        for file in files:
            name = file.get('name', '')
            # Check if name matches any weird pattern
            if any(pattern.lower() in name.lower() for pattern in WEIRD_PATTERNS):
                weird_files.append(file)

        logger.info(f"📊 Found {len(weird_files)} files with weird names")
        return weird_files

    def create_archive_folder(self) -> str:
        """
        Create "Archive - Duplicates" folder in root if it doesn't exist
        Returns: Folder ID
        """
        folder_name = "Archive - Duplicates"

        # Check if folder already exists
        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = self.service.files().list(
            q=query,
            fields='files(id, name)',
            pageSize=1
        ).execute()

        existing = results.get('files', [])
        if existing:
            folder_id = existing[0]['id']
            logger.info(f"📁 Using existing archive folder: {folder_id}")
            return folder_id

        # Create new folder
        if self.dry_run:
            logger.info(f"📁 [DRY RUN] Would create folder: {folder_name}")
            return "DRY_RUN_FOLDER_ID"

        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }

        folder = self.service.files().create(
            body=folder_metadata,
            fields='id'
        ).execute()

        folder_id = folder.get('id')
        logger.info(f"📁 Created archive folder: {folder_id}")
        return folder_id

    def move_file(self, file_id: str, file_name: str, destination_folder_id: str) -> bool:
        """
        Move a file to destination folder
        Returns: True if successful
        """
        if self.dry_run:
            logger.info(f"  📦 [DRY RUN] Would move: {file_name}")
            return True

        try:
            # Get current parents
            file = self.service.files().get(
                fileId=file_id,
                fields='parents'
            ).execute()

            previous_parents = ",".join(file.get('parents', []))

            # Move file (remove from old parents, add to new parent)
            self.service.files().update(
                fileId=file_id,
                addParents=destination_folder_id,
                removeParents=previous_parents,
                fields='id, parents'
            ).execute()

            logger.info(f"  ✅ Moved: {file_name}")
            return True

        except Exception as e:
            logger.error(f"  ❌ Failed to move {file_name}: {e}")
            return False

    def cleanup_duplicates(self, duplicates: Dict[str, List[Dict]], archive_folder_id: str) -> Dict:
        """
        Move duplicate files to archive (keep oldest, move rest)
        Returns: Stats dict
        """
        logger.info("\n" + "="*60)
        logger.info("MOVING DUPLICATES TO ARCHIVE")
        logger.info("="*60)

        stats = {
            'moved': 0,
            'kept': 0,
            'failed': 0
        }

        for (name, size), file_list in duplicates.items():
            # Sort by creation time (oldest first)
            sorted_files = sorted(file_list, key=lambda f: f.get('createdTime', ''))

            # Keep oldest, move rest
            oldest = sorted_files[0]
            to_move = sorted_files[1:]

            logger.info(f"\n📄 {name} ({len(file_list)} copies)")
            logger.info(f"  ✅ Keeping oldest: {oldest.get('createdTime', 'unknown date')}")
            stats['kept'] += 1

            for file in to_move:
                created = file.get('createdTime', 'unknown date')
                logger.info(f"  📦 Moving duplicate from: {created}")

                success = self.move_file(file['id'], file['name'], archive_folder_id)
                if success:
                    stats['moved'] += 1
                else:
                    stats['failed'] += 1

        return stats

    def cleanup_weird_names(self, weird_files: List[Dict], archive_folder_id: str) -> Dict:
        """
        Move weirdly named files to archive
        Returns: Stats dict
        """
        logger.info("\n" + "="*60)
        logger.info("MOVING WEIRD FILENAMES TO ARCHIVE")
        logger.info("="*60)

        stats = {
            'moved': 0,
            'failed': 0
        }

        for file in weird_files:
            name = file.get('name', 'unknown')
            logger.info(f"  📦 {name}")

            success = self.move_file(file['id'], name, archive_folder_id)
            if success:
                stats['moved'] += 1
            else:
                stats['failed'] += 1

        return stats

    def run_cleanup(self, skip_weird_names=False):
        """
        Main cleanup workflow
        """
        logger.info("="*60)
        logger.info("GOOGLE DRIVE CLEANUP")
        logger.info(f"Started at: {datetime.utcnow().isoformat()}")
        logger.info("="*60)

        # Step 1: List all files
        all_files = self.list_all_files()

        if not all_files:
            logger.info("ℹ️  No files found to clean up")
            return

        # Step 2: Find duplicates
        duplicates = self.find_duplicates(all_files)

        # Step 3: Find weird names
        weird_files = []
        if not skip_weird_names:
            weird_files = self.find_weird_names(all_files)

        # Step 4: Create archive folder
        archive_folder_id = self.create_archive_folder()

        # Step 5: Move duplicates
        dup_stats = {'moved': 0, 'kept': 0, 'failed': 0}
        if duplicates:
            dup_stats = self.cleanup_duplicates(duplicates, archive_folder_id)
        else:
            logger.info("\nℹ️  No duplicates found")

        # Step 6: Move weird names
        weird_stats = {'moved': 0, 'failed': 0}
        if weird_files and not skip_weird_names:
            weird_stats = self.cleanup_weird_names(weird_files, archive_folder_id)
        elif not skip_weird_names:
            logger.info("\nℹ️  No weirdly named files found")

        # Summary
        logger.info("\n" + "="*60)
        logger.info("CLEANUP SUMMARY")
        logger.info("="*60)
        logger.info(f"Total files scanned: {len(all_files)}")
        logger.info(f"Duplicate sets found: {len(duplicates)}")
        logger.info(f"  - Originals kept: {dup_stats['kept']}")
        logger.info(f"  - Duplicates moved: {dup_stats['moved']}")
        logger.info(f"  - Failed: {dup_stats['failed']}")

        if not skip_weird_names:
            logger.info(f"Weirdly named files: {len(weird_files)}")
            logger.info(f"  - Moved to archive: {weird_stats['moved']}")
            logger.info(f"  - Failed: {weird_stats['failed']}")

        total_moved = dup_stats['moved'] + weird_stats['moved']
        total_failed = dup_stats['failed'] + weird_stats['failed']

        logger.info("-"*60)
        logger.info(f"TOTAL MOVED: {total_moved}")
        logger.info(f"TOTAL FAILED: {total_failed}")
        logger.info("="*60)

        if self.dry_run:
            logger.info("\n🔍 This was a DRY RUN. Run without --dry-run to actually move files.")


def main():
    parser = argparse.ArgumentParser(description='Clean up Google Drive duplicates and weird filenames')
    parser.add_argument('--dry-run', action='store_true', help='Preview only, do not move files')
    parser.add_argument('--skip-weird-names', action='store_true', help='Only process duplicates, skip weird names')
    args = parser.parse_args()

    try:
        cleanup_service = DriveCleanupService(dry_run=args.dry_run)
        cleanup_service.run_cleanup(skip_weird_names=args.skip_weird_names)

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
