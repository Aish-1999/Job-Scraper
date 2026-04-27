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

# Must have BOTH a role keyword AND a student keyword
ROLE_KEYWORDS = [
    "data science", "machine learning", "nlp", "deep learning",
    "computer vision", "data analyst", "mlops", "ki ", "ai ",
    "künstliche intelligenz", "data engineer"
]

STUDENT_KEYWORDS = [
    "werkstudent", "praktikum", "praktikant", "internship",
    "intern", "thesis", "bachelorarbeit", "masterarbeit",
    "abschlussarbeit", "student"
]

def is_relevant(title):
    title = title.lower()
    has_role    = any(k in title for k in ROLE_KEYWORDS)
    has_student = any(k in title for k in STUDENT_KEYWORDS)
    return has_role and has_student

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
    'veroeffentlichtseit': '1',  # only jobs posted in last 24 hours
}
    try:
        resp = requests.get(
            'https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/app/jobs',
            headers=HEADERS, params=params, verify=False, timeout=15
        )
        data = resp.json()
        for job in data.get("stellenangebote") or []:
            title   = job.get("titel", "")
            company = job.get("arbeitgeber", "Unknown")
            refnr   = job.get("refnr", "")
            encoded = base64.b64encode(refnr.encode()).decode()
            url     = f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{encoded}"
            if is_relevant(title):
                jobs.append({
                    "title":   title,
                    "company": company,
                    "url":     url,
                    "source":  "Arbeitsagentur"
                })
    except Exception as e:
        print(f"Arbeitsagentur error: {e}")
    return jobs

def scrape_linkedin(query):
    jobs = []
    url = f"https://www.linkedin.com/jobs/search/?keywords={query}&location=Germany&f_E=1%2C2&sortBy=DD"
    try:
        from bs4 import BeautifulSoup
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        for card in soup.select(".base-card"):
            title   = card.select_one(".base-search-card__title")
            company = card.select_one(".base-search-card__subtitle")
            link    = card.select_one("a")
            if title and is_relevant(title.text):
                jobs.append({
                    "title":   title.text.strip(),
                    "company": company.text.strip() if company else "Unknown",
                    "url":     link["href"].split("?")[0] if link else "",
                    "source":  "LinkedIn"
                })
    except Exception as e:
        print(f"LinkedIn error: {e}")
    return jobs

# Run scrapers
print("Scraping Arbeitsagentur...")
aa_jobs = (
    scrape_arbeitsagentur("Werkstudent Data Science") +
    scrape_arbeitsagentur("Praktikum Machine Learning") +
    scrape_arbeitsagentur("Werkstudent Machine Learning") +
    scrape_arbeitsagentur("Praktikum Data Science") +
    scrape_arbeitsagentur("Praktikum NLP") +
    scrape_arbeitsagentur("Thesis Data Science")
)
print(f"Arbeitsagentur: {len(aa_jobs)} relevant jobs")

print("Scraping LinkedIn...")
li_jobs = (
    scrape_linkedin("werkstudent+data+science+germany") +
    scrape_linkedin("praktikum+machine+learning+germany") +
    scrape_linkedin("data+science+internship+germany")
)
print(f"LinkedIn: {len(li_jobs)} relevant jobs")

# Combine and deduplicate
all_jobs = aa_jobs + li_jobs
seen_urls = set()
unique_jobs = []
for job in all_jobs:
    if job["url"] and job["url"] not in seen_urls:
        seen_urls.add(job["url"])
        unique_jobs.append(job)

# Only new jobs, max 15 per run
new_jobs = [j for j in unique_jobs if j["url"] not in seen][:15]
print(f"New jobs to send: {len(new_jobs)}")

for job in new_jobs:
    msg = (
        f"🔔 <b>New Job Alert!</b>\n\n"
        f"<b>{job['title']}</b>\n"
        f"🏢 {job['company']}\n"
        f"📌 {job['source']}\n"
        f"🔗 {job['url']}"
    )
    send_telegram(msg)
    send_email(
        subject=f"[{job['source']}] {job['title']} at {job['company']}",
        body=f"{job['title']} at {job['company']}\nSource: {job['source']}\n\n{job['url']}"
    )
    seen.add(job["url"])
    print(f"✅ Sent: {job['title']} at {job['company']}")

with open("seen_jobs.json", "w") as f:
    json.dump(list(seen), f)

print("Done!")