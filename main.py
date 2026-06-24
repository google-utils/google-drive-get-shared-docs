from googleapiclient.discovery import build
from time import sleep
import json

from config import *


def get_all_users(workspace_data):
    """
    Returns all users from workspace
    """
    all_users = []
    admin_creds = get_admin_creds(f"./sa/adminitrator.json", workspace_data["admin"])
    service = build('admin', 'directory_v1', credentials=admin_creds)
    request = service.users().list(domain=workspace_data["domain"], query='isSuspended=false', maxResults=500)
    while request is not None:
        response = request.execute()
        all_users.extend(response.get('users', []))
        request = service.users().list_next(request, response)
    return all_users


def list_shared_documents(user_email, limit=None, supports_all_drives=False):
    """
    Returns a list of docs shared with user but not owned by them
    """
    print(f"Getting docs for {user_email} with limit='{limit}' and supports_all_drives='{supports_all_drives}'")
    user_creds = get_user_creds(f"./sa/adminitrator.json", user_email)
    service = build('drive', 'v3', credentials=user_creds)

    found_docs = 0
    page_num = 1

    # query = "'me' in readers and not 'me' in owners and trashed = false"
    # query = "'me' in writers and not 'me' in owners and trashed = false"
    query = "('me' in writers or 'me' in readers) and not 'me' in owners and trashed = false"
    fields = "nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, owners, permissions, driveId)"
    documents = []
    page_token = None

    mime_type_to_link = {
        "application/vnd.google-apps.document": "https://docs.google.com/document/d/",
        "application/vnd.google-apps.spreadsheet": "https://docs.google.com/spreadsheets/d/",
        "application/vnd.google-apps.presentation": "https://docs.google.com/presentation/d/",
        "application/vnd.google-apps.drawing": "https://docs.google.com/drawings/d/",
        "application/vnd.google-apps.folder": "https://drive.google.com/drive/folders/",
        "application/pdf": "https://drive.google.com/file/d/",
        "text/plain": "https://drive.google.com/file/d/",
        "image/jpeg": "https://drive.google.com/file/d/",
        "image/png": "https://drive.google.com/file/d/",
        "image/gif": "https://drive.google.com/file/d/",
        "video/mp4": "https://drive.google.com/file/d/",
        "application/zip": "https://drive.google.com/file/d/",
        # Add more mappings if you need
    }

    while True:
        try:
            if supports_all_drives:
                results = service.files().list(
                    q=query,
                    fields=fields,
                    pageToken=page_token,
                    corpora='allDrives',
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True
                ).execute()
            else:
                results = service.files().list(
                    q=query,
                    fields=fields,
                    pageToken=page_token,
                ).execute()

            items = results.get('files', [])
            found_docs = found_docs + len(items)
            print(f" Page {page_num}: Found {len(items)} docs (Total: {found_docs})")

            for item in items:
                mime_type = item.get('mimeType', 'N/A')
                if mime_type.startswith('application/vnd.google-apps.'):
                    mime_type = mime_type.replace('application/vnd.google-apps.', '')
                file_id = item.get('id', 'N/A')
                document_link = mime_type_to_link.get(mime_type, "https://drive.google.com/file/d/") + file_id
                perms = [perm['emailAddress'] for perm in item.get('permissions', []) if 'emailAddress' in perm]
                # if not perms:
                #     continue
                documents.append([
                    item.get('name', 'N/A'),
                    file_id,
                    document_link,
                    mime_type,
                    item.get('createdTime', 'N/A'),
                    item.get('modifiedTime', 'N/A'),
                    ', '.join([owner['emailAddress'] for owner in item.get('owners', [])]),
                    'N/A',  # Placeholder for Drive Name
                    ', '.join([perm['emailAddress'] for perm in item.get('permissions', []) if 'emailAddress' in perm]),
                    item.get('driveId', 'N/A')
                ])
            
            if limit and found_docs >= limit:
                break
            page_token = results.get('nextPageToken')
            if not page_token:
                break
            page_num += 1
        except Exception as e:
            print(f"Error searching files: {str(e)}")
            break

    return documents


