"""
Job Intel — Daily Scraper (351 Saudi Government Entities + Job Boards)
Runs via GitHub Actions at 9am GST (6am UTC).
Outputs jobs.json for the frontend.
"""

import json
import hashlib
import re
import time
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

# ═══════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════

UA = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
]

KEYWORDS = [
    "innovation manager", "strategy director", "transformation lead",
    "digital transformation", "corporate development", "AI strategy",
    "technology director", "management consultant", "Vision 2030",
    "innovation director", "head of strategy", "product director",
    "مدير الابتكار", "تحول رقمي", "استراتيجية",
]

# Load all 351 entities
ENTITIES_PATH = Path(__file__).parent / "entities.json"
ALL_ENTITIES = json.loads(ENTITIES_PATH.read_text(encoding="utf-8")) if ENTITIES_PATH.exists() else []
print(f"Loaded {len(ALL_ENTITIES)} entities from entities.json")

session = requests.Session()


# ═══════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════

def get(url, params=None, timeout=15):
    session.headers.update({"User-Agent": random.choice(UA)})
    time.sleep(random.uniform(1.0, 2.5))
    try:
        r = session.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception as e:
        return None


def fp(title, company):
    s = f"{title.lower().strip()}|{company.lower().strip()}"
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def parse_date(text):
    if not text:
        return date.today().isoformat()
    text = text.strip().lower()
    today = date.today()
    for pat, unit in [(r"(\d+)\s*day", "d"), (r"(\d+)\s*hour", "h"), (r"(\d+)\s*week", "w"),
                      (r"(\d+)\s*month", "m"), (r"today|just now", "0"), (r"yesterday", "1"),
                      (r"منذ\s*(\d+)\s*يوم", "d"), (r"منذ\s*(\d+)\s*أسبوع", "w")]:
        m = re.search(pat, text)
        if m:
            if unit in ("0", "h"):
                return today.isoformat()
            if unit == "1":
                return (today - timedelta(days=1)).isoformat()
            n = int(m.group(1)) if m.groups() else 1
            delta = {"d": timedelta(days=n), "w": timedelta(weeks=n), "m": timedelta(days=n*30)}
            return (today - delta.get(unit, timedelta(0))).isoformat()
    return today.isoformat()


def detect_seniority(title):
    t = title.lower()
    if any(w in t for w in ["chief", "cto", "ceo", "cfo", "vp", "vice president"]):
        return "executive"
    if any(w in t for w in ["director", "head of", "general manager"]):
        return "director"
    if any(w in t for w in ["senior", "sr.", "lead", "principal", "manager"]):
        return "senior"
    if any(w in t for w in ["junior", "jr.", "associate", "intern"]):
        return "junior"
    return "mid"


def detect_category(title, tags):
    t = (title + " " + " ".join(tags)).lower()
    if any(w in t for w in ["strategy", "consulting", "consultant", "advisory", "governance", "policy"]):
        return "Strategy & Consulting"
    if any(w in t for w in ["technology", "product", "ai", "data", "cyber", "digital", "cloud", "it ", "software"]):
        return "Technology & Product"
    if any(w in t for w in ["operations", "program", "project", "construction", "infrastructure"]):
        return "Operations & Execution"
    if any(w in t for w in ["finance", "investment", "fund", "risk", "banking"]):
        return "Finance & Investment"
    return "Strategy & Consulting"


HIGH_COMPANIES = {"pif", "neom", "qiddiya", "stc", "aramco", "sdaia", "bcg", "mckinsey",
                  "bain", "kaust", "roshn", "humain", "elm", "red sea", "acwa"}


def score_job(title, company, tags, signals):
    s = 0.50
    for w in ["innovation", "strategy", "transformation", "director", "head", "lead", "chief"]:
        if w in title.lower():
            s += 0.05
    for c in HIGH_COMPANIES:
        if c in company.lower():
            s += 0.04
            break
    for t in ["innovation", "strategy", "transformation", "ai", "vision-2030"]:
        if t in tags:
            s += 0.02
    s += len(signals) * 0.015
    return round(min(s, 0.98), 2)


def make_job(title, company, city, source, url, tags=None, signals=None, posted="", summary=""):
    tg = list(set((tags or [])[:5]))
    sg = list(set((signals or [])[:3]))
    return {
        "id": fp(title, company), "src": source,
        "t": title[:120], "co": company[:80], "cy": city or "Riyadh", "ct": "SA",
        "ca": detect_category(title, tg), "tg": tg, "sg": sg,
        "sn": detect_seniority(title), "sc": score_job(title, company, tg, sg),
        "sm": (summary or "")[:200], "st": "new",
        "dt": parse_date(posted), "u": url,
    }


