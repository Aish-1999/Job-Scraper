import requests
import warnings
warnings.filterwarnings("ignore")

HEADERS = {
    'User-Agent': 'Jobsuche/2.9.2 (de.arbeitsagentur.jobboerse; build:1077; iOS 15.1.0) Alamofire/5.4.4',
    'Host': 'rest.arbeitsagentur.de',
    'X-API-Key': 'jobboerse-jobsuche',
    'Connection': 'keep-alive',
}

params = {
    'angebotsart': '1',
    'page': '1',
    'pav': 'false',
    'size': '25',
    'umkreis': '200',
    'was': 'Data Scientist',
    'wo': 'Deutschland',
}

resp = requests.get(
    'https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/app/jobs',
    headers=HEADERS,
    params=params,
    verify=False
)

print(f"Status: {resp.status_code}")
print(f"Response length: {len(resp.text)}")
print(f"First 500 chars: {resp.text[:500]}")