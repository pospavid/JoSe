import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
import urllib3
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Pro test raději rozšíříme klíčová slova na maximum, abychom viděli, zda vůbec něco parsujeme
KEYWORDS = ["gis", "analytik", "specialista", "vývojář", "developer", "zeměměřič", "geodet", "kartograf", "pracovník", "nabídka", "přijme", "hledá", "inženýr", "technik"]

fg = FeedGenerator()
fg.title('GIS a Geodezie Pracovní Nabídky')
fg.link(href='https://gisportal.cz/pracovni-nabidky/', rel='alternate')
fg.description('Automaticky generovaný přehled z portálů Gisportal a Zeměměřič')
fg.language('cs')

jobs_found = False
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "cs,en-US;q=0.7,en;q=0.3"
}

print("=== DIAGNOSTIKA START ===")

# ----------------------------------------------------
# 1. DIAGNOSTIKA: GISPORTAL.CZ
# ----------------------------------------------------
try:
    url_gis = "https://gisportal.cz/pracovni-nabidky/"
    response = requests.get(url_gis, verify=False, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    articles = soup.find_all('article')
    print(f"Gisportal: Celkem nalezeno <article> tagů: {len(articles)}")
    
    for i, article in enumerate(articles[:5]): # Vypíšeme prvních 5 pro kontrolu
        title_tag = article.find('h2', class_='entry-title')
        if title_tag:
            link_tag = title_tag.find('a')
            if link_tag:
                print(f"  [{i}] Nalezený text inzerátu: '{link_tag.text.strip()}'")
                title_text = link_tag.text.strip()
                job_url = link_tag.get('href')
                
                if any(kw in title_text.lower() for kw in KEYWORDS):
                    fe = fg.add_entry()
                    fe.title(f"Gisportal: {title_text}")
                    fe.link(href=job_url)
                    fe.description(f"Nová pozice na Gisportálu: {title_text}")
                    fe.guid(job_url, permalink=True)
                    jobs_found = True
        else:
            # Pokud nenašel h2.entry-title, zkusíme najít jakýkoliv odkaz uvnitř article
            any_link = article.find('a')
            if any_link:
                print(f"  [{i}] Alternativní odkaz text: '{any_link.text.strip()}'")

except Exception as e:
    print(f"Chyba při skrapování Gisportal: {e}")


# ----------------------------------------------------
# 2. DIAGNOSTIKA: ZEMEMERIC.CZ
# ----------------------------------------------------
try:
    url_zeme = "https://www.zememeric.cz/inzerce-pracovni-nabidky-prehled/"
    response = requests.get(url_zeme, verify=False, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    rows = soup.find_all('tr')
    print(f"Zeměměřič: Celkem nalezeno <tr> řádků: {len(rows)}")
    
    # Pokud nenašel tr, podíváme se, jestli tam vůbec je nějaká tabulka
    if len(rows) == 0:
        tables = soup.find_all('table')
        print(f"  Varování: Nalezeno <table> tagů: {len(tables)}")
    
    for i, row in enumerate(rows[1:6]): # Kontrola prvních 5 řádků (vynecháváme hlavičku)
        cells = row.find_all('td')
        if len(cells) >= 2:
            link_tag = cells[1].find('a')
            if link_tag:
                print(f"  [{i}] Nalezený text inzerátu: '{link_tag.text.strip()}'")
                title_text = link_tag.text.strip()
                job_url = link_tag.get('href')
                
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

print("=== DIAGNOSTIKA KONEC ===")

# Pojistka pro prázdný feed
if not jobs_found:
    print("VÝSLEDEK: Žádné nabídky neodpovídaly klíčovým slovům. Vytvářím prázdný feed.")
    fe = fg.add_entry()
    fe.title("Žádné nové pozice")
    fe.link(href="https://gisportal.cz/pracovni-nabidky/")
    fe.description(f"Při kontrole {datetime.now().strftime('%d.%m.%Y')} nebyly nalezeny žádné nové inzeráty.")
    fe.guid("no-jobs-today", permalink=False)

# Uložení do XML
fg.rss_file('pracovni_nabidky.xml', pretty=True)
