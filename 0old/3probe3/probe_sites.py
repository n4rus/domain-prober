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
# Files for progress, HTML output, and empty domains
PROGRESS_FILE = "progress.json"
OUTPUT_FILE = "found_websites.html"
EMPTY_DOMAINS_FILE = "empty_domains.txt"

# -------------------------------
# Checkpoint Functions (JSON)
# -------------------------------
def save_checkpoint(phase, last_candidate):
    """Save current phase and last processed candidate."""
    data = {"phase": phase, "last_candidate": last_candidate}
    with open(PROGRESS_FILE, "w") as f:
        json.dump(data, f)

def load_checkpoint():
    """Load checkpoint data if exists."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return None

# -------------------------------
# Empty Domains Handling
# -------------------------------
def load_empty_domains() -> set:
    """Load previously probed empty domains from file."""
    empty = set()
    if os.path.exists(EMPTY_DOMAINS_FILE):
        with open(EMPTY_DOMAINS_FILE, "r") as f:
            for line in f:
                candidate = line.strip()
                if candidate:
                    empty.add(candidate)
    return empty

def record_empty(url: str, empty_set: set):
    """If url not already recorded, append it to the empty domains file and update the set."""
    if url not in empty_set:
        with open(EMPTY_DOMAINS_FILE, "a") as f:
            f.write(url + "\n")
        empty_set.add(url)

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
    """Test the URL, print it, and return True if valid content is found."""
    print(f"Testing: {url}")
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 200 and is_valid_content(response.text):
            return True
    except (requests.RequestException, UnicodeError):
        pass
    return False

# -------------------------------
# Candidate Generation (with Skip Filter)
# -------------------------------
def generate_candidates_from_dictionary(dict_file: str, skip: set):
    """
    Yield candidate domains from the dictionary file (one word per line),
    skipping empty lines, overly long words, and those already in the skip set.
    """
    with open(dict_file, "r") as f:
        for line in f:
            word = line.strip()
            if word and len(word) <= 63:
                candidate = f"http://{word}.com"
                if candidate not in skip:
                    yield candidate

def generate_candidates_from_combinations(length: int, skip: set):
    """
    Yield candidate domains by generating all combinations of letters and digits
    of the given length, skipping those in the skip set.
    """
    chars = string.ascii_lowercase + string.digits
    for comb in itertools.product(chars, repeat=length):
        candidate = f"http://{''.join(comb)}.com"
        if candidate not in skip:
            yield candidate

# -------------------------------
# HTML Output Functions
# -------------------------------
def load_found_domains() -> set:
    """
    If the HTML output exists, parse it to recover already-found valid domains.
    """
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
    """
    Overwrite the HTML file with all valid domains (sorted alphabetically)
    as clickable links.
    """
    sorted_domains = sorted(found, key=lambda x: x.lower())
    with open(OUTPUT_FILE, "w") as f:
        f.write("<html>\n<head>\n<title>Found Websites</title>\n</head>\n<body>\n")
        f.write("<h1>Probed Websites with Valid Content</h1>\n<ul>\n")
        for domain in sorted_domains:
            f.write(f'  <li><a href="{domain}" target="_blank">{domain}</a></li>\n')
        f.write("</ul>\n</body>\n</html>\n")
    print(f"Updated HTML file with {len(sorted_domains)} valid domains.")

# -------------------------------
# Domain Probing with Resume & Empty Skip
# -------------------------------
def probe_domains(candidates, phase: str, batch_size: int, max_workers: int,
                  found: set, empty_set: set) -> set:
    """
    Probe candidate domains in batches with parallel scanning.
    Uses checkpoint data to resume processing and skips candidates in empty_set.
    Updates the HTML file each time a valid (non‑empty) domain is found.
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
            # Resume: skip until reaching last processed candidate.
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
                        # Valid domain: update found set and update HTML file immediately.
                        found.add(url)
                        save_results(found)
                    else:
                        # Record empty/invalid domains.
                        record_empty(url, empty_set)
                save_checkpoint(phase, url)
                batch = []
        if batch:
            future_to_url = {executor.submit(probe_site, url): url for url in batch}
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                if future.result():
                    found.add(url)
                    save_results(found)
                else:
                    record_empty(url, empty_set)
            save_checkpoint(phase, url)
    # Final update of the HTML file.
    save_results(found)
    return found

# -------------------------------
# Main Function
# -------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Probe websites and generate one HTML file listing valid domains (alphabetically sorted) as links. "
                    "Domains that return empty are recorded for skipping on future runs."
    )
    parser.add_argument("--dict", type=str, required=True, help="Path to dictionary file (one word per line).")
    parser.add_argument("--batch", type=int, default=5, help="Batch size for parallel probing.")
    parser.add_argument("--max-workers", type=int, default=10, help="Number of parallel workers.")
    parser.add_argument("--combo-length", type=int, default=5, help="Length for combination-based domain generation.")
    args = parser.parse_args()

    # Load found valid domains and already empty (invalid) domains.
    found = load_found_domains()
    empty_set = load_empty_domains()

    print("Starting domain probing...\n")

    # Phase 1: Process dictionary-based candidates.
    print("Phase 1: Probing dictionary-based candidates...")
    dict_candidates = generate_candidates_from_dictionary(args.dict, empty_set)
    found = probe_domains(dict_candidates, "dictionary", args.batch, args.max_workers, found, empty_set)

    # Mark checkpoint to start combination phase.
    save_checkpoint("combination", None)

    # Phase 2: Process combination-based candidates.
    print("Phase 2: Probing combination-based candidates...")
    combo_candidates = generate_candidates_from_combinations(args.combo_length, empty_set)
    found = probe_domains(combo_candidates, "combination", args.batch, args.max_workers, found, empty_set)

    print(f"\nCompleted probing. Total valid domains: {len(found)}")
    print(f"Results saved in {OUTPUT_FILE}")
    print(f"Empty/invalid domains recorded in {EMPTY_DOMAINS_FILE}")

if __name__ == '__main__':
    main()

