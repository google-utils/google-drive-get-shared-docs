## Info
This script 
1. Gets all the documents that shared with the user in workspace A
2. Creates a spreadsheet with all the documents and their links 
3. Shares the sheet with the user in workspace B

## How to use
1. Put your SA json file into `sa` folder
2. Edit `config.ws_data` and specify the sa filename
3. Edit `config.desired_accounts` and specify the account you want to process.

### Important to know
Here are the Domain Wide Delegation scopes you must have configured for your Service Account client id in G-Suit.
```text
https://www.googleapis.com/auth/admin.directory.user.readonly'
https://www.googleapis.com/auth/spreadsheets
https://www.googleapis.com/auth/drive.readonly
https://www.googleapis.com/auth/drive.file
https://www.googleapis.com/auth/drive
```
Also in order to get it done <b>Google Sheets API</b> must be enabled as well as <b>Google Admin SDK</b> if you want to retrieve users automatically.