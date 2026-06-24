from google.oauth2 import service_account


# Workspaces to process: domain -> admin to impersonate (domain-wide delegation).
ws_data = {
    "your_domain.com": {
        "domain": "your_domain.com",
        "admin": "your_admin_email@your_domain.com",
    },
    # "second_domain.com": {
    #     "domain": "second_domain.com",
    #     "admin": "your_admin_email@second_domain.com",
    # }
}

# Accounts to process: list the docs shared with "old", share the resulting
# sheet with "new".
desired_accounts = [
    {
        "old": "u.name@your_domain.com",
        "new": "u.name@another_domain.com"
    },
]

def get_admin_creds(sa_path, admin_email):
    credentials = service_account.Credentials.from_service_account_file(
        sa_path,
        scopes=[
            # 'https://www.googleapis.com/auth/admin.directory.user',
            'https://www.googleapis.com/auth/admin.directory.user.readonly',
            # 'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/drive.readonly',
            'https://www.googleapis.com/auth/spreadsheets',
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
        'https://www.googleapis.com/auth/drive.file',
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
