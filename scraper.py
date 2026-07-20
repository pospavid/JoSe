import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
import urllib3
from datetime import datetime
import os
from apify_client import ApifyClient
from datetime import timedelta
import time

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

from datetime import timedelta

from datetime import timedelta

import time

# ----------------------------------------------------
# 3. LINKEDIN (Přes Apify API - opravené atributy Run)
# ----------------------------------------------------
APIFY_TOKEN = os.environ.get("APIFY_TOKEN")

if APIFY_TOKEN:
    try:
        client = ApifyClient(APIFY_TOKEN)

        search_url = "https://www.linkedin.com/jobs/search/?keywords=GIS&location=Czechia&f_TPR=r1209600"

        run_input = {
            "urls": [search_url],
            "deepScrape": False,
            "limit": 15
        }

        print("Spouštím Apify scraper pro LinkedIn...")
        
        # 1. Spustíme actor přes .start()
        run = client.actor("curious_coder/linkedin-jobs-scraper").start(run_input=run_input)
        
        # ✅ Správný přístup k atributům objektu Run (namísto dict slovníku)
        run_id = run.id
        dataset_id = run.default_dataset_id
        
        # 2. Počkáme 25 sekund na stažení prvních inzerátů
        print("Čekám 25 sekund na stažení prvních inzerátů...")
        time.sleep(25)

        # 3. Načteme položky přímo z datasetu
        dataset_items = client.dataset(dataset_id).list_items().items
        print(f"LinkedIn (Apify): Získáno {len(dataset_items)} inzerátů z datasetu.")

        for item in dataset_items:
            title_text = item.get("title") or item.get("jobTitle") or item.get("position") or ""
            company = item.get("companyName") or item.get("company") or "LinkedIn"
            job_url = item.get("link") or item.get("url") or item.get("jobUrl") or ""
            
            if title_text and job_url:
                fe = fg.add_entry()
                fe.title(f"LinkedIn: {title_text} ({company})")
                fe.link(href=job_url)
                fe.description(f"Pracovní pozice na LinkedInu: {title_text} ve firmě {company}")
                fe.guid(job_url, permalink=True)
                jobs_found = True
                print(f"  -> Přidáno do RSS: {title_text}")
            else:
                print(f"  -> Přeskočena neúplná položka: {item}")

        # 4. Zastavíme actor na Apify, ať neplýtvá minuty
        try:
            client.run(run_id).abort()
        except Exception:
            pass

    except Exception as e:
        print(f"Chyba při skrapování LinkedIn přes Apify: {e}")
else:
    print("Apify token nebyl nalezen v proměnných prostředí (APIFY_TOKEN).")

import requests
from bs4 import BeautifulSoup

# ----------------------------------------------------
# 4. JOBS.CZ (Přímé skrapování přes requests)
# ----------------------------------------------------
print("Spouštím skrapování Jobs.cz...")

jobs_url = "https://www.jobs.cz/prace/praha/?q%5B%5D=gis&locality%5Bradius%5D=0"

# Hlavička, aby web neblokoval požadavek jako bota
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

try:
    response = requests.get(jobs_url, headers=headers, timeout=10)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Inzeráty na Jobs.cz jsou v kartách/článcích (SearchResultCard nebo <article>)
        # Hledáme všechny odkazy na detail nabídky (/rpd/ nebo /nabidka/)
        job_articles = soup.select("article") or soup.select(".SearchResultCard")
        
        print(f"Jobs.cz: Nalezeno {len(job_articles)} možných inzerátů.")

        for article in job_articles:
            # Nadpis a odkaz bývají uvnitř tagu <a> nebo <h2>/<h3>
            link_tag = article.select_one("a[href*='/rpd/']") or article.select_one("a[href*='/nabidka/']") or article.select_one("h2 a") or article.select_one("h3 a")
            
            if link_tag:
                title_text = link_tag.get_text(strip=True)
                job_link = link_tag.get("href", "")
                
                # Pokud je odkaz relativní, převedeme na absolutní URL
                if job_link.startswith("/"):
                    job_link = f"https://www.jobs.cz{job_link}"

                # Název firmy (pokud je na kartě uvedena)
                company_tag = article.select_one(".SearchResultCard__footer") or article.select_one("[class*='company']")
                company = company_tag.get_text(strip=True) if company_tag else "Jobs.cz"

                if title_text and job_link:
                    fe = fg.add_entry()
                    fe.title(f"Jobs.cz: {title_text} ({company})")
                    fe.link(href=job_link)
                    fe.description(f"Pracovní pozice na Jobs.cz: {title_text} - Firma: {company}")
                    fe.guid(job_link, permalink=True)
                    jobs_found = True
                    print(f"  -> Přidáno do RSS: {title_text}")

    else:
        print(f"Jobs.cz vrátil stavový kód: {response.status_code}")

except Exception as e:
        print(f"Chyba při skrapování Jobs.cz: {e}")


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
