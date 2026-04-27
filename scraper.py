import requests, json, smtplib, os, base64, warnings
from email.mime.text import MIMEText
warnings.filterwarnings("ignore")

# Load keywords
with open("keywords.json") as f:
    KEYWORDS = [k.lower() for k in json.load(f)["keywords"]]

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

HEADERS = {
    'User-Agent': 'Jobsuche/2.9.2 (de.arbeitsagentur.jobboerse; build:1077; iOS 15.1.0) Alamofire/5.4.4',
    'Host': 'rest.arbeitsagentur.de',
    'X-API-Key': 'jobboerse-jobsuche',
    'Connection': 'keep-alive',
}

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML"
    })

def send_email(subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_USER
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(EMAIL_USER, EMAIL_PASS)
        s.send_message(msg)

def matches(text):
    return any(k in text.lower() for k in KEYWORDS)

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
    }
    try:
        resp = requests.get(
            'https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/app/jobs',
            headers=HEADERS,
            params=params,
            verify=False,
            timeout=15
        )
        data = resp.json()
        for job in data.get("stellenangebote") or []:
            title   = job.get("titel", "")
            company = job.get("arbeitgeber", "Unknown")
            refnr   = job.get("refnr", "")
            encoded = base64.b64encode(refnr.encode()).decode()
            url     = f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{encoded}"
            if matches(title):
                jobs.append({
                    "title":   title,
                    "company": company,
                    "url":     url
                })
    except Exception as e:
        print(f"Error for query '{query}': {e}")
    return jobs

# Search queries
QUERIES = [
    "Data Scientist",
    "Machine Learning",
    "Data Analyst",
    "NLP",
    "Werkstudent Data",
    "Praktikum Data Science",
    "Deep Learning",
    "Computer Vision",
    "MLOps",
    "Künstliche Intelligenz"
]

# Run all searches
all_jobs = []
for query in QUERIES:
    results = scrape_arbeitsagentur(query)
    print(f"'{query}': {len(results)} jobs found")
    all_jobs.extend(results)

# Remove duplicates by URL
seen_urls = set()
unique_jobs = []
for job in all_jobs:
    if job["url"] not in seen_urls:
        seen_urls.add(job["url"])
        unique_jobs.append(job)

# Find new jobs
new_jobs = [j for j in unique_jobs if j["url"] not in seen]
print(f"\nTotal unique: {len(unique_jobs)}, New: {len(new_jobs)}")

# Send alerts
for job in new_jobs:
    msg = (
        f"🔔 <b>New Job Alert!</b>\n\n"
        f"<b>{job['title']}</b>\n"
        f"🏢 {job['company']}\n"
        f"🔗 {job['url']}"
    )
    send_telegram(msg)
    send_email(
        subject=f"New Job: {job['title']} at {job['company']}",
        body=f"{job['title']} at {job['company']}\n\n{job['url']}"
    )
    seen.add(job["url"])
    print(f"✅ Sent: {job['title']} at {job['company']}")

# Save seen jobs
with open("seen_jobs.json", "w") as f:
    json.dump(list(seen), f)

print("\nDone!")