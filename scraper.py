import os
import time
import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from apify_client import ApifyClient
import xml.etree.ElementTree as ET

RSS_FILE = "pracovni_nabidky.xml"

# ----------------------------------------------------
# 1. NAČTENÍ EXISTUJÍCÍHO XML FEEDU (POKUD EXISTUJE)
# ----------------------------------------------------
fg = FeedGenerator()
fg.title("Pracovní nabídky GIS & Geodézie v ČR")
fg.link(href="https://www.gisportal.cz/", rel="alternate")
fg.description("Agregovaný RSS feed z LinkedIn, Jobs.cz, Zeměměřič a GISportál")
fg.language("cs")

seen_guids = set()

if os.path.exists(RSS_FILE):
    try:
        tree = ET.parse(RSS_FILE)
        root = tree.getroot()
        
        # Projdeme staré položky, načteme je do fg a jejich GUID uložíme do seen_guids
        for item in root.findall(".//item"):
            title = item.findtext("title") or ""
            link = item.findtext("link") or ""
            description = item.findtext("description") or ""
            guid = item.findtext("guid") or link

            if guid and guid not in seen_guids:
                fe = fg.add_entry()
                fe.title(title)
                fe.link(href=link)
                fe.description(description)
                fe.guid(guid, permalink=True)
                seen_guids.add(guid)
                
        print(f"Načteno {len(seen_guids)} existujících nabídek z '{RSS_FILE}'.")
    except Exception as e:
        print(f"Upozornění: Nelze načíst staré XML ({e}), vytváří se nový feed.")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
new_count = 0


# ----------------------------------------------------
# 2. LINKEDIN (přes Apify API)
# ----------------------------------------------------
APIFY_TOKEN = os.environ.get("APIFY_TOKEN")
if APIFY_TOKEN:
    try:
        print("Spouštím kontrolu: LinkedIn...")
        client = ApifyClient(APIFY_TOKEN)
        run_input = {
            "urls": ["https://www.linkedin.com/jobs/search/?keywords=GIS&location=Czechia&f_TPR=r1209600"],
            "deepScrape": False,
            "limit": 15
        }
        run = client.actor("curious_coder/linkedin-jobs-scraper").start(run_input=run_input)
        
        time.sleep(25)
        dataset_items = client.dataset(run.default_dataset_id).list_items().items

        for item in dataset_items:
            title_text = item.get("title") or item.get("jobTitle") or item.get("position") or ""
            company = item.get("companyName") or item.get("company") or "LinkedIn"
            job_url = item.get("link") or item.get("url") or item.get("jobUrl") or ""

            if title_text and job_url:
                # Pokud v XML NENÍ -> přidáme
                if job_url not in seen_guids:
                    fe = fg.add_entry()
                    fe.title(f"LinkedIn: {title_text} ({company})")
                    fe.link(href=job_url)
                    fe.description(f"Pozice z LinkedInu: {title_text} - Firma: {company}")
                    fe.guid(job_url, permalink=True)
                    
                    seen_guids.add(job_url)
                    new_count += 1
                    print(f"  -> [LinkedIn] PŘIDÁNO: {title_text}")
                # Pokud v XML JE -> ignorujeme
                else:
                    print(f"  -> [LinkedIn] Ignorováno (již v XML): {title_text}")

        try:
            client.run(run.id).abort()
        except Exception:
            pass
    except Exception as e:
        print(f"Chyba LinkedIn: {e}")


