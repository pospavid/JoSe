import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
import urllib3
from datetime import datetime
import os
from apify_client import ApifyClient

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Klíčová slova pro Zeměměřiče
KEYWORDS = ["gis", "analytik", "specialista", "vývojář", "developer", "zeměměřič", "geodet", "kartograf", "pracovník", "inženýr", "technik", "práce", "nabídka", "pozice"]

fg = FeedGenerator()
fg.title('GIS a Geodezie Pracovní Nabídky')
fg.link(href='https://gisportal.cz/pracovni-nabidky/', rel='alternate')
fg.description('Automaticky generovaný přehled z portálů Gisportal a Zeměměřič')
fg.language('cs')

jobs_found = False
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ----------------------------------------------------
# 1. GISPORTAL.CZ (Přímé HTML čtení nadpisů h3)
# ----------------------------------------------------
try:
    url = "https://gisportal.cz/pracovni-nabidky/"
    response = requests.get(url, headers=headers, verify=False)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        # Najdeme všechny h3 nadpisy na stránce
        h3_tags = soup.find_all('h3')
        print(f"Gisportal: Nalezeno {len(h3_tags)} nadpisů h3.")
        
        for h3 in h3_tags:
            # Hledáme odkaz přímo uvnitř h3 nebo v jeho okolí
            a_tag = h3.find('a') or h3.find_parent('a')
            
            if a_tag and a_tag.get('href'):
                title_text = h3.get_text(strip=True)
                job_url = a_tag['href']
                
                # Ignorujeme prázdné nebo systémové nadpisy
                if title_text:
                    fe = fg.add_entry()
                    fe.title(f"Gisportal: {title_text}")
                    fe.link(href=job_url)
                    fe.description(f"Pracovní nabídka z Gisportálu: {title_text}")
                    fe.guid(job_url, permalink=True)
                    jobs_found = True
    else:
        print(f"Gisportal selhal s kódem: {response.status_code}")
except Exception as e:
    print(f"Chyba při skrapování Gisportal: {e}")


# ----------------------------------------------------
# 2. ZEMEMERIC.CZ (Ověřená sitemap)
# ----------------------------------------------------
try:
    sitemap_url = "https://www.zememeric.cz/inzerce-sitemap.xml"
    response = requests.get(sitemap_url, headers=headers, verify=False)
    
    if response.status_code == 200:
        soup_xml = BeautifulSoup(response.text, 'xml')
        urls = soup_xml.find_all('url')
        
        for url_tag in urls[:20]:
            loc_tag = url_tag.find('loc')
            if loc_tag:
                job_url = loc_tag.text.strip()
                slug = job_url.split('/')[-2] if job_url.endswith('/') else job_url.split('/')[-1]
                title_text = slug.replace('-', ' ').capitalize()
                
                if any(kw in title_text.lower() for kw in KEYWORDS):
                    fe = fg.add_entry()
                    fe.title(f"Zeměměřič: {title_text}")
                    fe.link(href=job_url)
                    fe.description(f"Nabídka z portálu Zeměměřič: {title_text}")
                    fe.guid(job_url, permalink=True)
                    jobs_found = True
except Exception as e:
    print(f"Chyba při čtení sitemapy Zeměměřič: {e}")

# ----------------------------------------------------
# 3. LINKEDIN (Přes Apify API)
# ----------------------------------------------------
APIFY_TOKEN = os.environ.get("APIFY_TOKEN")

if APIFY_TOKEN:
    try:
        client = ApifyClient(APIFY_TOKEN)

        # Konfigurace vstupu pro Apify LinkedIn Jobs Scraper
        run_input = {
            "title": "GIS",             # Nebo "Geodet"
            "location": "Czechia",      # Místo výkonu práce
            "publishedAt": "r86400",     # Inzeráty za posledních 24 hodin (86400 sekund)
            "maxItems": 10              # Limit položek pro úsporu kreditu
        }

        # Spuštění Actoru na Apify a čekání na výsledky
        # (Používáme oblíbený veřejný actor 'curious_coder/linkedin-jobs-scraper')
        run = client.actor("curious_coder/linkedin-jobs-scraper").call(run_input=run_input)

        # Načtení nalezených inzerátů z Datasetu
        dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items
        print(f"LinkedIn (Apify): Nalezeno {len(dataset_items)} inzerátů.")

        for item in dataset_items:
            title_text = item.get("title", "")
            company = item.get("companyName", "")
            job_url = item.get("link", "")
            
            if title_text and job_url:
                fe = fg.add_entry()
                fe.title(f"LinkedIn: {title_text} ({company})")
                fe.link(href=job_url)
                fe.description(f"Pracovní pozice na LinkedInu: {title_text} v firmě {company}")
                fe.guid(job_url, permalink=True)
                jobs_found = True

    except Exception as e:
        print(f"Chyba při skrapování LinkedIn přes Apify: {e}")
else:
    print("Apify token nebyl nalezen v proměnných prostředí (APIFY_TOKEN).")


# Pojistka pro prázdný feed
if not jobs_found:
    fe = fg.add_entry()
    fe.title("Žádné nové pozice")
    fe.link(href="https://gisportal.cz/pracovni-nabidky/")
    fe.description(f"Při kontrole {datetime.now().strftime('%d.%m.%Y')} nebyly nalezeny žádné nové inzeráty.")
    fe.guid("no-jobs-today", permalink=False)

# Uložení do XML
fg.rss_file('pracovni_nabidky.xml', pretty=True)
print("RSS feed byl úspěšně přegenerován.")