# ═══════════════════════════════════════════
# SOURCE 1: BAYT.COM
# ═══════════════════════════════════════════
def scrape_bayt(keyword, max_pages=2):
    jobs = []
    for page in range(1, max_pages + 1):
        resp = get("https://www.bayt.com/en/saudi-arabia/jobs/", params={"keyword": keyword, "page": page})
        if not resp:
            break
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("li[data-js-job]") or soup.select(".has-pointer-d") or soup.select("li.is-compact")
        if not cards:
            break
        for card in cards:
            try:
                a = card.select_one("h2 a") or card.select_one("a")
                if not a:
                    continue
                title = a.get_text(strip=True)
                if not title or len(title) < 5:
                    continue
                href = a.get("href", "")
                url = f"https://www.bayt.com{href}" if href.startswith("/") else href
                co = (card.select_one(".t-mute a") or card.select_one("[data-automation-id='company']"))
                company = co.get_text(strip=True) if co else ""
                loc = card.select_one(".t-mute span")
                location = loc.get_text(strip=True) if loc else ""
                city = "Riyadh"
                for c in ["Riyadh","Jeddah","Dammam","Dhahran","NEOM","Jubail","Mecca","Tabuk","Khobar"]:
                    if c.lower() in location.lower():
                        city = c; break
                dt_el = card.select_one("time") or card.select_one(".t-small")
                posted = dt_el.get_text(strip=True) if dt_el else ""
                j = make_job(title, company, city, "bayt", url, tags=[keyword.lower().replace(" ","-")], posted=posted)
                if j["co"]:
                    jobs.append(j)
            except Exception:
                continue
    return jobs


# ═══════════════════════════════════════════
# SOURCE 2: CAREERJET
# ═══════════════════════════════════════════
def scrape_careerjet(keyword, max_pages=1):
    jobs = []
    for page in range(1, max_pages + 1):
        resp = get("https://www.careerjet.com.sa/search/jobs", params={"s": keyword, "l": "Saudi Arabia", "p": page})
        if not resp:
            break
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("article.job") or soup.select("li.job")
        if not cards:
            links = soup.find_all("a", href=re.compile(r"/jobad/"))
            cards = [l.parent for l in links if l.parent] if links else []
        if not cards:
            break
        for card in cards:
            try:
                a = card.select_one("h2 a") or card.select_one("a[href*='/jobad/']")
                if not a:
                    continue
                title = a.get_text(strip=True)
                if not title or len(title) < 5:
                    continue
                href = a.get("href", "")
                url = urljoin("https://www.careerjet.com.sa", href)
                co = card.select_one(".company")
                company = co.get_text(strip=True) if co else ""
                loc = card.select_one(".location")
                location = loc.get_text(strip=True) if loc else ""
                city = "Riyadh"
                for c in ["Riyadh","Jeddah","Dammam","Dhahran","NEOM","Jubail"]:
                    if c.lower() in location.lower():
                        city = c; break
                desc = card.select_one(".desc")
                summary = desc.get_text(strip=True)[:200] if desc else ""
                j = make_job(title, company, city, "careerjet", url,
                            tags=[keyword.lower().replace(" ","-")], summary=summary)
                if j["co"]:
                    jobs.append(j)
            except Exception:
                continue
    return jobs


