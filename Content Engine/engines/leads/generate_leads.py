import csv
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from ddgs import DDGS


ROOT = Path(__file__).resolve().parents[2]

BLOCKED_DOMAINS = {
    "comparis.ch",
    "onedoc.ch",
    "local.ch",
    "search.ch",
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "youtube.com",
}

DEFAULT_EXCLUDED_TERMS = {
    "stellenbörse",
    "stellenboerse",
    "job",
    "jobs",
    "karriere",
    "shop",
    "lieferant",
}

EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)

PHONE_RE = re.compile(
    r"(?:\+41|0041|0)[\s()./-]*(?:\d[\s()./-]*){8,10}"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def clean_domain(url):
    domain = urlparse(url).netloc.lower()

    if domain.startswith("www."):
        domain = domain[4:]

    return domain


def blocked(domain):
    return any(
        domain == item or domain.endswith("." + item)
        for item in BLOCKED_DOMAINS
    )


def extract_contact(url):
    email = ""
    phone = ""

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=10,
            allow_redirects=True,
        )

        if "text/html" not in response.headers.get(
            "Content-Type",
            "",
        ):
            return email, phone

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        text = soup.get_text(
            " ",
            strip=True,
        )

        emails = EMAIL_RE.findall(text)
        phones = PHONE_RE.findall(text)

        if emails:
            email = emails[0]

        if phones:
            phone = phones[0].strip()

        if not email or not phone:
            for link in soup.find_all("a", href=True):
                label = (
                    link.get_text(" ", strip=True)
                    + " "
                    + link["href"]
                ).lower()

                if not any(
                    word in label
                    for word in [
                        "kontakt",
                        "contact",
                        "impressum",
                    ]
                ):
                    continue

                contact_url = urljoin(
                    response.url,
                    link["href"],
                )

                try:
                    contact_response = requests.get(
                        contact_url,
                        headers=HEADERS,
                        timeout=10,
                    )

                    contact_text = BeautifulSoup(
                        contact_response.text,
                        "html.parser",
                    ).get_text(
                        " ",
                        strip=True,
                    )

                    if not email:
                        found = EMAIL_RE.findall(
                            contact_text
                        )

                        if found:
                            email = found[0]

                    if not phone:
                        found = PHONE_RE.findall(
                            contact_text
                        )

                        if found:
                            phone = found[0].strip()

                except Exception:
                    pass

                break

    except Exception:
        pass

    return email, phone


def generate(job_id):
    job_file = ROOT / "core" / "jobs" / f"{job_id}.json"

    if not job_file.exists():
        raise FileNotFoundError(
            f"Job nicht gefunden: {job_file}"
        )

    job = json.loads(
        job_file.read_text(
            encoding="utf-8-sig"
        )
    )

    target = int(
        job.get("quantity", 5)
    )

    if target < 1:
        raise ValueError(
            "quantity muss mindestens 1 sein."
        )

    query = job.get("query")

    if not query:
        query = (
            f'{job["company"]} Schweiz Kontakt'
        )

    region = job.get(
        "region",
        "ch-de",
    )

    required_terms = {
        str(term).lower()
        for term in job.get(
            "required_terms",
            [],
        )
    }

    excluded_terms = (
        DEFAULT_EXCLUDED_TERMS
        | {
            str(term).lower()
            for term in job.get(
                "excluded_terms",
                [],
            )
        }
    )

    output_dir = (
        ROOT
        / "exports"
        / job_id
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    rows = []
    seen_domains = set()

    max_results = min(
        200,
        max(
            40,
            target * 10,
        ),
    )

    results = DDGS().text(
        query,
        region=region,
        safesearch="moderate",
        max_results=max_results,
    )

    for result in results:
        if len(rows) >= target:
            break

        url = (
            result.get("href")
            or result.get("url")
        )

        title = result.get(
            "title",
            "",
        ).strip()

        title_l = title.lower()

        if not url:
            continue

        if required_terms and not any(
            term in title_l
            for term in required_terms
        ):
            continue

        if any(
            term in title_l
            for term in excluded_terms
        ):
            continue

        domain = clean_domain(url)

        if (
            not domain
            or domain in seen_domains
            or blocked(domain)
        ):
            continue

        seen_domains.add(domain)

        email, phone = extract_contact(url)

        if not email and not phone:
            continue

        rows.append({
            "company": title,
            "website": url,
            "email": email,
            "phone": phone,
            "domain": domain,
            "source_query": query,
        })

    output = output_dir / "leads.csv"

    with output.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "company",
                "website",
                "email",
                "phone",
                "domain",
                "source_query",
            ],
        )

        writer.writeheader()
        writer.writerows(rows)

    return output, rows


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("LEAD_ENGINE_DYNAMIC_READY")
        print(
            "USAGE: python generate_leads.py JOB-XXXXXXXX"
        )
        sys.exit(0)

    output, rows = generate(
        sys.argv[1]
    )

    print(
        f"LEAD_ENGINE_READY: {len(rows)} Leads"
    )
    print(
        f"OUTPUT: {output}"
    )