def create_google_sheet(sheet_name):
    """
    Creates a new Google Sheet in the specified shared drive and returns its ID
    """
    sa_creds = get_sa_creds(f"./sa/adminitrator.json")
    service = build('drive', 'v3', credentials=sa_creds)
    sheets_service = build('sheets', 'v4', credentials=sa_creds)
    
    # Create the spreadsheet
    spreadsheet = {
        'properties': {
            'title': sheet_name
        }
    }
    spreadsheet = sheets_service.spreadsheets().create(body=spreadsheet, fields='spreadsheetId').execute()
    spreadsheet_id = spreadsheet.get('spreadsheetId')
    
    # Move the file to the shared drive
    file = service.files().update(
        fileId=spreadsheet_id,
        addParents='YOUR_SHARED_DRIVE_ID',
        supportsAllDrives=True,
        fields='id, parents'
    ).execute()
    
    return spreadsheet_id


def delete_sheet(service, sh_id, sheet_id):
    """
    Deletes a sheet from the spreadsheet
    """

    requests = [{
        "deleteSheet": {
            "sheetId": sheet_id
        }
    }]
    body = {
        'requests': requests
    }
    service.spreadsheets().batchUpdate(spreadsheetId=sh_id, body=body).execute()


def share_google_sheet(sh_id, user_email):
    """
    Shares the Google Sheet with the specified user
    """
    sa_creds = get_sa_creds(f"./sa/adminitrator.json")
    service = build('drive', 'v3', credentials=sa_creds)
    user_permission = {
        'type': 'user',
        'role': 'writer',
        'emailAddress': user_email
    }
    r = service.permissions().create(
        fileId=sh_id,
        body=user_permission,
        fields='id',
        supportsAllDrives=True
    ).execute()
    return r


def write_to_google_sheet(sh_id, email, data, shared_drives):
    """
    Write all the docs shared with the user to the spreadsheet_id in chunks of 1000 rows.
    """
    try:
        sa_creds = get_sa_creds(f"./sa/adminitrator.json")
        service = build('sheets', 'v4', credentials=sa_creds)
        sheet_service = service.spreadsheets()

        # Create a new sheet with the given email as the title
        requests = [{
            "addSheet": {
                "properties": {
                    "title": email
                }
            }
        }]
        body = {'requests': requests}
        sheet_service.batchUpdate(spreadsheetId=sh_id, body=body).execute()

        # Match all drive names
        for doc in data:
            drive_id = doc[9]  # Get drive ID from the last column
            drive_name = get_drive_name(drive_id, shared_drives)
            doc[7] = drive_name  # Update the Drive Name column

        # Prepare headers and data
        headers = ["Name", "ID", "Link", "Mime Type", "Created Time", "Modified Time", "Owners", "Drive Name", "Permissions"]
        # Remove driveId from each row
        data = [row[:-1] for row in data]
        
        # Combine headers and data
        all_data = [headers] + data

        # Write data in chunks of 1000 rows
        for i in range(0, len(all_data), 1000):
            chunk = all_data[i:i + 1000]
            request = sheet_service.values().append(
                spreadsheetId=sh_id,
                range=f"{email}!A1",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": chunk}
            )
            request.execute()

        print(f' + Data written to Google Sheet: {email}')

        # Delete default "Sheet1" if it exists
        try:
            sheet_metadata = sheet_service.get(spreadsheetId=sh_id).execute()
            if sheet_metadata['sheets'][0]['properties']['title'] == "Sheet1":
                delete_sheet(service, sh_id, sheet_metadata['sheets'][0]['properties']['sheetId'])
        except Exception as e:
            print(f"Error deleting Sheet1: {e}")

        return True
    except Exception as e:
        print(f"Error writing to Google Sheet: {e}")
        return False


