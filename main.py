import os
import smtplib
import yaml
import json
import itertools
from email.mime.text import MIMEText
from duckduckgo_search import DDGS


def load_config():
    """Load configuration from config.yaml"""
    try:
        with open("config.yaml", "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("⚠️ config.yaml not found, using defaults")
        return {"max_results": 5}


def load_queries():
    """Load and expand queries from queries.json"""
    try:
        with open("queries.json", "r") as f:
            data = json.load(f)

        base_queries = data.get("base_queries", [])
        country_bias = data.get("country_bias", [])
        site_bias = data.get("site_bias", [])

        expanded_queries = []

        # Combine base + country + site biases
        for b in base_queries:
            for combo in itertools.product(
                country_bias or [""],
                site_bias or [""]
            ):
                c, s = combo
                query = " ".join([b, c, s]).strip()
                expanded_queries.append(query)

        return expanded_queries

    except FileNotFoundError:
        print("⚠️ queries.json not found, no queries to run")
        return []


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
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(from_email, password)
            server.sendmail(from_email, [to_email], msg.as_string())
        print("✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Error sending email: {e}")


def main():
    config = load_config()
    queries = load_queries()

    all_results = ""
    for q in queries:
        results = search_duckduckgo(q, max_results=config.get("max_results", 5))
        all_results += format_results(q, results)

    from_email = os.environ.get("EMAIL_USER")
    password = os.environ.get("EMAIL_PASS")
    to_email = os.environ.get("TO_EMAIL")

    if not from_email or not password or not to_email:
        print("❌ Missing email credentials (EMAIL_USER, EMAIL_PASS, TO_EMAIL). Please set them in GitHub Secrets.")
        return

    send_email("Scholarship Search Results", all_results, from_email, to_email, password)


if __name__ == "__main__":
    main()
