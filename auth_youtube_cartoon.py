from src.uploader import get_youtube_service

print("Authorizing Cartoon Plus YouTube Channel...")
print("A browser window should open. Please log in with the Cartoon Plus Google account.")

# This will trigger the OAuth flow and save the token as 'youtube_token_cartoon.json'
youtube = get_youtube_service(token_file='youtube_token_cartoon.json')

if youtube:
    print("\n✅ Successfully authorized! 'youtube_token_cartoon.json' has been created.")
    print("\nNext steps for GitHub Actions:")
    print("1. Open PowerShell and run this command to convert the token to Base64:")
    print("   [convert]::ToBase64String([IO.File]::ReadAllBytes('youtube_token_cartoon.json')) | clip")
    print("2. The Base64 string is now copied to your clipboard.")
    print("3. Go to GitHub -> Settings -> Secrets and Variables -> Actions")
    print("4. Add a new repository secret named: YOUTUBE_TOKEN_CARTOON_JSON_B64")
    print("5. Paste the clipboard contents as the value.")
else:
    print("\n❌ Authorization failed. Make sure client_secret.json is present in the folder.")