def save_result_to_file(user_email, sh_id):
    """
    save shared sheet and user_email to the output.json
    """
    data_to_append = {
        "email": f"{user_email}",
        "file": f"https://docs.google.com/spreadsheets/d/{sh_id}"
    }

    try:
        with open('output.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
            if isinstance(data, list):
                data.append(data_to_append)
            else:
                data = [data, data_to_append]
    except FileNotFoundError:
        data = [data_to_append]

    with open('output.json', 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


def move_sa_files_to_shared_drive():
    """
    One-time operation to move all files owned by service account to shared drive
    """
    sa_creds = get_sa_creds(f"./sa/adminitrator.json")
    service = build('drive', 'v3', credentials=sa_creds)
    
    # Get service account email
    sa_info = service.about().get(fields='user').execute()
    sa_email = sa_info['user']['emailAddress']
    
    # Query for files owned by service account
    query = f"'{sa_email}' in owners"
    fields = "nextPageToken, files(id, name)"
    page_token = None
    moved_count = 0
    page_num = 1
    
    while True:
        try:
            results = service.files().list(
                q=query,
                fields=fields,
                pageToken=page_token,
                pageSize=1000,  # Increased page size
                corpora='allDrives',
                includeItemsFromAllDrives=True,
                supportsAllDrives=True
            ).execute()
            
            items = results.get('files', [])
            print(f"Page {page_num}: Found {len(items)} files")
            
            for item in items:
                try:
                    # Move file to shared drive
                    service.files().update(
                        fileId=item['id'],
                        addParents='YOUR_SHARED_DRIVE_ID',
                        supportsAllDrives=True,
                        fields='id, parents'
                    ).execute()
                    moved_count += 1
                    print(f"Moved: {item['name']}")
                except Exception as e:
                    print(f"Failed to move {item['name']}: {str(e)}")
            
            page_token = results.get('nextPageToken')
            if not page_token:
                break
            page_num += 1
                
        except Exception as e:
            print(f"Error listing files: {str(e)}")
            break
    
    print(f"\nTotal files moved: {moved_count}")
    print(f"Total pages processed: {page_num}")


def list_shared_drives(admin_email):
    """
    Lists all shared drives accessible to the admin account
    """
    admin_creds = get_admin_creds(f"./sa/adminitrator.json", admin_email)
    service = build('drive', 'v3', credentials=admin_creds)
    
    drives = []
    page_token = None
    
    while True:
        try:
            response = service.drives().list(
                pageSize=100,
                pageToken=page_token,
                fields="nextPageToken, drives(id, name, createdTime)"
            ).execute()
            
            for drive in response.get('drives', []):
                drives.append({
                    'id': drive.get('id'),
                    'name': drive.get('name'),
                    'created': drive.get('createdTime')
                })
            
            page_token = response.get('nextPageToken')
            if not page_token:
                break
                
        except Exception as e:
            print(f"Error listing shared drives: {str(e)}")
            break
    
    return drives


def get_drive_name(drive_id, shared_drives):
    """
    Get drive name from drive ID using shared drives list
    """
    for drive in shared_drives:
        if drive['id'] == drive_id:
            return drive['name']
    return 'N/A'


if __name__ == '__main__':
    # List all accessible shared drives
    print("\nListing all accessible shared drives:")
    shared_drives = list_shared_drives("your_admin_email@your_domain.com")
    print(len(shared_drives))
    
    # Uncomment to run the one-time operation
    # move_sa_files_to_shared_drive()
    # sleep(10)

    for account in desired_accounts:
        print(f'Processing user: {account["old"]}')
        user_docs = list_shared_documents(account["old"], limit=None, supports_all_drives=False)
        print(f"Found {len(user_docs)} docs")
        
        if user_docs:
            spreadsheet_id = create_google_sheet(f"Files shared with {account['old']}")
            insert_data = write_to_google_sheet(spreadsheet_id, account["old"], user_docs, shared_drives)
            if insert_data:
                shared = share_google_sheet(spreadsheet_id, account["new"])
                if shared:
                    save_result_to_file(account["new"], spreadsheet_id)
                print(f" + Google Sheet was shared with: {account['new']}")
        sleep(200)