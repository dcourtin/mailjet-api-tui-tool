"""
Script de diagnostic : affiche les champs bruts retournés par l'API Mailjet
pour le premier message trouvé.
"""
import os, json
from datetime import datetime, timezone
from mailjet_rest import Client
from dotenv import load_dotenv

load_dotenv()
client = Client(auth=(os.environ['MAILJET_API_KEY'], os.environ['MAILJET_API_SECRET']), version='v3')

# 1. Test /message with ShowSubject and ShowContactAlt
start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
res = client.message.get(filters={
    'ShowSubject': 'true',
    'ShowContactAlt': 'true',
    'Limit': 1,
    'FromTS': start.strftime("%Y-%m-%dT%H:%M:%S"),
})
print("=== /message (1 result) ===")
print(f"HTTP {res.status_code}")
data = res.json().get('Data', [])
if data:
    print(json.dumps(data[0], indent=2))
else:
    print("Aucun message trouvé pour aujourd'hui.")
    # Try without date filter
    res2 = client.message.get(filters={'ShowExtraData': 'true', 'Limit': 1})
    data2 = res2.json().get('Data', [])
    if data2:
        print("(Sans filtre de date):")
        print(json.dumps(data2[0], indent=2))

# 2. Test /messagesentstatistics
print("\n=== /messagesentstatistics (1 result) ===")
res3 = client.messagesentstatistics.get(filters={
    'ShowExtraData': 'true',
    'Limit': 1,
    'FromTS': start.strftime("%Y-%m-%dT%H:%M:%S"),
})
print(f"HTTP {res3.status_code}")
data3 = res3.json().get('Data', [])
if data3:
    print(json.dumps(data3[0], indent=2))
else:
    print("Aucun résultat.")

# 3. Test /messageinformation
print("\n=== /messageinformation (1 result) ===")
res4 = client.messageinformation.get(filters={
    'ShowExtraData': 'true',
    'Limit': 1,
    'FromTS': start.strftime("%Y-%m-%dT%H:%M:%S"),
})
print(f"HTTP {res4.status_code}")
data4 = res4.json().get('Data', [])
if data4:
    print(json.dumps(data4[0], indent=2))
else:
    print("Aucun résultat.")
