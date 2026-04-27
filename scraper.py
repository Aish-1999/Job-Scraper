import requests, json, smtplib, os, base64, warnings
from datetime import datetime
from email.mime.text import MIMEText
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore")

SEEN_FILE = "seen_jobs.json"

# ==============================
# Load seen jobs
# ==============================
if os.path.exists(SEEN_FILE):
    try:
        with open(SEEN_FILE, "r") as f:
            seen = set(json.load(f))
    except:
        seen = set()
else:
    seen = set()

# ==============================
# ENV VARIABLES
# ==============================
BOT_TOKEN  = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID")
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")

# ==============================
# KEYWORDS
# ==============================
ROLE_KEYWORDS = [
    "data science", "machine learning", "nlp", "deep learning",
    "computer vision", "data analyst", "mlops", "ai",
    "künstliche intelligenz", "data engineer", "python"
]

STUDENT_KEYWORDS = [
    "werkstudent", "praktikum", "praktikant", "internship",
    "intern", "thesis", "bachelorarbeit", "masterarbeit",
    "abschlussarbeit", "student"
]

def is_relevant(title):
    t = title.lower()
    return any(r in t for r in ROLE_KEYWORDS) and any(s in t for s in STUDENT_KEYWORDS)

# STRICT: ONLY TODAY (for Arbeitsagentur)
def is_today(date_str):
    try:
        posted = datetime.strptime(date_str, "%Y-%m-%d").date()
        return posted == datetime.now().date()
    except:
        return False

# ==============================
# SMART SCORING
# ==============================
def score_job(title):
    t = title.lower()
    score = 0

    if any(r in t for r in ["data scientist", "machine learning", "ai", "deep learning"]):
        score += 40

    if any(s in t for s in STUDENT_KEYWORDS):
        score += 20

    if any(k in t for k in ["python", "nlp", "vision", "ml"]):
        score += 15

    if any(loc in t for loc in ["berlin", "munich", "hamburg"]):
        score += 10

    if any(b in t for b in ["senior", "lead", "manager", "consultant"]):
        score -= 30

    return score

# ==============================
# NOTIFICATIONS
# ==============================
def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Telegram not configured")
        return

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    )

def send_email(subject, body):
    if not EMAIL_USER or not EMAIL_PASS:
        print("⚠️ Email not configured")
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_USER

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(EMAIL_USER, EMAIL_PASS)
        s.send_message(msg)

# ==============================
# SOURCE 1: ARBEITSAGENTUR
# ==============================
HEADERS = {
    'User-Agent': 'Jobsuche/2.9.2',
    'X-API-Key': 'jobboerse-jobsuche',
}

def scrape_arbeitsagentur(query):
    jobs = []

    params = {
        'angebotsart': '1',
        'page': '1',
        'size': '25',
        'umkreis': '200',
        'was': query,
        'wo': 'Deutschland',
        'veroeffentlichtseit': '0'
    }

    try:
        resp = requests.get(
            'https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/app/jobs',
            headers=HEADERS,
            params=params,
            timeout=15
        )

        data = resp.json()

        for job in data.get("stellenangebote", []):
            title = job.get("titel", "")
            company = job.get("arbeitgeber", "")
            refnr = job.get("refnr", "")
            date_str = job.get("aktuelleVeroeffentlichungsdatum", "")

            if not refnr:
                continue

            encoded = base64.b64encode(refnr.encode()).decode()
            url = f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{encoded}"

            if is_relevant(title) and is_today(date_str):
                jobs.append({
                    "title": title,
                    "company": company,
                    "url": url,
                    "date": date_str,
                    "source": "AA"
                })

    except Exception as e:
        print("AA error:", e)

    return jobs

# ==============================
# SOURCE 2: INDEED
# ==============================
def scrape_indeed(query):
    jobs = []
    url = f"https://de.indeed.com/jobs?q={query}&l=Deutschland&fromage=1"

    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")

        cards = soup.select("a.tapItem")

        for card in cards[:15]:
            title_el = card.select_one("h2 span")
            company_el = card.select_one(".companyName")

            if not title_el:
                continue

            title = title_el.text.strip()
            company = company_el.text.strip() if company_el else "Unknown"
            link = "https://de.indeed.com" + card.get("href", "")

            if is_relevant(title):
                jobs.append({
                    "title": title,
                    "company": company,
                    "url": link,
                    "date": "Today",
                    "source": "Indeed"
                })

    except Exception as e:
        print("Indeed error:", e)

    return jobs

# ==============================
# RUN
# ==============================
QUERIES = [
    "Werkstudent Data Science",
    "Praktikum Machine Learning",
    "Werkstudent AI",
    "Praktikum NLP"
]

all_jobs = []

for q in QUERIES:
    all_jobs.extend(scrape_arbeitsagentur(q))
    all_jobs.extend(scrape_indeed(q))

# Deduplicate
unique_jobs = {j["url"]: j for j in all_jobs}.values()

# ==============================
# APPLY SCORING
# ==============================
scored_jobs = []

for j in unique_jobs:
    if j["url"] in seen:
        continue

    s = score_job(j["title"])
    if s >= 50:
        j["score"] = s
        scored_jobs.append(j)

# Sort best first
scored_jobs = sorted(scored_jobs, key=lambda x: x["score"], reverse=True)

# Only top jobs
new_jobs = scored_jobs[:10]

print("New high-quality jobs:", len(new_jobs))

# ==============================
# SEND ALERTS
# ==============================
for job in new_jobs:
    msg = (
        f"🔥 <b>{job['title']}</b>\n"
        f"🏢 {job['company']} ({job['source']})\n"
        f"⭐ Score: {job['score']}/100\n"
        f"📅 {job['date']}\n"
        f"🔗 {job['url']}"
    )

    send_telegram(msg)
    send_email(
        f"{job['title']} ({job['source']})",
        f"{job['title']} at {job['company']}\nScore: {job['score']}\n\n{job['url']}"
    )

    seen.add(job["url"])

# ==============================
# SAVE
# ==============================
with open(SEEN_FILE, "w") as f:
    json.dump(list(seen), f)

print("Done!")