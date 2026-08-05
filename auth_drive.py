import os
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# We just need read-only access to download the videos
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def authenticate_drive():
    creds = None
    if os.path.exists('drive_token.json'):
        creds = Credentials.from_authorized_user_file('drive_token.json', SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('client_secret.json'):
                print("❌ ERROR: 'client_secret.json' not found. Please ensure it is in the same folder.")
                return None
                
            flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        with open('drive_token.json', 'w') as token:
            token.write(creds.to_json())
            
    print("\n✅ Successfully authorized Google Drive! 'drive_token.json' has been created.")
    print("\nNext steps for GitHub Actions:")
    print("1. Open PowerShell and run this command to convert the token to Base64:")
    print("   [convert]::ToBase64String([IO.File]::ReadAllBytes(\"$PWD\\drive_token.json\")) | clip")
    print("2. The Base64 string is now copied to your clipboard.")
    print("3. Go to GitHub -> Settings -> Secrets and Variables -> Actions")
    print("4. Add a new repository secret named: DRIVE_TOKEN_JSON_B64")
    print("5. Paste the clipboard contents as the value.")
    
    return creds

if __name__ == '__main__':
    print("Authorizing Google Drive...")
    print("A browser window should open. Please log in with the exact same Google account you used for Cartoon Plus YouTube.")
    authenticate_drive()