# ----------------------------------------------------
# 3. JOBS.CZ
# ----------------------------------------------------
print("Spouštím kontrolu: Jobs.cz...")
try:
    jobs_url = "https://www.jobs.cz/prace/praha/?q%5B%5D=gis&locality%5Bradius%5D=0"
    resp = requests.get(jobs_url, headers=headers, timeout=10)
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.select("article") or soup.select(".SearchResultCard")

        for art in articles:
            link_tag = art.select_one("a[href*='/rpd/']") or art.select_one("a[href*='/nabidka/']") or art.select_one("h2 a") or art.select_one("h3 a")
            if link_tag:
                title_text = link_tag.get_text(strip=True)
                job_link = link_tag.get("href", "")
                if job_link.startswith("/"):
                    job_link = f"https://www.jobs.cz{job_link}"

                if title_text and job_link:
                    if job_link not in seen_guids:
                        comp_tag = art.select_one(".SearchResultCard__footer") or art.select_one("[class*='company']")
                        company = comp_tag.get_text(strip=True) if comp_tag else "Jobs.cz"

                        fe = fg.add_entry()
                        fe.title(f"Jobs.cz: {title_text} ({company})")
                        fe.link(href=job_link)
                        fe.description(f"Pozice z Jobs.cz: {title_text} - Firma: {company}")
                        fe.guid(job_link, permalink=True)

                        seen_guids.add(job_link)
                        new_count += 1
                        print(f"  -> [Jobs.cz] PŘIDÁNO: {title_text}")
                    else:
                        print(f"  -> [Jobs.cz] Ignorováno (již v XML): {title_text}")
except Exception as e:
    print(f"Chyba Jobs.cz: {e}")


# ----------------------------------------------------
# 4. ZEMĚMĚŘIČ.CZ
# ----------------------------------------------------
print("Spouštím kontrolu: Zeměměřič.cz...")
try:
    zememerjc_url = "https://www.zememericskazurnalistika.cz/burza-prace/"
    resp = requests.get(zememerjc_url, headers=headers, timeout=10)
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, "html.parser")
        offers = soup.select(".entry-title a") or soup.select("article a[href*='burza']")

        for offer in offers:
            title_text = offer.get_text(strip=True)
            job_link = offer.get("href", "")

            if title_text and job_link:
                if job_link not in seen_guids:
                    fe = fg.add_entry()
                    fe.title(f"Zeměměřič: {title_text}")
                    fe.link(href=job_link)
                    fe.description(f"Nabídka z burzy práce Zeměměřič: {title_text}")
                    fe.guid(job_link, permalink=True)

                    seen_guids.add(job_link)
                    new_count += 1
                    print(f"  -> [Zeměměřič] PŘIDÁNO: {title_text}")
                else:
                    print(f"  -> [Zeměměřič] Ignorováno (již v XML): {title_text}")
except Exception as e:
    print(f"Chyba Zeměměřič.cz: {e}")


# ----------------------------------------------------
# 5. GISPORTÁL.CZ
# ----------------------------------------------------
print("Spouštím kontrolu: GISportál.cz...")
try:
    gisportal_url = "https://www.gisportal.cz/category/prace-a-studium/"
    resp = requests.get(gisportal_url, headers=headers, timeout=10)
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.select("article h2 a") or soup.select(".post-title a")

        for art in articles:
            title_text = art.get_text(strip=True)
            job_link = art.get("href", "")

            if title_text and job_link:
                if job_link not in seen_guids:
                    fe = fg.add_entry()
                    fe.title(f"GISportál: {title_text}")
                    fe.link(href=job_link)
                    fe.description(f"Článek/Nabídka z GISportálu: {title_text}")
                    fe.guid(job_link, permalink=True)

                    seen_guids.add(job_link)
                    new_count += 1
                    print(f"  -> [GISportál] PŘIDÁNO: {title_text}")
                else:
                    print(f"  -> [GISportál] Ignorováno (již v XML): {title_text}")
except Exception as e:
    print(f"Chyba GISportál.cz: {e}")


# ----------------------------------------------------
# 6. ULOŽENÍ AKTUALIZOVANÉHO XML SOUBORU
# ----------------------------------------------------
fg.rss_file(RSS_FILE)
print(f"\nHotovo. Přidáno {new_count} nových nabídek. Soubor '{RSS_FILE}' nyní obsahuje celkem {len(seen_guids)} položek.")
