from google.oauth2 import service_account
main_domain = "your_domain"

# Configure for your domain
ws_data = {
    f"{main_domain}": {
        "domain": main_domain,
        "sa": "adminitrator.json",
        "admin": f"your_admin_email@{main_domain}",
    }
}

desired_accounts = [
    {
        "old": "u.name@your_domain.com", # user to investigate
        "new": "u.name@another_domain.com" # user to share a sheet with
    },
    {
        "old": "u.name_2@your_domain.com", # user to investigate
        "new": "u.name_2@another_domain.com" # user to share a sheet with
    }
]

def get_admin_creds(sa_path, admin_email):
    credentials = service_account.Credentials.from_service_account_file(
        sa_path,
        scopes=[
            'https://www.googleapis.com/auth/admin.directory.user.readonly',
            'https://www.googleapis.com/auth/drive.readonly',
            'https://www.googleapis.com/auth/spreadsheets'
        ],
        subject=admin_email
    )
    return credentials


def get_sa_creds(service_account_file):
    """
    Returns service account credentials for Google API.
    """
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive.file'
    ]
    creds = service_account.Credentials.from_service_account_file(service_account_file, scopes=scopes)
    return creds


def get_user_creds(sa_path, user_email):
    credentials = service_account.Credentials.from_service_account_file(
        sa_path,
        scopes=['https://www.googleapis.com/auth/drive'],
        subject=user_email
    )
    return credentials
