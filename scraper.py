import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
import urllib3
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

KEYWORDS = ["gis", "analytik", "specialista", "vývojář", "developer", "zeměměřič", "geodet", "kartograf", "pracovník", "inženýr", "technik"]

fg = FeedGenerator()
fg.title('GIS a Geodezie Pracovní Nabídky')
fg.link(href='https://gisportal.cz/pracovni-nabidky/', rel='alternate')
fg.description('Automaticky generovaný přehled z portálů Gisportal a Zeměměřič')
fg.language('cs')

jobs_found = False
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, application/xml"
}

# ----------------------------------------------------
# 1. REPARATURA: GISPORTAL.CZ (Přes skryté API)
# ----------------------------------------------------
try:
    # Zkoušíme načíst inzeráty z custom post type 'jobs' i klasické 'posts' z rubriky, pokud by se změnila struktura
    api_url = "https://gisportal.cz/wp-json/wp/v2/jobs?per_page=15"
    response = requests.get(api_url, verify=False, headers=headers)
    
    # Pokud custom jobs nevrátí nic, zkusíme standardní příspěvky (může to být záložní varianta webu)
    if response.status_code != 200 or len(response.json()) == 0:
        api_url = "https://gisportal.cz/wp-json/wp/v2/posts?categories=pracovni-nabidky&per_page=15"
        response = requests.get(api_url, verify=False, headers=headers)

    if response.status_code == 200:
        posts = response.json()
        print(f"Gisportal API: Nalezeno {len(posts)} příspěvků ke kontrole.")
        
        for post in posts:
            title_text = post.get('title', {}).get('rendered', '').strip()
            title_text = BeautifulSoup(title_text, 'html.parser').text
            job_url = post.get('link', '')
            
            print(f"  Kontrola názvu: '{title_text}'") # Tento řádek nám v logu ukáže, co přesně web posílá
            
            # Pokud je inzerát v sekci jobs, vezmeme ho raději VŠECHNY, abychom o nic nepřišli, 
            # případně aplikujeme filtr na klíčová slova
            if any(kw in title_text.lower() for kw in KEYWORDS) or "wp/v2/jobs" in api_url:
                fe = fg.add_entry()
                fe.title(f"Gisportal: {title_text}")
                fe.link(href=job_url)
                fe.description(f"Nová pozice na Gisportálu: {title_text}")
                fe.guid(job_url, permalink=True)
                jobs_found = True
    else:
        print(f"Gisportal API selhalo s kódem: {response.status_code}")
except Exception as e:
    print(f"Chyba při API skrapování Gisportal: {e}")


# ----------------------------------------------------
# 2. REPARATURA: ZEMEMERIC.CZ (Přes XML Sitemapu)
# ----------------------------------------------------
try:
    # Obcházíme blokaci tabulky tím, že načteme XML mapu inzerátů
    sitemap_url = "https://www.zememeric.cz/inzerce-sitemap.xml"
    response = requests.get(sitemap_url, verify=False, headers=headers)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'xml')
        # Sitemapa obsahuje tagy <url>, uvnitř kterých je <loc> (odkaz)
        urls = soup.find_all('url')
        print(f"Zeměměřič Sitemap: Nalezeno {len(urls)} odkazů v mapě.")
        
        # Projdeme nejnovější inzeráty (sitemapa je většinou řazená od nejnovějších)
        # Omezíme na prvních 20, ať neprocházíme historii
        for url_tag in urls[:20]:
            loc_tag = url_tag.find('loc')
            if loc_tag:
                job_url = loc_tag.text.strip()
                
                # U sitemapy nemáme název, ale vytáhneme ho čistě z URL adresy,
                # kde je název pozice v čitelném tvaru (tzv. slug)
                # Příklad: .../inzerce-detail/geodet-brno -> geodet brno
                slug = job_url.split('/')[-2] if job_url.endswith('/') else job_url.split('/')[-1]
                title_text = slug.replace('-', ' ').capitalize()
                
                if any(kw in title_text.lower() for kw in KEYWORDS):
                    fe = fg.add_entry()
                    fe.title(f"Zeměměřič: {title_text}")
                    fe.link(href=job_url)
                    fe.description(f"Nabídka z portálu Zeměměřič (odkaz: {slug})")
                    fe.guid(job_url, permalink=True)
                    jobs_found = True
    else:
        print(f"Zeměměřič Sitemap selhala s kódem: {response.status_code}")
except Exception as e:
    print(f"Chyba při čtení sitemapy Zeměměřič: {e}")


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
