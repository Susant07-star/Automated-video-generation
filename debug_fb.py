import os
import requests
from dotenv import load_dotenv

load_dotenv()
access_token = os.getenv('FACEBOOK_PAGE_ACCESS_TOKEN')
page_id = os.getenv('FACEBOOK_PAGE_ID')

print("1. Checking Token Identity (/me endpoint)")
try:
    me_url = f"https://graph.facebook.com/v19.0/me?access_token={access_token}"
    res = requests.get(me_url).json()
    print("Identity Response:", res)
    if 'name' in res:
        print(f"Token belongs to: {res['name']} (ID: {res['id']})")
        if res['id'] != page_id:
            print("WARNING: The ID attached to this token DOES NOT MATCH your FACEBOOK_PAGE_ID!")
except Exception as e:
    print("Error checking token:", e)

print("\n2. Checking Token Permissions (/me/permissions endpoint)")
try:
    perm_url = f"https://graph.facebook.com/v19.0/me/permissions?access_token={access_token}"
    res2 = requests.get(perm_url).json()
    if 'data' in res2:
        granted = [p['permission'] for p in res2['data'] if p['status'] == 'granted']
        print("Granted Permissions:", granted)
        if 'pages_manage_posts' not in granted and 'publish_video' not in granted:
            print("WARNING: Missing required posting permissions!")
    else:
        print("Permissions Response:", res2)
except Exception as e:
    print("Error checking permissions:", e)
