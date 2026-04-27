import requests, json, smtplib, os, base64, warnings
from datetime import datetime, timedelta
from email.mime.text import MIMEText
warnings.filterwarnings("ignore")

# Load seen jobs
try:
    with open("seen_jobs.json") as f:
        seen = set(json.load(f))
except:
    seen = set()

# Credentials
BOT_TOKEN  = os.environ["TELEGRAM_TOKEN"]
CHAT_ID    = os.environ["TELEGRAM_CHAT_ID"]
EMAIL_USER = os.environ["EMAIL_USER"]
EMAIL_PASS = os.environ["EMAIL_PASS"]

# Must match BOTH a role AND a student keyword
ROLE_KEYWORDS = [
    "data science", "machine learning", "nlp", "deep learning",
    "computer vision", "data analyst", "mlops", "ai ",
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
    """Only allow jobs posted in last 2 days"""
    try:
        posted = datetime.strptime(date_str, "%Y-%m-%d")
        return datetime.now() - posted <= timedelta(days=2)
    except:
        return False

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})

def send_email(subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_USER
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(EMAIL_USER, EMAIL_PASS)
        s.send_message(msg)

HEADERS = {
    'User-Agent': 'Jobsuche/2.9.2 (de.arbeitsagentur.jobboerse; build:1077; iOS 15.1.0) Alamofire/5.4.4',
    'Host': 'rest.arbeitsagentur.de',
    'X-API-Key': 'jobboerse-jobsuche',
    'Connection': 'keep-alive',
}

def scrape_arbeitsagentur(query):
    jobs = []
    params = {
        'angebotsart': '1',
        'page': '1',
        'pav': 'false',
        'size': '25',
        'umkreis': '200',
        'was': query,
        'wo': 'Deutschland',
        'veroeffentlichtseit': '2',  # only last 2 days
    }
    try:
        resp = requests.get(
            'https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/app/jobs',
            headers=HEADERS, params=params, verify=False, timeout=15
        )
        data = resp.json()
        for job in data.get("stellenangebote") or []:
            title    = job.get("titel", "")
            company  = job.get("arbeitgeber", "Unknown")
            refnr    = job.get("refnr", "")
            date_str = job.get("aktuelleVeroeffentlichungsdatum", "")
            encoded  = base64.b64encode(refnr.encode()).decode()
            url      = f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{encoded}"

            # Double check date in case API ignores the filter
            if is_relevant(title) and is_recent(date_str):
                jobs.append({
                    "title":   title,
                    "company": company,
                    "url":     url,
                    "date":    date_str,
                    "source":  "Arbeitsagentur"
                })
    except Exception as e:
        print(f"Error for '{query}': {e}")
    return jobs

# Search queries
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

# Run all searches
all_jobs = []
for query in QUERIES:
    results = scrape_arbeitsagentur(query)
    print(f"'{query}': {len(results)} fresh jobs")
    all_jobs.extend(results)

# Deduplicate by URL
seen_urls = set()
unique_jobs = []
for job in all_jobs:
    if job["url"] and job["url"] not in seen_urls:
        seen_urls.add(job["url"])
        unique_jobs.append(job)

# Only new ones, max 15
new_jobs = [j for j in unique_jobs if j["url"] not in seen][:15]
print(f"\nTotal unique fresh: {len(unique_jobs)}, New to send: {len(new_jobs)}")

for job in new_jobs:
    msg = (
        f"🔔 <b>New Job Alert!</b>\n\n"
        f"<b>{job['title']}</b>\n"
        f"🏢 {job['company']}\n"
        f"📅 Posted: {job['date']}\n"
        f"🔗 {job['url']}"
    )
    send_telegram(msg)
    send_email(
        subject=f"New Job: {job['title']} at {job['company']}",
        body=f"{job['title']} at {job['company']}\nPosted: {job['date']}\n\n{job['url']}"
    )
    seen.add(job["url"])
    print(f"✅ Sent: {job['title']} | {job['date']}")

with open("seen_jobs.json", "w") as f:
    json.dump(list(seen), f)

print("Done!")