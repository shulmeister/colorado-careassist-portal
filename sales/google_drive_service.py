import os
import io
import logging
import requests
from typing import Optional, Tuple, List, Dict, Any
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import json
import re

logger = logging.getLogger(__name__)

class GoogleDriveService:
    """Service for interacting with Google Drive API"""
    
    def __init__(self):
        self.creds = None
        self.service = None
        self.enabled = False
        
        try:
            # Check for service account key in environment variable
            creds_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_KEY')
            if creds_json:
                creds_dict = json.loads(creds_json)
                self.creds = service_account.Credentials.from_service_account_info(
                    creds_dict,
                    scopes=['https://www.googleapis.com/auth/drive.readonly']
                )
                self.service = build('drive', 'v3', credentials=self.creds)
                self.enabled = True
                logger.info("Google Drive service initialized successfully")
            else:
                logger.warning("GOOGLE_SERVICE_ACCOUNT_KEY not found. Google Drive service disabled.")
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive service: {str(e)}")
    
    def download_file_from_url(self, url: str) -> Optional[Tuple[bytes, str, dict]]:
        """
        Download a file from a Google Drive URL
        Returns: (file_content, filename, metadata) or None if failed
        """
        if not self.enabled:
            logger.error("Google Drive service is not enabled")
            return None
            
        try:
            file_id = self._extract_file_id(url)
            if not file_id:
                logger.error(f"Could not extract file ID from URL: {url}")
                return None
                
            # Get file metadata
            file_metadata = self.service.files().get(
                fileId=file_id,
                fields='name, mimeType, owners, createdTime',
                supportsAllDrives=True
            ).execute()
            filename = file_metadata.get('name', 'downloaded_file')
            mime_type = file_metadata.get('mimeType', '')

            logger.info(f"Downloading file: {filename} (ID: {file_id}, Type: {mime_type})")

            # Download file content
            request = self.service.files().get_media(
                fileId=file_id,
                supportsAllDrives=True
            )
            file_io = io.BytesIO()
            downloader = MediaIoBaseDownload(file_io, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                # logger.debug(f"Download {int(status.progress() * 100)}%.")
                
            return file_io.getvalue(), filename, file_metadata
            
        except Exception as e:
            logger.error(f"Error downloading file from Drive: {str(e)}")
            return None
            
    def _extract_file_id(self, url: str) -> Optional[str]:
        """Extract Google Drive file ID from URL"""
        # Patterns for Drive URLs
        patterns = [
            r'drive\.google\.com\/file\/d\/([a-zA-Z0-9_-]+)',
            r'drive\.google\.com\/open\?id=([a-zA-Z0-9_-]+)',
            r'docs\.google\.com\/file\/d\/([a-zA-Z0-9_-]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
                
        return None

    def _extract_folder_id(self, url: str) -> Optional[str]:
        """Extract Google Drive folder ID from URL"""
        patterns = [
            r'drive\.google\.com\/drive\/folders\/([a-zA-Z0-9_-]+)',
            r'drive\.google\.com\/drive\/u\/\d+\/folders\/([a-zA-Z0-9_-]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def list_files_in_folder(self, folder_url: str, image_only: bool = True, recursive: bool = True) -> List[Dict[str, Any]]:
        """
        List all files in a Google Drive folder.
        If recursive=True, also scans subfolders.
        Returns list of dicts with: id, name, mimeType, createdTime
        """
        if not self.enabled:
            logger.error("Google Drive service is not enabled")
            return []

        folder_id = self._extract_folder_id(folder_url)
        if not folder_id:
            logger.error(f"Could not extract folder ID from URL: {folder_url}")
            return []

        return self._list_files_recursive(folder_id, image_only, recursive)

    def _list_files_recursive(self, folder_id: str, image_only: bool, recursive: bool, depth: int = 0) -> List[Dict[str, Any]]:
        """Internal recursive file listing."""
        if depth > 5:  # Prevent infinite recursion
            return []
        
        try:
            all_files = []
            
            # First, get image files in this folder
            if image_only:
                query = f"'{folder_id}' in parents and trashed = false and (mimeType contains 'image/')"
            else:
                query = f"'{folder_id}' in parents and trashed = false and mimeType != 'application/vnd.google-apps.folder'"

            page_token = None
            while True:
                response = self.service.files().list(
                    q=query,
                    spaces='drive',
                    fields='nextPageToken, files(id, name, mimeType, createdTime)',
                    pageToken=page_token,
                    pageSize=100,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                    corpora='allDrives'
                ).execute()
                all_files.extend(response.get('files', []))
                page_token = response.get('nextPageToken')
                if not page_token:
                    break

            logger.info(f"Found {len(all_files)} files in folder {folder_id} (depth {depth})")

            # If recursive, also scan subfolders
            if recursive:
                subfolder_query = f"'{folder_id}' in parents and trashed = false and mimeType = 'application/vnd.google-apps.folder'"
                page_token = None
                subfolders = []
                while True:
                    response = self.service.files().list(
                        q=subfolder_query,
                        spaces='drive',
                        fields='nextPageToken, files(id, name)',
                        pageToken=page_token,
                        pageSize=100,
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                        corpora='allDrives'
                    ).execute()
                    subfolders.extend(response.get('files', []))
                    page_token = response.get('nextPageToken')
                    if not page_token:
                        break

                for subfolder in subfolders:
                    subfolder_id = subfolder.get('id')
                    subfolder_name = subfolder.get('name', 'unknown')
                    logger.info(f"Scanning subfolder: {subfolder_name}")
                    subfolder_files = self._list_files_recursive(subfolder_id, image_only, recursive, depth + 1)
                    all_files.extend(subfolder_files)

            return all_files
        except Exception as e:
            logger.error(f"Error listing files in folder {folder_id}: {e}")
            return []

    def download_file_by_id(self, file_id: str) -> Optional[Tuple[bytes, str, dict]]:
        """Download a file by its ID. Returns (content, filename, metadata)."""
        if not self.enabled:
            return None
        try:
            file_metadata = self.service.files().get(
                fileId=file_id,
                fields='name, mimeType, owners, createdTime',
                supportsAllDrives=True
            ).execute()
            filename = file_metadata.get('name', 'downloaded_file')

            request = self.service.files().get_media(
                fileId=file_id,
                supportsAllDrives=True
            )
            file_io = io.BytesIO()
            downloader = MediaIoBaseDownload(file_io, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()

            return file_io.getvalue(), filename, file_metadata
        except Exception as e:
            logger.error(f"Error downloading file {file_id}: {e}")
            return None
