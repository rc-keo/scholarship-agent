import os
import re
import csv
import sys
import json
import time
import glob
import math
import smtplib
import tldextract
import requests
import dateparser
import pandas as pd
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from email import encoders
from readability import Document

# -------------------- settings & inputs --------------------

HERE = os.path.dirname(os.path.abspath(__file__))

QUERIES_PATH = os.path.join(HERE, "queries.json")
CONFIG_PATH  = os.path.join(HERE, "config.yaml")

FUNDING_KEYWORDS = [
    "scholarship", "scholarships", "fellowship", "stipend", "stipends",
    "tuition waiver", "tuition waivers", "fee waiver", "funded",
    "graduate assistantship", "teaching assistantship", "research assistantship",
    "assistantship", "tuition covered", "tuition remission", "tuition reduction",
    "living allowance", "monthly allowance", "tuition support", "full funding"
]

NO_GRE_SIGNS = [
    "no gre", "gre not required", "gre waived", "gre waiver"
]

NO_IELTS_SIGNS = [
    "ielts waiver", "ielts not required", "english proficiency waiver",
    "medium of instruction", "moi", "waive ielts"
]

DEADLINE_PATTERNS = [
    r"deadline[:\s-]*([A-Za-z]{3,9}\s\d{1,2},\s\d{4})",
    r"deadline[:\s-]*([A-Za-z]{3,9}\s\d{1,2})",
    r"apply by[:\s-]*([A-Za-z]{3,9}\s\d{1,2},\s\d{4})",
    r"application deadline[:\s-]*([A-Za-z]{3,9}\s\d{1,2},\s\d{4})",
    r"closing date[:\s-]*([A-Za-z]{3,9}\s\d{1,2},\s\d{4})",
    r"(\d{1,2}\s[A-Za-z]{3,9}\s\d{4})",
    r"([A-Za-z]{3,9}\s\d{1,2},\s\d{4})"
]

CSV_NAME = "scholarships_latest.csv"

# -------------------- helpers --------------------

def safe_get(url, timeout=20, headers=None):
    headers = headers or {"User-Agent": "Mozilla/5.0 (ScholarshipAgent)"}
    try:
        r = requests.get(url, timeout=timeout, headers=headers, allow_redirects=True)
        if r.status_code in (200, 201):
            return r.text, r.url
        return None, url
    except Exception:
        return None, url

def extract_main_text(html, url):
    if not html:
        return "", ""
    try:
        doc = Document(html)
        title = doc.short_title() or ""
        content_html = doc.summary()
        soup = BeautifulSoup(content_html, "lxml")
        text = soup.get_text(separator="\n", strip=True)
        return text, title
    except Exception:
        soup = BeautifulSoup(html, "lxml")
        title = soup.title.get_text(strip=True) if soup.title else ""
        text = soup.get_text(separator="\n", strip=True)
        return text, title

def domain_of(url):
    try:
        ext = tldextract.extract(url)
        return ".".join(part for part in [ext.domain, ext.suffix] if part)
    except Exception:
        return urlparse(url).netloc

def find_signals(text, keywords):
    text_l = text.lower()
    hits = [kw for kw in keywords if kw in text_l]
    return list(dict.fromkeys(hits))

def find_deadlines(text):
    found = set()
    for pat in DEADLINE_PATTERNS:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            raw = m.group(1) if m.groups() else m.group(0)
            dt = dateparser.parse(raw, settings={"PREFER_DATES_FROM": "future"})
            if dt:
                found.add(dt.strftime("%Y-%m-%d"))
    return sorted(found)

def score_item(text):
    s = 0.0
    funding_hits = find_signals(text, FUNDING_KEYWORDS)
    s += 0.5 * len(funding_hits)
    gre_hits = find_signals(text, NO_GRE_SIGNS)
    ielts_hits = find_signals(text, NO_IELTS_SIGNS)
    if gre_hits:
        s += 0.5
    if ielts_hits:
        s += 0.3
    deadlines = find_deadlines(text)
    if deadlines:
        s += 0.4
    return s, funding_hits, gre_hits, ielts_hits, deadlines

