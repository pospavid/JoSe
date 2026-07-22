import os
import time
import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from apify_client import ApifyClient
import xml.etree.ElementTree as ET

# Soubor pro uložení RSS feedu
RSS_FILE = "pracovni_nabidky.xml"


def get_existing_guids(file_path):
    """Načte všechny GUID / odkazy z existujícího XML souboru, aby se neopakovaly duplicity."""
    existing_guids = set()
    if os.path.exists(file_path):
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            # V RSS 2.0 hledáme položky v channel/item/guid nebo channel/item/link
            for item in root.findall(".//item"):
                guid = item.find("guid")
                link = item.find("link")
                if guid is not None and guid.text:
                    existing_guids.add(guid.text.strip())
                elif link is not None and link.text:
                    existing_guids.add(link.text.strip())
        except Exception as e:
            print(f"Upozornění: Nepodařilo se načíst existující XML ({e}), vytvoří se nové.")
    return existing_guids


# ----------------------------------------------------
# 1. INICIALIZACE RSS FEEDU A NAČTENÍ STÁVAJÍCÍCH DATA
# ----------------------------------------------------
seen_guids = get_existing_guids(RSS_FILE)
print(f"Načteno {len(seen_guids)} již uložených inzerátů z '{RSS_FILE}'.")

fg = FeedGenerator()
fg.title("Pracovní nabídky GIS v ČR")
fg.link(href="https://www.linkedin.com/", rel="alternate")
fg.description("Agregovaný RSS feed pracovních nabídek v oboru GIS v České republice")
fg.language("cs")

# ----------------------------------------------------
# 2. LINKEDIN (Přes Apify API - opravený přstup k Run)
# ----------------------------------------------------
APIFY_TOKEN = os.environ.get("APIFY_TOKEN")

if APIFY_TOKEN:
    try:
        client = ApifyClient(APIFY_TOKEN)

        # Vyhledávání GIS v ČR za posledních 14 dní (f_TPR=r1209600)
        search_url = "https://www.linkedin.com/jobs/search/?keywords=GIS&location=Czechia&f_TPR=r1209600"

        run_input = {
            "urls": [search_url],
            "deepScrape": False,
            "limit": 15
        }

        print("Spouštím Apify scraper pro LinkedIn...")
        
        # Spustíme actor přes .start()
        run = client.actor("curious_coder/linkedin-jobs-scraper").start(run_input=run_input)
        
        # Přístup přes atributy objektu Run (nové SDK)
        run_id = run.id
        dataset_id = run.default_dataset_id
        
        print("Čekám 25 sekund na stažení prvních inzerátů...")
        time.sleep(25)

        # Načtení dat přímo z datasetu
        dataset_items = client.dataset(dataset_id).list_items().items
        print(f"LinkedIn (Apify): Získáno {len(dataset_items)} položek z datasetu.")

        for item in dataset_items:
            title_text = item.get("title") or item.get("jobTitle") or item.get("position") or ""
            company = item.get("companyName") or item.get("company") or "LinkedIn"
            job_url = item.get("link") or item.get("url") or item.get("jobUrl") or ""
            
            if title_text and job_url:
                # Kontrola duplicity
                if job_url in seen_guids:
                    print(f"  -> [LinkedIn] Přeskočena duplicita: {title_text}")
                    continue

                fe = fg.add_entry()
                fe.title(f"LinkedIn: {title_text} ({company})")
                fe.link(href=job_url)
                fe.description(f"Pracovní pozice na LinkedInu: {title_text} ve firmě {company}")
                fe.guid(job_url, permalink=True)
                
                seen_guids.add(job_url)
                print(f"  -> [LinkedIn] NOVÝ inzerát přidán: {title_text}")
            else:
                print(f"  -> [LinkedIn] Přeskočena neúplná položka: {item}")

        # Ukončíme běh v Apify, abychom neplýtvali kredity
        try:
            client.run(run_id).abort()
        except Exception:
            pass

    except Exception as e:
        print(f"Chyba při skrapování LinkedIn přes Apify: {e}")
else:
    print("Apify token nebyl nalezen v proměnných prostředí (APIFY_TOKEN).")


# ----------------------------------------------------
# 3. JOBS.CZ (Přímé rychlé skrapování přes requests)
# ----------------------------------------------------
print("Spouštím skrapování Jobs.cz...")

jobs_url = "https://www.jobs.cz/prace/praha/?q%5B%5D=gis&locality%5Bradius%5D=0"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

try:
    response = requests.get(jobs_url, headers=headers, timeout=10)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        
        job_articles = soup.select("article") or soup.select(".SearchResultCard")
        print(f"Jobs.cz: Nalezeno {len(job_articles)} možných inzerátů.")

        for article in job_articles:
            link_tag = article.select_one("a[href*='/rpd/']") or article.select_one("a[href*='/nabidka/']") or article.select_one("h2 a") or article.select_one("h3 a")
            
            if link_tag:
                title_text = link_tag.get_text(strip=True)
                job_link = link_tag.get("href", "")
                
                if job_link.startswith("/"):
                    job_link = f"https://www.jobs.cz{job_link}"

                # Kontrola duplicity
                if job_link in seen_guids:
                    print(f"  -> [Jobs.cz] Přeskočena duplicita: {title_text}")
                    continue

                company_tag = article.select_one(".SearchResultCard__footer") or article.select_one("[class*='company']")
                company = company_tag.get_text(strip=True) if company_tag else "Jobs.cz"

                if title_text and job_link:
                    fe = fg.add_entry()
                    fe.title(f"Jobs.cz: {title_text} ({company})")
                    fe.link(href=job_link)
                    fe.description(f"Pracovní pozice na Jobs.cz: {title_text} - Firma: {company}")
                    fe.guid(job_link, permalink=True)
                    
                    seen_guids.add(job_link)
                    print(f"  -> [Jobs.cz] NOVÝ inzerát přidán: {title_text}")
    else:
        print(f"Jobs.cz vrátil stavový kód: {response.status_code}")

except Exception as e:
    print(f"Chyba při skrapování Jobs.cz: {e}")


# ----------------------------------------------------
# 4. ULOŽENÍ VÝSLEDNÉHO XML FEEDU
# ----------------------------------------------------
fg.rss_file(RSS_FILE)
print(f"RSS feed byl úspěšně vygenerován do souboru '{RSS_FILE}'.")
