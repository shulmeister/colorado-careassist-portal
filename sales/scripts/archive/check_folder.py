"""Check folder contents."""
from google_drive_service import GoogleDriveService

drive = GoogleDriveService()
folder_url = "https://drive.google.com/drive/folders/1aGO6vxe50yA-1UcanPDEVlIFrXOMRYK4"

# List all files including subfolders
files = drive.list_files_in_folder(folder_url, image_only=False, recursive=True)
print(f"Found {len(files)} total items:")
for f in files[:30]:
    print(f"  {f['mimeType'][:30]:30} | {f['name']}")
if len(files) > 30:
    print(f"  ... and {len(files) - 30} more")
