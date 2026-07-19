import requests
from bs4 import BeautifulSoup
from datetime import datetime

# Seznam stránek, které chceš hlídat
URLS = {
    "GisPortal": "https://gisportal.cz/pracovni-nabidky",
    "Zememeric": "https://www.zememeric.cz/inzerce-pracovni-nabidky-prehled"
}

jobs_found = []

for firma, url in URLS.items():
    try:
        # verify=False pro jistotu kvůli SSL chybám, na které narážíme
        response = requests.get(url, verify=False, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # TADY SE LIŠÍ PODLE WEBU - musíš najít správné HTML tagy
        # Např. hledáme všechny nadpisy h3, které obsahují slovo "Developer"
        for link in soup.find_all('a'):
            text = link.text.strip()
            if "developer" in text.lower() or "python" in text.lower():
                jobs_found.append({"firma": firma, "pozice": text, "url": link.get('href')})
    except Exception as e:
        print(f"Chyba při stahování {firma}: {e}")

# Vygenerování výsledného HTML
html_content = f"""
<!DOCTYPE html>
<html lang="cs">
<head>
    <meta charset="UTF-8">
    <title>Moje Pracovní Nabídky</title>
    <style>
        body {{ font-family: sans-serif; margin: 40px; background: #f4f4f9; }}
        .job-card {{ background: white; padding: 15px; margin-bottom: 10px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
    </style>
</head>
<body>
    <h1>Nalezené pozice (Aktualizováno: {datetime.now().strftime('%d.%m.%Y %H:%M')})</h1>
"""

if jobs_found:
    for job in jobs_found:
        html_content += f"""
        <div class="job-card">
            <h3>{job['firma']} - {job['pozice']}</h3>
            <a href="{job['url']}" target="_blank">Odkaz na nabídku</a>
        </div>
        """
else:
    html_content += "<p>Dnes nebyly nalezeny žádné nové vyhovující pozice.</p>"

html_content += "</body></html>"

# Uložení do souboru index.html
with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)