# ═══════════════════════════════════════════
# SOURCE 3: LINKEDIN PUBLIC
# ═══════════════════════════════════════════
def scrape_linkedin(keyword):
    jobs = []
    kw = quote_plus(keyword)
    resp = get(f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={kw}&location=Saudi%20Arabia&geoId=100459316&start=0&sortBy=DD")
    if not resp:
        return jobs
    soup = BeautifulSoup(resp.text, "html.parser")
    for card in soup.select("li"):
        try:
            a = card.select_one("a.base-card__full-link") or card.select_one("a[href*='/jobs/view/']")
            if not a:
                continue
            title_el = card.select_one("h3") or card.select_one(".base-search-card__title")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title or len(title) < 5:
                continue
            href = a.get("href", "").split("?")[0]
            url = href if href.startswith("http") else f"https://www.linkedin.com{href}"
            co = card.select_one("h4") or card.select_one(".base-search-card__subtitle")
            company = co.get_text(strip=True) if co else ""
            loc = card.select_one(".job-search-card__location")
            location = loc.get_text(strip=True) if loc else ""
            city = "Riyadh"
            for c in ["Riyadh","Jeddah","Dammam","Dhahran","NEOM","Jubail"]:
                if c.lower() in location.lower():
                    city = c; break
            tm = card.select_one("time")
            posted = tm.get("datetime", "") if tm else ""
            j = make_job(title, company, city, "linkedin", url,
                        tags=[keyword.lower().replace(" ","-")], posted=posted)
            if j["co"]:
                jobs.append(j)
        except Exception:
            continue
    return jobs


# ═══════════════════════════════════════════
# SOURCE 4: ALL 351 GOVERNMENT ENTITIES
# ═══════════════════════════════════════════
def scrape_all_entities():
    """
    For each of the 351 entities:
    1. Search Bayt.com for "[entity name] jobs"
    2. If entity has a website, try to find career links
    3. Add LinkedIn jobs link if available
    """
    jobs = []
    total = len(ALL_ENTITIES)

    for i, ent in enumerate(ALL_ENTITIES):
        name = ent["name"]
        url = ent.get("url", "")
        linkedin = ent.get("linkedin", "")

        # Progress
        if (i + 1) % 50 == 0 or i == 0:
            print(f"    [{i+1}/{total}] Processing {name}...")

        # Method 1: Search Bayt for this entity (batch — only do first word + "jobs")
        # We do this in batches to avoid rate limits
        if (i + 1) % 10 == 0:  # Every 10th entity, search Bayt
            try:
                search_name = name.split("(")[0].strip()[:40]  # Trim long names
                bayt_jobs = scrape_bayt(search_name, max_pages=1)
                for j in bayt_jobs:
                    j["src"] = "gov"
                jobs.extend(bayt_jobs)
            except Exception:
                pass

        # Method 2: If entity has a website, try scraping career links
        if url:
            try:
                resp = get(url, timeout=10)
                if resp:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    # Look for career/job links
                    career_links = soup.find_all("a", href=re.compile(r"(?i)career|job|vacanc|hiring|وظائف|توظيف"))
                    for link in career_links[:3]:
                        text = link.get_text(strip=True)
                        if text and 5 < len(text) < 120:
                            href = link.get("href", "")
                            link_url = href if href.startswith("http") else urljoin(url, href)
                            # This is a careers page link, not a specific job
                            # We'll add it as a portal entry
                            j = make_job(f"Careers at {name}", name, "Riyadh", "gov", link_url,
                                        tags=["government", "vision-2030"],
                                        summary=f"{name} is hiring. Visit their careers portal.")
                            jobs.append(j)
                            break  # One entry per entity
            except Exception:
                pass

        # Method 3: Add LinkedIn jobs link if available
        if linkedin and not any(j["co"] == name for j in jobs):
            linkedin_jobs = linkedin.rstrip("/") + "/jobs/" if "/jobs" not in linkedin else linkedin
            j = make_job(f"Open Roles — {name}", name, "Riyadh", "gov", linkedin_jobs,
                        tags=["government", "vision-2030"],
                        summary=f"{name} ({ent.get('name_ar', '')}). Check LinkedIn for current openings.")
            jobs.append(j)

    return jobs


# ═══════════════════════════════════════════
# DEDUP
# ═══════════════════════════════════════════
def deduplicate(jobs):
    seen = set()
    unique = []
    for j in jobs:
        if j["id"] not in seen:
            seen.add(j["id"])
            unique.append(j)
    return unique


# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════
def main():
    print(f"{'='*60}")
    print(f"JOB INTEL — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"351 Saudi Entities + Job Boards")
    print(f"{'='*60}")

    all_jobs = []

    # 1. Bayt.com keywords
    print("\n[1/4] BAYT.COM — Keyword Search")
    for kw in KEYWORDS[:10]:
        try:
            jobs = scrape_bayt(kw, max_pages=2)
            all_jobs.extend(jobs)
            print(f"  '{kw}' → {len(jobs)}")
        except Exception as e:
            print(f"  '{kw}' → ERR: {e}")

    # 2. Careerjet
    print("\n[2/4] CAREERJET — Aggregator")
    for kw in KEYWORDS[:6]:
        try:
            jobs = scrape_careerjet(kw)
            all_jobs.extend(jobs)
            print(f"  '{kw}' → {len(jobs)}")
        except Exception as e:
            print(f"  '{kw}' → ERR: {e}")

    # 3. LinkedIn
    print("\n[3/4] LINKEDIN — Public API")
    for kw in KEYWORDS[:4]:
        try:
            jobs = scrape_linkedin(kw)
            all_jobs.extend(jobs)
            print(f"  '{kw}' → {len(jobs)}")
        except Exception as e:
            print(f"  '{kw}' → ERR: {e}")

    # 4. ALL 351 Government Entities
    print(f"\n[4/4] ALL {len(ALL_ENTITIES)} GOVERNMENT & PIF ENTITIES")
    try:
        gov = scrape_all_entities()
        all_jobs.extend(gov)
        print(f"  Total entity jobs: {len(gov)}")
    except Exception as e:
        print(f"  ERR: {e}")

    # Dedup & sort
    unique = deduplicate(all_jobs)
    unique.sort(key=lambda j: j["sc"], reverse=True)

    print(f"\n{'='*60}")
    print(f"RAW: {len(all_jobs)} → UNIQUE: {len(unique)}")

    # Preserve statuses
    prev = Path("jobs.json")
    smap = {}
    if prev.exists():
        try:
            old = json.loads(prev.read_text())
            for j in old.get("jobs", []):
                if j.get("st") not in (None, "new"):
                    smap[j["id"]] = j["st"]
        except Exception:
            pass
    for j in unique:
        if j["id"] in smap:
            j["st"] = smap[j["id"]]

    # Write
    out = {"updated": datetime.now().isoformat(), "count": len(unique), "jobs": unique[:300]}
    Path("jobs.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"Wrote {out['count']} jobs → jobs.json")
    print(f"Updated: {out['updated']}")


if __name__ == "__main__":
    main()
