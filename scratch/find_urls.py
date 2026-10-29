import requests
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}

r = requests.get("https://www.kinderformularium.nl/geneesmiddelen", headers=headers, timeout=10)
print(f"Status: {r.status_code}")
# Find all links to geneesmiddel
matches = set(re.findall(r'/geneesmiddel/\d+/[a-z0-9-]+', r.text))
print(f"Found {len(matches)} links")

drugs = ["aciclovir", "fluconazol", "amoxicilline", "ursodeoxycholzuur", "posaconazol", "omeprazol", "penicilline", "fenoxymethylpenicilline", "cotrimoxazol"]
for d in drugs:
    found = [m for m in matches if d in m]
    print(f"{d}: {found}")
