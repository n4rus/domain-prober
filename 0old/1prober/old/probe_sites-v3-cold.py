#!/usr/bin/env python3
import argparse
import concurrent.futures
import itertools
import json
import os
import requests
import string

# -------------------------------
# Configuration
# -------------------------------
MIN_CONTENT_LENGTH = 100  # Minimum characters to consider content valid
PARKED_PHRASES = [
    "this domain is parked",
    "buy this domain",
    "for sale",
    "domain parking",
]
SAVE_INTERVAL = 20  # Update HTML file every 20 new valid domains
PROGRESS_FILE = "progress.json"
OUTPUT_FILE = "found_websites.html"

# -------------------------------
# Checkpoint Functions (using JSON)
# -------------------------------
def save_checkpoint(phase, last_candidate):
    """Save the current phase and last processed candidate to a JSON checkpoint."""
    data = {"phase": phase, "last_candidate": last_candidate}
    with open(PROGRESS_FILE, "w") as f:
        json.dump(data, f)

def load_checkpoint():
    """Load checkpoint data from PROGRESS_FILE if it exists."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return None

# -------------------------------
# Content Validation & Probing
# -------------------------------
def is_valid_content(content: str) -> bool:
    """Return True if content is long enough and does not include parked phrases."""
    if len(content) < MIN_CONTENT_LENGTH:
        return False
    lower = content.lower()
    return not any(phrase in lower for phrase in PARKED_PHRASES)

def probe_site(url: str, timeout: float = 5.0) -> bool:
    """Print the URL being tested and return True if it responds with valid content."""
    print(f"Testing: {url}")
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 200 and is_valid_content(response.text):
            return True
    except (requests.RequestException, UnicodeError):
        pass
    return False

# -------------------------------
# Candidate Generation
# -------------------------------
def generate_candidates_from_dictionary(dict_file: str):
    """Yield candidate domains from the dictionary file (one word per line), skipping empty or overly long words."""
    with open(dict_file, "r") as f:
        for line in f:
            word = line.strip()
            if word and len(word) <= 63:  # valid domain label length
                yield f"http://{word}.com"

def generate_candidates_from_combinations(length: int):
    """Yield candidate domains by generating all combinations of letters and digits of the given length."""
    chars = string.ascii_lowercase + string.digits
    for comb in itertools.product(chars, repeat=length):
        yield f"http://{''.join(comb)}.com"

# -------------------------------
# HTML Output Functions
# -------------------------------
def load_found_domains() -> set:
    """If the output HTML file exists, parse it to recover already-found domains."""
    found = set()
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r") as f:
            for line in f:
                if '<li><a href="' in line:
                    start = line.find('<li><a href="') + len('<li><a href="')
                    end = line.find('"', start)
                    domain = line[start:end]
                    found.add(domain)
    return found

def save_results(found: set):
    """Overwrite the HTML file with all valid domains (sorted alphabetically) as clickable links."""
    sorted_domains = sorted(found, key=lambda x: x.lower())
    with open(OUTPUT_FILE, "w") as f:
        f.write("<html>\n<head>\n<title>Found Websites</title>\n</head>\n<body>\n")
        f.write("<h1>Probed Websites with Valid Content</h1>\n<ul>\n")
        for domain in sorted_domains:
            f.write(f'  <li><a href="{domain}" target="_blank">{domain}</a></li>\n')
        f.write("</ul>\n</body>\n</html>\n")
    print(f"Saved {len(sorted_domains)} valid domains to {OUTPUT_FILE}")

# -------------------------------
# Domain Probing with Resume Support
# -------------------------------
def probe_domains(candidates, phase: str, batch_size: int, max_workers: int, found: set) -> set:
    """
    Probe candidate domains in batches using parallel scanning.
    If a checkpoint exists for the current phase, resume from the last candidate processed.
    Updates the HTML file every SAVE_INTERVAL new valid domains.
    """
    checkpoint = load_checkpoint()
    resume = True
    last_candidate = None
    if checkpoint and checkpoint.get("phase") == phase and checkpoint.get("last_candidate"):
        last_candidate = checkpoint.get("last_candidate")
        resume = False

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        batch = []
        for candidate in candidates:
            # If resuming, skip candidates until we reach the last processed one.
            if not resume:
                if candidate == last_candidate:
                    resume = True
                continue

            batch.append(candidate)
            if len(batch) == batch_size:
                future_to_url = {executor.submit(probe_site, url): url for url in batch}
                for future in concurrent.futures.as_completed(future_to_url):
                    url = future_to_url[future]
                    if future.result():
                        found.add(url)
                # Save checkpoint using the last candidate of the batch.
                save_checkpoint(phase, candidate)
                batch = []
                if len(found) % SAVE_INTERVAL == 0:
                    save_results(found)
        if batch:
            future_to_url = {executor.submit(probe_site, url): url for url in batch}
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                if future.result():
                    found.add(url)
            save_checkpoint(phase, candidate)
    save_results(found)
    return found

# -------------------------------
# Main Function
# -------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Probe websites and generate one HTML file listing valid domains (alphabetically sorted)."
    )
    parser.add_argument("--dict", type=str, required=True, help="Path to dictionary file (one word per line).")
    parser.add_argument("--batch", type=int, default=5, help="Batch size for parallel probing.")
    parser.add_argument("--max-workers", type=int, default=10, help="Number of parallel workers.")
    parser.add_argument("--combo-length", type=int, default=5, help="Length for combination-based domain generation.")
    args = parser.parse_args()

    # Load any previously found valid domains.
    found = load_found_domains()

    print("Starting domain probing...\n")

    # Phase 1: Process dictionary-based candidates first.
    print("Phase 1: Probing dictionary-based candidates...")
    dict_candidates = generate_candidates_from_dictionary(args.dict)
    found = probe_domains(dict_candidates, "dictionary", args.batch, args.max_workers, found)

    # Once dictionary phase is complete, update checkpoint to mark the start of combination phase.
    save_checkpoint("combination", None)

    # Phase 2: Process combination-based candidates.
    print("Phase 2: Probing combination-based candidates...")
    combo_candidates = generate_candidates_from_combinations(args.combo_length)
    found = probe_domains(combo_candidates, "combination", args.batch, args.max_workers, found)

    print(f"\nCompleted probing. Total valid domains: {len(found)}")
    print(f"Results saved in {OUTPUT_FILE}")

if __name__ == '__main__':
    main()

