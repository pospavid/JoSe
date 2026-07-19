import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
import urllib3
from datetime import datetime

# Vypnutí SSL varování
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Klíčová slova, která tě zajímají (vše se převádí na malá písmena, takže na velikosti nezáleží)
KEYWORDS = ["gis", "analytik", "specialista", "vývojář", "developer", "zeměměřič", "geodet", "kartograf", "pracovník"]

# Inicializace RSS Feed Generatoru
fg = FeedGenerator()
fg.title('GIS a Geodezie Pracovní Nabídky')
fg.link(href='https://gisportal.cz/pracovni-nabidky/', rel='alternate')
fg.description('Automaticky generovaný přehled z portálů Gisportal a Zeměměřič')
fg.language('cs')

jobs_found = False
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ----------------------------------------------------
# 1. SCRAPING: GISPORTAL.CZ
# ----------------------------------------------------
try:
    url_gis = "https://gisportal.cz/pracovni-nabidky/"
    response = requests.get(url_gis, verify=False, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Gisportal používá tag <article> pro každý inzerát
    articles = soup.find_all('article')
    
    for article in articles:
        # Hledáme nadpis h2 s třídou entry-title
        title_tag = article.find('h2', class_='entry-title')
        if title_tag:
            link_tag = title_tag.find('a')
            if link_tag:
                title_text = link_tag.text.strip()
                job_url = link_tag.get('href')
                
                # Kontrola klíčových slov
                if any(kw in title_text.lower() for kw in KEYWORDS):
                    fe = fg.add_entry()
                    fe.title(f"Gisportal: {title_text}")
                    fe.link(href=job_url)
                    fe.description(f"Nová pozice na Gisportálu: {title_text}")
                    fe.guid(job_url, permalink=True)
                    jobs_found = True
except Exception as e:
    print(f"Chyba při skrapování Gisportal: {e}")


# ----------------------------------------------------
# 2. SCRAPING: ZEMEMERIC.CZ
# ----------------------------------------------------
try:
    url_zeme = "https://www.zememeric.cz/inzerce-pracovni-nabidky-prehled/"
    response = requests.get(url_zeme, verify=False, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Zeměměřič má inzeráty v tabulce, hledáme řádky <tr>
    # Ignorujeme první řádek (hlavičku tabulky)
    rows = soup.find_all('tr')[1:]
    
    for row in rows:
        cells = row.find_all('td')
        # Tabulka musí mít aspoň 2 buňky (Datum a Název s odkazem)
        if len(cells) >= 2:
            link_tag = cells[1].find('a')
            if link_tag:
                title_text = link_tag.text.strip()
                job_url = link_tag.get('href')
                
                # Oprava relativního odkazu, pokud chybí doména
                if job_url and not job_url.startswith('http'):
                    job_url = "https://www.zememeric.cz" + job_url
                
                if any(kw in title_text.lower() for kw in KEYWORDS):
                    fe = fg.add_entry()
                    fe.title(f"Zeměměřič: {title_text}")
                    fe.link(href=job_url)
                    fe.description(f"Nabídka z portálu Zeměměřič: {title_text}")
                    fe.guid(job_url, permalink=True)
                    jobs_found = True
except Exception as e:
    print(f"Chyba při skrapování Zeměměřič: {e}")


# Pojistka pro prázdný feed
if not jobs_found:
    fe = fg.add_entry()
    fe.title("Žádné nové pozice")
    fe.link(href="https://gisportal.cz/pracovni-nabidky/")
    fe.description(f"Při kontrole {datetime.now().strftime('%d.%m.%Y')} nebyly nalezeny žádné nové inzeráty odpovídající klíčovým slovům.")
    fe.guid("no-jobs-today", permalink=False)

# Uložení do XML
fg.rss_file('pracovni_nabidky.xml', pretty=True)
print("RSS feed byl úspěšně vygenerován.")
