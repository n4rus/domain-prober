#!/usr/bin/env python3
import argparse
import concurrent.futures
import itertools
import string
import requests
import os

# -------------------------------
# Configuration
# -------------------------------
MIN_CONTENT_LENGTH = 100  # Minimum characters to consider content valid
PARKED_PHRASES = ["this domain is parked", "buy this domain", "for sale", "domain parking"]
SAVE_INTERVAL = 20  # Save every 20 sites
CHECKPOINT_FILE = "progress.txt"
OUTPUT_FILE = "found_websites.html"
TESTED_DOMAINS_FILE = "tested_domains.txt"
DOMAIN_HTML_DIR = "saved_sites"  # Directory to store saved HTML files

# Ensure the output directory exists
os.makedirs(DOMAIN_HTML_DIR, exist_ok=True)

# -------------------------------
# Functions
# -------------------------------
def is_valid_content(content: str) -> bool:
    """Check if page content is long enough and does not contain parked domain phrases."""
    if len(content) < MIN_CONTENT_LENGTH:
        return False
    lower_content = content.lower()
    if any(phrase in lower_content for phrase in PARKED_PHRASES):
        return False
    return True

def probe_site(url: str, timeout: float = 5.0) -> bool:
    """Check if a URL is valid and contains real content."""
    print(f"Testing: {url}")  # Show domain being tested
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 200 and is_valid_content(response.text):
            save_html_page(url, response.text)  # Save the HTML page
            return True
    except requests.RequestException:
        pass
    return False

def save_html_page(url, content):
    """Save the HTML content of a successfully probed domain."""
    domain_name = url.replace("http://", "").replace("https://", "").replace("/", "_")
    filename = os.path.join(DOMAIN_HTML_DIR, f"{domain_name}.html")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

def save_checkpoint(last_processed: str):
    """Save the last processed domain to a file."""
    with open(CHECKPOINT_FILE, "w") as f:
        f.write(last_processed + "\n")

def load_checkpoint():
    """Load the last processed domain from the checkpoint file."""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            return f.read().strip()
    return None

def save_tested_domain(url):
    """Append tested domain to the tested_domains.txt file."""
    with open(TESTED_DOMAINS_FILE, "a") as f:
        f.write(url + "\n")

def generate_candidates_from_dictionary(dict_file: str):
    """Yield dictionary-based domain candidates, skipping empty lines."""
    with open(dict_file, "r") as f:
        words = [line.strip() for line in f if line.strip()]
    for word in words:
        yield f"http://{word}.com"

def generate_candidates_from_combinations(length: int):
    """Yield generated letter/number combinations as domain candidates."""
    chars = string.ascii_lowercase + string.digits
    for comb in itertools.product(chars, repeat=length):
        yield f"http://{''.join(comb)}.com"

def probe_domains(candidates, batch_size: int, max_workers: int = 10):
    """Probe domains in parallel batches and save results periodically."""
    found = set()
    last_processed = load_checkpoint()
    resume = last_processed is None  # Start processing if no checkpoint exists

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        batch = []
        for candidate in candidates:
            save_tested_domain(candidate)  # Save tested domain

            if not resume:
                if candidate == last_processed:
                    resume = True  # Resume when reaching last checkpoint
                continue

            batch.append(candidate)
            if len(batch) == batch_size:
                future_to_url = {executor.submit(probe_site, url): url for url in batch}
                for future in concurrent.futures.as_completed(future_to_url):
                    url = future_to_url[future]
                    if future.result():
                        found.add(url)

                batch = []  # Clear batch
                if len(found) >= SAVE_INTERVAL:
                    save_results(found)
                    save_checkpoint(candidate)  # Save progress
                    found.clear()

        if batch:
            future_to_url = {executor.submit(probe_site, url): url for url in batch}
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                if future.result():
                    found.add(url)

        if found:
            save_results(found)
            save_checkpoint(candidate)

def save_results(links):
    """Save results incrementally to the HTML file."""
    links = sorted(links)
    mode = "a" if os.path.exists(OUTPUT_FILE) else "w"
    with open(OUTPUT_FILE, mode) as f:
        if mode == "w":
            f.write("<html>\n<head>\n<title>Found Websites</title>\n</head>\n<body>\n")
            f.write("<h1>Probed Websites with Content</h1>\n<ul>\n")

        for link in links:
            f.write(f'  <li><a href="{link}" target="_blank">{link}</a></li>\n')

        if mode == "w":
            f.write("</ul>\n</body>\n</html>\n")

# -------------------------------
# Main Function
# -------------------------------
def main():
    parser = argparse.ArgumentParser(description="Probe websites and save real content.")
    parser.add_argument("--dict", type=str, required=True, help="Dictionary file.")
    parser.add_argument("--batch", type=int, default=5, help="Batch size.")
    parser.add_argument("--max-workers", type=int, default=10, help="Parallel workers.")
    parser.add_argument("--combo-length", type=int, default=5, help="Combination length.")

    args = parser.parse_args()

    print("Starting domain probing...\n")

    # Phase 1: Dictionary-based candidates
    print("Phase 1: Checking dictionary-based domains...")
    dict_candidates = generate_candidates_from_dictionary(args.dict)
    probe_domains(dict_candidates, args.batch, args.max_workers)

    # Phase 2: Generated letter/number combinations
    print("Phase 2: Checking generated domains...")
    combo_candidates = generate_candidates_from_combinations(args.combo_length)
    probe_domains(combo_candidates, args.batch, args.max_workers)

    print(f"\nResults saved in {OUTPUT_FILE}.")
    print(f"All tested domains are in {TESTED_DOMAINS_FILE}.")
    print(f"Resumable progress stored in {CHECKPOINT_FILE}.")
    print(f"HTML pages saved in the '{DOMAIN_HTML_DIR}' directory.")

if __name__ == '__main__':
    main()

