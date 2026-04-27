import requests, json, smtplib, os
from bs4 import BeautifulSoup
from email.mime.text import MIMEText

# Load config
with open("keywords.json") as f:
    KEYWORDS = [k.lower() for k in json.load(f)["keywords"]]

try:
    with open("seen_jobs.json") as f:
        seen = set(json.load(f))
except:
    seen = set()

BOT_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
EMAIL_USER = os.environ["EMAIL_USER"]
EMAIL_PASS = os.environ["EMAIL_PASS"]

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

def matches(text):
    text = text.lower()
    return any(k in text for k in KEYWORDS)

def scrape_indeed_germany():
    jobs = []
    url = "https://de.indeed.com/jobs?q=data+science+praktikum&l=Deutschland"
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(resp.text, "html.parser")
    for card in soup.select(".job_seen_beacon"):
        title = card.select_one("h2 span")
        company = card.select_one(".companyName")
        link = card.select_one("h2 a")
        if title and matches(title.text):
            jobs.append({
                "title": title.text.strip(),
                "company": company.text.strip() if company else "?",
                "url": "https://de.indeed.com" + link["href"] if link else ""
            })
    return jobs

# Add more scraper functions here for LinkedIn, StepStone, etc.
all_jobs = scrape_indeed_germany()

new_jobs = [j for j in all_jobs if j["url"] not in seen]

for job in new_jobs:
    msg = f"🔔 <b>New Job!</b>\n{job['title']}\n{job['company']}\n{job['url']}"
    send_telegram(msg)
    send_email(f"New Job: {job['title']}", f"{job['title']} at {job['company']}\n{job['url']}")
    seen.add(job["url"])

with open("seen_jobs.json", "w") as f:
    json.dump(list(seen), f)