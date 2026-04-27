import requests, json, smtplib, os, base64, warnings
from datetime import datetime, timedelta
from email.mime.text import MIMEText

warnings.filterwarnings("ignore")

# ==============================
# Load seen jobs
# ==============================
SEEN_FILE = "seen_jobs.json"

if os.path.exists(SEEN_FILE):
    try:
        with open(SEEN_FILE, "r") as f:
            seen = set(json.load(f))
    except:
        seen = set()
else:
    seen = set()

# ==============================
# Credentials
# ==============================
BOT_TOKEN  = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID")
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")

# ==============================
# Keywords
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

def is_recent(date_str):
    """Last 24 hours (approx since API gives only date)"""
    try:
        posted = datetime.strptime(date_str, "%Y-%m-%d")
        return datetime.now() - posted <= timedelta(days=1)
    except:
        return False

# ==============================
# Notifications
# ==============================
def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML"
    })

def send_email(subject, body):
    if not EMAIL_USER or not EMAIL_PASS:
        return
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_USER

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(EMAIL_USER, EMAIL_PASS)
        s.send_message(msg)

# ==============================
# API Config
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
        'veroeffentlichtseit': '1',  # last 24h
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
            title    = job.get("titel", "")
            company  = job.get("arbeitgeber", "Unknown")
            refnr    = job.get("refnr", "")
            date_str = job.get("aktuelleVeroeffentlichungsdatum", "")

            if not refnr:
                continue

            encoded = base64.b64encode(refnr.encode()).decode()
            url = f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{encoded}"

            if is_relevant(title) and is_recent(date_str):
                jobs.append({
                    "title": title,
                    "company": company,
                    "url": url,
                    "date": date_str
                })

    except Exception as e:
        print(f"Error for '{query}': {e}")

    return jobs

# ==============================
# Queries
# ==============================
QUERIES = [
    "Werkstudent Data Science",
    "Praktikum Machine Learning",
    "Werkstudent Machine Learning",
    "Praktikum Data Science",
    "Praktikum NLP",
    "Thesis Data Science",
    "Werkstudent NLP",
    "Praktikum Deep Learning",
    "Werkstudent AI",
    "Praktikum Künstliche Intelligenz"
]

# ==============================
# Run
# ==============================
all_jobs = []

for query in QUERIES:
    results = scrape_arbeitsagentur(query)
    print(f"{query}: {len(results)} jobs")
    all_jobs.extend(results)

# Deduplicate
unique_jobs = {job["url"]: job for job in all_jobs}.values()

# Filter new
new_jobs = [j for j in unique_jobs if j["url"] not in seen][:15]

print(f"\nNew jobs to send: {len(new_jobs)}")

for job in new_jobs:
    msg = (
        f"🔔 <b>{job['title']}</b>\n"
        f"🏢 {job['company']}\n"
        f"📅 {job['date']}\n"
        f"🔗 {job['url']}"
    )

    send_telegram(msg)
    send_email(
        f"{job['title']} at {job['company']}",
        f"{job['title']} at {job['company']}\n{job['date']}\n\n{job['url']}"
    )

    seen.add(job["url"])

# Save seen jobs
with open(SEEN_FILE, "w") as f:
    json.dump(list(seen), f)

print("Done!")