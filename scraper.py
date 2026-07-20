import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
import urllib3
from datetime import datetime
import os
from apify_client import ApifyClient
from datetime import timedelta

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
# 3. LINKEDIN (Přes Apify API - opravený run_timeout)
# ----------------------------------------------------
APIFY_TOKEN = os.environ.get("APIFY_TOKEN")

if APIFY_TOKEN:
    try:
        client = ApifyClient(APIFY_TOKEN)

        # Přímý odkaz na vyhledávání GIS v ČR za poslední týden (r604800)
        search_url = "https://www.linkedin.com/jobs/search/?keywords=GIS&location=Czechia&f_TPR=r604800"

        run_input = {
            "urls": [search_url],
            "count": 10,              # Omezení počtu na 10 položek
            "scrapeCompany": False,   # VYPNUTO: Zamezí načítání detailů firem a zacyklení
            "deepScrape": False
        }

        print("Spouštím Apify scraper pro LinkedIn...")
        
        # run_timeout přijímá objekt timedelta z modulu datetime
        run = client.actor("curious_coder/linkedin-jobs-scraper").call(
            run_input=run_input,
            memory_mbytes=1024,
            run_timeout=timedelta(seconds=120)  # Max. doba běhu 2 minuty
        )

        if run and "defaultDatasetId" in run:
            dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items
            print(f"LinkedIn (Apify): Nalezeno {len(dataset_items)} inzerátů.")

            for item in dataset_items:
                title_text = item.get("title") or item.get("jobTitle") or ""
                company = item.get("companyName") or item.get("company") or ""
                job_url = item.get("link") or item.get("url") or ""
                
                if title_text and job_url:
                    fe = fg.add_entry()
                    fe.title(f"LinkedIn: {title_text} ({company})")
                    fe.link(href=job_url)
                    fe.description(f"Pracovní pozice na LinkedInu: {title_text} ve firmě {company}")
                    fe.guid(job_url, permalink=True)
                    jobs_found = True
        else:
            print("Apify běh vypršel nebo nevrátil výsledky.")

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
