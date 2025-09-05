import os
import smtplib
import yaml
import json
from datetime import datetime
from email.mime.text import MIMEText
from duckduckgo_search import DDGS


def load_config():
    """Load configuration from config.yaml"""
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_queries():
    """Load queries from queries.json"""
    with open("queries.json", "r", encoding="utf-8") as f:
        return json.load(f)


def search_duckduckgo(query, max_results=5):
    """DuckDuckGo search via duckduckgo_search package"""
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append({
                "program": r.get("title", "").strip(),
                "university": "",  # placeholder, parsing later
                "funding": "Scholarship/Assistantship (check link)",
                "deadline": "Check webpage",
                "link": r.get("href", ""),
                "snippet": r.get("body", "").strip()
            })
    return results


def save_results(all_results):
    """Save results into results.json"""
    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)


def create_email_body(all_results):
    """Create readable email body text from results"""
    if not all_results:
        return "No open MSc scholarships or assistantships were found at this time."

    body_lines = []
    for r in all_results:
        body_lines.append(
            f"🎓 {r.get('program','')} \n"
            f"   Funding: {r.get('funding','')}\n"
            f"   Deadline: {r.get('deadline','')}\n"
            f"   Link: {r.get('link','')}\n"
            f"   {r.get('snippet','')}\n"
        )
    return "\n\n".join(body_lines)


def send_email(subject, body, sender, password, recipient, from_name="Scholarship Agent"):
    """Send email using Gmail SMTP"""
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{sender}>"
    msg["To"] = recipient

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, [recipient], msg.as_string())


def main():
    config = load_config()
    queries = load_queries()

    max_results_per_query = config.get("filters", {}).get("max_results_per_query", 5)
    max_total_results = config.get("filters", {}).get("max_total_results", 100)

    all_results = []
    for q in queries.get("base_queries", []):
        results = search_duckduckgo(q, max_results=max_results_per_query)
        all_results.extend(results)
        if len(all_results) >= max_total_results:
            break

    # Save results to file
    save_results(all_results)

    # Create email body
    email_body = create_email_body(all_results)

    # Send email
    email_cfg = config.get("email", {})
    send_email(
        subject=email_cfg.get("subject", "Scholarship Search Results"),
        body=email_body,
        sender=email_cfg.get("sender"),
        password=email_cfg.get("password"),
        recipient=email_cfg.get("recipient"),
        from_name=email_cfg.get("from_name", "Scholarship Agent"),
    )

    print(f"✅ Completed: {len(all_results)} results found and emailed.")


if __name__ == "__main__":
    main()
