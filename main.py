from googleapiclient.discovery import build
from time import sleep
import json

from config import *


def get_all_users(workspace_data):
    """
    Returns all users from workspace
    """
    all_users = []
    admin_creds = get_admin_creds(f"./sa/{workspace_data['sa']}", workspace_data["admin"])
    service = build('admin', 'directory_v1', credentials=admin_creds)
    request = service.users().list(domain=workspace_data["domain"], query='isSuspended=false', maxResults=500)
    while request is not None:
        response = request.execute()
        all_users.extend(response.get('users', []))
        request = service.users().list_next(request, response)
    return all_users


def list_shared_documents(workspace_data, user_email):
    """
    Returns a list of docs shared with user but not owned by them
    """
    user_creds = get_user_creds(f"./sa/{workspace_data['sa']}", user_email)
    service = build('drive', 'v3', credentials=user_creds)

    # query = "'me' in readers and not 'me' in owners and trashed = false"
    # query = "'me' in writers and not 'me' in owners and trashed = false"
    query = "('me' in writers or 'me' in readers) and not 'me' in owners and trashed = false"
    fields = "nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, owners, permissions)"
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
        results = service.files().list(q=query, fields=fields, pageToken=page_token).execute()
        items = results.get('files', [])
        for item in items:
            mime_type = item.get('mimeType', 'N/A')
            file_id = item.get('id', 'N/A')
            document_link = mime_type_to_link.get(mime_type, "https://drive.google.com/file/d/") + file_id
            perms = [perm['emailAddress'] for perm in item.get('permissions', []) if 'emailAddress' in perm]
            if not perms:
                continue
            documents.append([
                item.get('name', 'N/A'),
                file_id,
                document_link,
                mime_type,
                item.get('createdTime', 'N/A'),
                item.get('modifiedTime', 'N/A'),
                ', '.join([owner['emailAddress'] for owner in item.get('owners', [])]),
                ', '.join([perm['emailAddress'] for perm in item.get('permissions', []) if 'emailAddress' in perm])
            ])
        page_token = results.get('nextPageToken')
        if not page_token:
            break
    return documents


def create_google_sheet(workspace_data, sheet_name):
    """
    Creates a new Google Sheet and returns its ID
    """
    sa_creds = get_sa_creds(f"./sa/{workspace_data['sa']}")
    service = build('sheets', 'v4', credentials=sa_creds)
    spreadsheet = {
        'properties': {
            'title': sheet_name
        }
    }
    spreadsheet = service.spreadsheets().create(body=spreadsheet, fields='spreadsheetId').execute()
    return spreadsheet.get('spreadsheetId')


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


def share_google_sheet(workspace_data, sh_id, user_email):
    """
    Shares the Google Sheet with the specified user
    """
    sa_creds = get_sa_creds(f"./sa/{workspace_data['sa']}")
    service = build('drive', 'v3', credentials=sa_creds)
    user_permission = {
        'type': 'user',
        'role': 'reader',
        'emailAddress': user_email
    }
    r = service.permissions().create(
        fileId=sh_id,
        body=user_permission,
        fields='id'
    ).execute()
    return r


def write_to_google_sheet(workspace_data, sh_id, email, data):
    """
    Write all the docs shared with the user to the spreadsheet_id in chunks of 1000 rows.
    """
    try:
        sa_creds = get_sa_creds(f"./sa/{workspace_data['sa']}")
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

        # Add headers to the data
        headers = ["Name", "ID", "Link", "Mime Type", "Created Time", "Modified Time", "Owners", "Permissions"]
        data.insert(0, headers)

        # Write data in chunks of 1000 rows
        for i in range(0, len(data), 1000):
            chunk = data[i:i + 1000]
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


if __name__ == '__main__':
    # users = get_all_users(ws_data["your_domain"])
    # emails = [user['primaryEmail'] for user in users if 'old' not in user['primaryEmail']]

    for account in desired_accounts:
        print(f'Processing user: {account["old"]}')
        user_docs = list_shared_documents(ws_data[main_domain], account["old"])
        print(f"Found {len(user_docs)} docs")
        
        if user_docs:
            spreadsheet_id = create_google_sheet(ws_data[main_domain], f"Files shared with {account['old']}")
            insert_data = write_to_google_sheet(ws_data[main_domain], spreadsheet_id, account["old"], user_docs)
            if insert_data:
                shared = share_google_sheet(ws_data[main_domain], spreadsheet_id, account["new"])
                if shared:
                    save_result_to_file(account["new"], spreadsheet_id)

                print(f" + Google Sheet was shared with: {account['new']}")
        sleep(200)
