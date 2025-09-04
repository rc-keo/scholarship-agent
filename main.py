import os
import smtplib
import yaml
import json
from email.mime.text import MIMEText
from duckduckgo_search import DDGS


def load_config():
    """Load configuration from config.yaml"""
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)


def load_queries():
    """Load queries from queries.json"""
    with open("queries.json", "r") as f:
        return json.load(f)


def search_duckduckgo(query, max_results=5):
    """DuckDuckGo search via duckduckgo_search package"""
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", "")
            })
    return results


def format_results(query, results):
    """Format search results into readable text"""
    if not results:
        return f"No results found for: {query}\n\n"
    text = f"Results for: {query}\n"
    for r in results:
        text += f"- {r['title']}\n  {r['url']}\n  {r['snippet']}\n\n"
    return text


def send_email(subject, body, from_email, to_email, password):
    """Send email using Gmail SMTP"""
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(from_email, password)
        server.sendmail(from_email, [to_email], msg.as_string())


def main():
    config = load_config()
    queries = load_queries()

    all_results = ""
    for q in queries.get("queries", []):
        results = search_duckduckgo(q, max_results=config.get("max_results", 5))
        all_results += format_results(q, results)

    from_email = os.environ["EMAIL_USER"]
    password = os.environ["EMAIL_PASS"]
    to_email = os.environ["TO_EMAIL"]

    send_email("Scholarship Search Results", all_results, from_email, to_email, password)


if __name__ == "__main__":
    main()
