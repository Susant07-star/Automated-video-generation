import urllib.request
import re
import json

req = urllib.request.Request('https://www.facebook.com/nextgenthoughts/', headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'})
try:
    html = urllib.request.urlopen(req).read().decode('utf-8')
    ids = re.findall(r'fb://page/\?id=([0-9]+)', html)
    if not ids:
        ids = re.findall(r'"pageID":"([0-9]+)"', html)
    if not ids:
        ids = re.findall(r'"identifier":"([0-9]+)"', html)
    
    if ids:
        print('SUCCESS_PAGE_ID:', ids[0])
    else:
        print('COULD NOT FIND PAGE ID')
except Exception as e:
    print('Error:', e)