def load_json(fp, default):
    try:
        with open(fp, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def load_yaml(fp):
    try:
        import yaml
    except ImportError:
        return {"filters": {"min_score": 2.5, "max_results_per_query": 20, "max_total_results": 120}}
    try:
        with open(fp, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return {"filters": {"min_score": 2.5, "max_results_per_query": 20, "max_total_results": 120}}

# -------------------- search --------------------

def ddg_search(q, max_results=20):
    \"\"\"DuckDuckGo search via duckduckgo_search package\"\"\"
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(q, max_results=max_results):
                # r keys: title, href, body
                results.append({\"title\": r.get(\"title\",\"\"), \"url\": r.get(\"href\",\"\"), \"snippet\": r.get(\"body\",\"\")})
        return results
    except Exception as e:
        print(\"Search error:\", e)
        return []

# -------------------- email --------------------

def send_email(csv_path, rows_len, subject=\"Scholarship Digest\", from_name=\"Scholarship Agent\"):
    user = os.getenv(\"EMAIL_USER\")
    pwd  = os.getenv(\"EMAIL_PASS\")
    to   = os.getenv(\"TO_EMAIL\")
    if not (user and pwd and to):
        print(\"EMAIL_USER/EMAIL_PASS/TO_EMAIL not set; skipping email.\")
        return False

    msg = MIMEMultipart()
    msg[\"From\"] = formataddr((from_name, user))
    msg[\"To\"] = to
    msg[\"Subject\"] = subject

    body = MIMEText(f\"Hi,\\n\\nAttached are {rows_len} curated MSc opportunities (scholarships/TA/GA/tuition waivers).\\nPlease verify details on the official pages.\\n\\nRegards,\\nScholarship Agent\", \"plain\")
    msg.attach(body)

    with open(csv_path, \"rb\") as f:
        part = MIMEBase(\"application\", \"octet-stream\")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header(\"Content-Disposition\", f\"attachment; filename={os.path.basename(csv_path)}\")
    msg.attach(part)

    try:
        with smtplib.SMTP_SSL(\"smtp.gmail.com\", 465) as server:
            server.login(user, pwd)
            server.sendmail(user, [to], msg.as_string())
        print(\"Email sent to\", to)
        return True
    except Exception as e:
        print(\"Email send error:\", e)
        return False

# -------------------- main pipeline --------------------

def main():
    queries = load_json(QUERIES_PATH, default={\"base_queries\": [], \"country_bias\": [], \"site_bias\": []})
    cfg = load_yaml(CONFIG_PATH)
    filters = cfg.get(\"filters\", {})
    min_score = float(filters.get(\"min_score\", 2.5))
    per_q = int(filters.get(\"max_results_per_query\", 20))
    max_total = int(filters.get(\"max_total_results\", 120))

    search_strings = []
    for b in queries.get(\"base_queries\", []):
        # expand with country/site bias
        expanded = [b]
        for c in queries.get(\"country_bias\", []):
            expanded.append(f\"{b} {c}\")
        for s in queries.get(\"site_bias\", []):
            expanded.append(f'{b} site:*{s}')
        search_strings.extend(expanded)

    # dedupe and trim
    search_strings = list(dict.fromkeys(search_strings))
    print(f\"Total query variants: {len(search_strings)}\")

    all_hits = []
    seen_urls = set()
    for q in search_strings:
        if len(all_hits) >= max_total:
            break
        res = ddg_search(q, max_results=per_q)
        for r in res:
            url = r[\"url\"]
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            all_hits.append(r)
        time.sleep(0.5)  # be gentle

    print(f\"Fetched {len(all_hits)} result URLs before filtering.\")

    rows = []
    seen_domains_titles = set()

    for item in all_hits:
        url = item[\"url\"]
        html, final_url = safe_get(url)
        if not html:
            continue
        text, title = extract_main_text(html, final_url)
        if not text or len(text) < 500:
            continue

        score, funding_hits, gre_hits, ielts_hits, deadlines = score_item(text)
        if score < min_score:
            continue

        dom = domain_of(final_url)
        key = (dom, (title or \"\").strip().lower())
        if key in seen_domains_titles:
            continue
        seen_domains_titles.add(key)

        rows.append({
            \"title\": title or item.get(\"title\",\"(no title)\"),
            \"url\": final_url,
            \"domain\": dom,
            \"score\": round(score, 2),
            \"funding_signals\": \"; \".join(funding_hits),
            \"gre_waiver_signals\": \"; \".join(gre_hits),
            \"ielts_waiver_signals\": \"; \".join(ielts_hits),
            \"deadlines\": \"; \".join(deadlines),
            \"snippet\": item.get(\"snippet\",\"\"),
        })

    if not rows:
        print(\"No rows matched filters. Consider lowering min_score in config.yaml.\")
        # still write an empty CSV
    df = pd.DataFrame(rows, columns=[
        \"title\",\"url\",\"domain\",\"score\",\"funding_signals\",
        \"gre_waiver_signals\",\"ielts_waiver_signals\",\"deadlines\",\"snippet\"
    ]).sort_values([\"score\",\"domain\"], ascending=[False, True])

    out_csv = os.path.join(HERE, \"scholarships_latest.csv\" )
    df.to_csv(out_csv, index=False, quoting=csv.QUOTE_MINIMAL, encoding=\"utf-8\")
    print(f\"Wrote {out_csv} with {len(df)} rows.\")

    subj = cfg.get(\"email\", {}).get(\"subject\", \"Scholarship Digest\")
    from_name = cfg.get(\"email\", {}).get(\"from_name\", \"Scholarship Agent\")
    if os.getenv(\"EMAIL_USER\"):
        send_email(out_csv, len(df), subject=subj, from_name=from_name)

if __name__ == \"__main__\":
    main()
