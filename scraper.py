import os
import time
import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from apify_client import ApifyClient
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit
import urllib3

# Zeměměřič i GISportál občas dělají problémy s ověřením certifikátu na
# některých sítích (např. GitHub Actions runnery) - stejně jako v ověřeně
# fungující verzi skriptu proto pro tyto dva zdroje vypínáme verify=True.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

RSS_FILE = "pracovni_nabidky.xml"

# Klíčová slova pro filtrování Zeměměřičovy sitemapy (ta obsahuje vedle
# pracovních nabídek i bazar geodetické techniky a hlášení o krádežích,
# takže bez filtru bychom je omylem přidávali taky).
KEYWORDS = ["gis", "analytik", "specialista", "vývojář", "developer", "zeměměřič",
            "geodet", "kartograf", "pracovník", "inženýr", "technik", "práce",
            "nabídka", "pozice"]


def strip_query(url: str) -> str:
    """Odstraní query string a fragment z URL, aby GUID zůstalo stabilní
    napříč jednotlivými spuštěními (např. jobs.cz přidává do URL pokaždé
    jiné ?searchId=..., což by jinak rozbilo deduplikaci)."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


# ----------------------------------------------------
# 1. NAČTENÍ EXISTUJÍCÍHO XML FEEDU (POKUD EXISTUJE)
# ----------------------------------------------------
print("=" * 60)
print("KROK 1: Načítám existující XML soubor...")
print("=" * 60)

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

        # Projdeme staré položky v XML
        for item in root.findall(".//item"):
            title = item.findtext("title") or ""
            link = item.findtext("link") or ""
            description = item.findtext("description") or ""
            guid = item.findtext("guid") or link
            pub_date = item.findtext("pubDate")

            if guid:
                guid_clean = guid.strip()
                if guid_clean not in seen_guids:
                    fe = fg.add_entry()
                    fe.title(title)
                    fe.link(href=link)
                    fe.description(description)
                    # BUG FIX: feedgen's guid() takes `permalink`, not `isPermalink`
                    fe.guid(guid_clean, permalink=True)

                    if pub_date:
                        try:
                            fe.pubDate(pub_date)
                        except Exception:
                            fe.pubDate(datetime.now(timezone.utc))

                    seen_guids.add(guid_clean)
                    print(f"  [Načteno z XML] GUID: {guid_clean}")

        print(f"--> CELKEM úspěšně načteno {len(seen_guids)} unikátních GUID ze souboru '{RSS_FILE}'.\n")
    except Exception as e:
        print(f"--> CHYBA při čtení XML souboru: {e}. Vytváří se zcela nový feed.\n")
else:
    print(f"--> Soubor '{RSS_FILE}' zatím neexistuje. Vytváří se nový.\n")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
new_count = 0

print("=" * 60)
print("KROK 2: Kontrola zdrojů a stahování nových nabídek...")
print("=" * 60)

# ----------------------------------------------------
# 2. LINKEDIN (přes Apify API)
# ----------------------------------------------------
APIFY_TOKEN = os.environ.get("APIFY_TOKEN")
if APIFY_TOKEN:
    try:
        print("\n--- Kontrola: LinkedIn ---")
        client = ApifyClient(APIFY_TOKEN)
        run_input = {
            "urls": ["https://www.linkedin.com/jobs/search/?keywords=GIS&location=Czechia&f_TPR=r1209600"],
            "deepScrape": False,
            "limit": 15
        }
        run = client.actor("curious_coder/linkedin-jobs-scraper").start(run_input=run_input)

        # BUG FIX: pevných 25s často nestačilo, než actor doběhne, takže
        # dataset byl prázdný a smyčka níže se nikdy nespustila (proto
        # v logu nebyla žádná chyba, ale ani žádná přidaná nabídka).
        # Místo toho na dokončení běhu aktivně čekáme (max. 120s).
        max_wait = 120
        waited = 0
        run_client = client.run(run["id"])
        status = run.get("status")
        while status not in ("SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED") and waited < max_wait:
            time.sleep(5)
            waited += 5
            status = run_client.get().get("status")

        print(f"  Stav Apify běhu: {status} (čekáno {waited}s)")

        dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items
        print(f"  Nalezeno {len(dataset_items)} položek z LinkedInu.")

        for item in dataset_items:
            title_text = item.get("title") or item.get("jobTitle") or item.get("position") or ""
            company = item.get("companyName") or item.get("company") or "LinkedIn"
            job_url = (item.get("link") or item.get("url") or item.get("jobUrl") or "").strip()

            if title_text and job_url:
                job_url = strip_query(job_url)
                if job_url not in seen_guids:
                    fe = fg.add_entry()
                    fe.title(f"LinkedIn: {title_text} ({company})")
                    fe.link(href=job_url)
                    fe.description(f"Pozice z LinkedInu: {title_text} - Firma: {company}")
                    # BUG FIX: permalink= instead of isPermalink=
                    fe.guid(job_url, permalink=True)
                    fe.pubDate(datetime.now(timezone.utc))

                    seen_guids.add(job_url)
                    new_count += 1
                    print(f"  + [PŘIDÁNO] {title_text} (GUID: {job_url})")
                else:
                    print(f"  - [SKOČENO - DUPLICITA] {title_text}")

        try:
            run_client.abort()
        except Exception:
            pass
    except Exception as e:
        print(f"  Chyba LinkedIn: {e}")
else:
    print("\n--- Kontrola: LinkedIn ---")
    print("  Přeskočeno: proměnná prostředí APIFY_TOKEN není nastavena.")


# ----------------------------------------------------
# 3. JOBS.CZ
# ----------------------------------------------------
print("\n--- Kontrola: Jobs.cz ---")
try:
    jobs_url = "https://www.jobs.cz/prace/praha/?q%5B%5D=gis&locality%5Bradius%5D=0"
    resp = requests.get(jobs_url, headers=headers, timeout=15)
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, "html.parser")

        # BUG FIX: web nově nepoužívá <article>/.SearchResultCard.
        # Nabídky poznáme podle odkazu vedoucího na detail /rpd/<id>/.
        link_tags = soup.select("h2 a[href*='/rpd/']")
        if not link_tags:
            link_tags = soup.select("a[href*='/rpd/']")

        seen_on_page = set()
        for link_tag in link_tags:
            title_text = link_tag.get_text(strip=True)
            job_link = link_tag.get("href", "").strip()
            if job_link.startswith("/"):
                job_link = f"https://www.jobs.cz{job_link}"

            # BUG FIX: jobs.cz přidává do URL proměnný ?searchId=...,
            # takže bychom bez očištění nikdy nenašli duplicitu a stejná
            # nabídka by se přidávala znovu a znovu při každém běhu.
            job_link = strip_query(job_link)

            if not title_text or not job_link or job_link in seen_on_page:
                continue
            seen_on_page.add(job_link)

            if job_link not in seen_guids:
                # Firmu se pokusíme dohledat v okolí nadpisu; pokud se
                # nepovede, nekrachujeme, jen necháme obecný popisek.
                company = "Jobs.cz"
                try:
                    card = link_tag.find_parent(["li", "div", "article"])
                    if card:
                        for li in card.find_all("li"):
                            text = li.get_text(strip=True)
                            if text and text != title_text and "hodnocení" not in text:
                                company = text
                                break
                except Exception:
                    pass

                fe = fg.add_entry()
                fe.title(f"Jobs.cz: {title_text} ({company})")
                fe.link(href=job_link)
                fe.description(f"Pozice z Jobs.cz: {title_text} - Firma: {company}")
                # BUG FIX: permalink= instead of isPermalink=
                fe.guid(job_link, permalink=True)
                fe.pubDate(datetime.now(timezone.utc))

                seen_guids.add(job_link)
                new_count += 1
                print(f"  + [PŘIDÁNO] {title_text} (GUID: {job_link})")
            else:
                print(f"  - [SKOČENO - DUPLICITA] {title_text}")
    else:
        print(f"  Jobs.cz vrátilo status kód {resp.status_code}")
except Exception as e:
    print(f"  Chyba Jobs.cz: {e}")


# ----------------------------------------------------
# 4. ZEMĚMĚŘIČ.CZ
# ----------------------------------------------------
print("\n--- Kontrola: Zeměměřič.cz ---")
try:
    # BUG FIX: doména "zememericskazurnalistika.cz" v původním kódu
    # neexistuje (proto DNS chyba). Místo lámání si hlavy s CSS selektory,
    # které se na webu časem mění, čteme rovnou WordPress/Rank Math
    # sitemapu pro rubriku "inzerce" - ta je stabilní a obsahuje URL
    # úplně všech inzerátů (nabídky práce i bazar techniky).
    sitemap_url = "https://www.zememeric.cz/inzerce-sitemap.xml"
    resp = requests.get(sitemap_url, headers=headers, timeout=15, verify=False)
    if resp.status_code == 200:
        soup_xml = BeautifulSoup(resp.text, "xml")
        urls = soup_xml.find_all("url")
        print(f"  Sitemapa obsahuje {len(urls)} položek (nabídky i bazar dohromady).")

        for url_tag in urls:
            loc_tag = url_tag.find("loc")
            if not loc_tag:
                continue
            job_link = loc_tag.text.strip()
            slug = job_link.rstrip("/").split("/")[-1]

            if slug in ("inzerce", ""):
                continue  # rozcestníková stránka, ne konkrétní inzerát

            title_text = slug.replace("-", " ").capitalize()

            # Filtr podle klíčových slov - sitemapa míchá pracovní nabídky
            # s inzeráty na prodej/krádež geodetické techniky.
            if not any(kw in title_text.lower() for kw in KEYWORDS):
                continue

            if job_link not in seen_guids:
                fe = fg.add_entry()
                fe.title(f"Zeměměřič: {title_text}")
                fe.link(href=job_link)
                fe.description(f"Nabídka z burzy práce Zeměměřič: {title_text}")
                # BUG FIX: permalink= instead of isPermalink=
                fe.guid(job_link, permalink=True)
                fe.pubDate(datetime.now(timezone.utc))

                seen_guids.add(job_link)
                new_count += 1
                print(f"  + [PŘIDÁNO] {title_text} (GUID: {job_link})")
            else:
                print(f"  - [SKOČENO - DUPLICITA] {title_text}")
    else:
        print(f"  Zeměměřič.cz sitemapa vrátila status kód {resp.status_code}")
except Exception as e:
    print(f"  Chyba Zeměměřič.cz: {e}")


# ----------------------------------------------------
# 5. GISPORTÁL.CZ
# ----------------------------------------------------
print("\n--- Kontrola: GISportál.cz ---")
try:
    # BUG FIX: stará adresa "gisportal.cz/category/prace-a-studium/"
    # vrací 404. Aktuální stránka s nabídkami je:
    gisportal_url = "https://gisportal.cz/pracovni-nabidky/"
    resp = requests.get(gisportal_url, headers=headers, timeout=15, verify=False)
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, "html.parser")
        h3_tags = soup.find_all("h3")
        print(f"  Nalezeno {len(h3_tags)} nadpisů h3 na stránce.")

        found_any = False
        for h3 in h3_tags:
            a_tag = h3.find("a") or h3.find_parent("a")
            if not (a_tag and a_tag.get("href")):
                continue

            title_text = h3.get_text(strip=True)
            job_link = a_tag["href"].strip()
            if not title_text:
                continue
            found_any = True
            job_link = strip_query(job_link)

            if job_link not in seen_guids:
                fe = fg.add_entry()
                fe.title(f"GISportál: {title_text}")
                fe.link(href=job_link)
                fe.description(f"Pracovní nabídka z GISportálu: {title_text}")
                # BUG FIX: permalink= instead of isPermalink=
                fe.guid(job_link, permalink=True)
                fe.pubDate(datetime.now(timezone.utc))

                seen_guids.add(job_link)
                new_count += 1
                print(f"  + [PŘIDÁNO] {title_text} (GUID: {job_link})")
            else:
                print(f"  - [SKOČENO - DUPLICITA] {title_text}")

        if not found_any:
            # POZOR: v mém testování GISportál aktuálně vykresluje výpis
            # nabídek přes JavaScript/AJAX, takže syrové HTML žádné <h3>
            # s nabídkou neobsahuje. Kód zde zůstává (a nic nekrachuje),
            # kdyby se to na straně webu změnilo zpět na statické
            # vykreslování - jinak by případný trvalý fix vyžadoval
            # prohlížeč (Selenium/Playwright) nebo nalezení jejich
            # interního AJAX endpointu.
            print("  Žádné nabídky v h3 nadpisech nenalezeny (web je pravděpodobně "
                  "vykresluje přes JavaScript). Zdroj pro tento běh nic nepřidal.")
    else:
        print(f"  GISportál.cz vrátilo status kód {resp.status_code}")
except Exception as e:
    print(f"  Chyba GISportál.cz: {e}")


# ----------------------------------------------------
# 6. ULOŽENÍ AKTUALIZOVANÉHO XML SOUBORU
# ----------------------------------------------------
print("\n" + "=" * 60)
print("KROK 3: Ukládání výsledku...")
print("=" * 60)
fg.rss_file(RSS_FILE, pretty=True)
print(f"Podařilo se přidat {new_count} nových nabídek.")
print(f"XML soubor '{RSS_FILE}' byl uložen. Nyní obsahuje celkem {len(seen_guids)} nabídek.")
