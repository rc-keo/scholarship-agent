import os
import smtplib
import yaml
import json
from datetime import datetime
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
                "program": r.get("title", "").strip(),
                "university": "",  # can parse later
                "funding": "Scholarship/Assistantship (check link)",  # placeholder
                "deadline": "Check webpage",  # placeholder
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
        body = "No open MSc scholarships or assistantships were found at this time."
    else:
        body_lines = []
        for r in all_results:
            body_lines.append(
                f"🎓 {r.get('program','')} \n"
                f"   Funding: {r.get('funding','')}\n"
                f"   Deadline: {r.get('deadline','')}\n"
                f"   Link: {r.get('link','')}\n"
                f"   {r.get('snippet','')}\n"
            )
        body = "\n\n".join(body_lines)

    # Save email body to file for GitHub Action
    with open("email_body.txt", "w", encoding="utf-8") as f:
        f.write(f"Scholarship Search Results ({datetime.today().date()})\n\n")
        f.write(body)


def main():
    config = load_config()
    queries = load_queries()

    all_results = []
    for q in queries.get("base_queries", []):
        results = search_duckduckgo(q, max_results=config.get("max_results", 5))
        all_results.extend(results)

    # Save raw results
    save_results(all_results)

    # Generate email body file
    create_email_body(all_results)


if __name__ == "__main__":
    main()
