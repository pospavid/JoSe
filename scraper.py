import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
import urllib3
import os

# Vypnutí otravných SSL varování, pokud by weby měly špatné certifikáty
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Seznam stránek, které chceš hlídat
URLS = {
    "Web firmy A": "https://gisportal.cz/pracovni-nabidky",
    "Web firmy B": "https://www.zememeric.cz/inzerce-pracovni-nabidky-prehled"
}

# 1. Inicializace RSS Feed Generatoru
fg = FeedGenerator()
fg.title('Moje Hlídání Pracovních Nabídek')
fg.link(href='https://github.com/tvoje-jmeno/JoSe', rel='alternate')
fg.description('Automaticky generovaný přehled nových pozic')
fg.language('cs')

jobs_found = False

# 2. Skrapování webů
for firma, url in URLS.items():
    try:
        response = requests.get(url, verify=False, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # TADY SE LIŠÍ PODLE WEBU - uprav podle konkrétní struktury stránek
        for link in soup.find_all('a'):
            text = link.text.strip()
            
            if "developer" in text.lower() or "python" in text.lower():
                job_url = link.get('href')
                # Ošetření relativních odkazů (pokud chybí doména)
                if job_url and not job_url.startswith('http'):
                    from urllib.parse import urljoin
                    job_url = urljoin(url, job_url)
                
                # Přidání položky do RSS feedu
                fe = fg.add_entry()
                fe.title(f"{firma}: {text}")
                fe.link(href=job_url)
                fe.description(f"Byla nalezena nová pozice: {text} na webu {firma}.")
                fe.guid(job_url, permalink=True) # GUID zabrání duplicitám ve čtečce
                
                jobs_found = True
                
    except Exception as e:
        print(f"Chyba při stahování {firma}: {e}")

# Pokud se nic nenašlo, vytvoříme aspoň jednu servisní zprávu, aby RSS feed nebyl prázdný (čtečky prázdné feedy nemají rády)
if not jobs_found:
    fe = fg.add_entry()
    fe.title("Žádné nové pozice")
    fe.link(href=list(URLS.values())[0])
    fe.description("Dnes nebyly nalezeny žádné nové vyhovující nabídky.")
    fe.guid("no-jobs-today", permalink=False)

# 3. Uložení výsledku do XML
fg.rss_file('pracovni_nabidky.xml', pretty=True)
print("RSS feed úspěšně aktualizován.")
