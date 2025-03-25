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
PARKED_PHRASES = [
    "this domain is parked",
    "buy this domain",
    "for sale",
    "domain parking",
]
SAVE_INTERVAL = 20  # Update the HTML file every 20 new valid domains
CHECKPOINT_FILE = "progress.txt"
OUTPUT_FILE = "found_websites.html"

# -------------------------------
# Content Validation & Probing
# -------------------------------
def is_valid_content(content: str) -> bool:
    """Return True if content is long enough and does not contain parked phrases."""
    if len(content) < MIN_CONTENT_LENGTH:
        return False
    lower_content = content.lower()
    return not any(phrase in lower_content for phrase in PARKED_PHRASES)

def probe_site(url: str, timeout: float = 5.0) -> bool:
    """Test the URL, print it, and return True if valid content is found."""
    print(f"Testing: {url}")
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 200 and is_valid_content(response.text):
            return True
    except (requests.RequestException, UnicodeError):
        # Catch network-related errors and UnicodeError (invalid domain label)
        pass
    return False

# -------------------------------
# Checkpoint Functions
# -------------------------------
def save_checkpoint(last_processed: str):
    """Save the last processed domain to the checkpoint file."""
    with open(CHECKPOINT_FILE, "w") as f:
        f.write(last_processed + "\n")

def load_checkpoint():
    """Load the last processed domain from the checkpoint file, if it exists."""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            return f.read().strip()
    return None

# -------------------------------
# Candidate Generation
# -------------------------------
def generate_candidates_from_dictionary(dict_file: str):
    """Yield candidate domains from a dictionary file, skipping empty or too long words."""
    with open(dict_file, "r") as f:
        for line in f:
            word = line.strip()
            if word and len(word) <= 63:
                yield f"http://{word}.com"

def generate_candidates_from_combinations(length: int):
    """Yield candidate domains by generating all combinations of letters and digits."""
    chars = string.ascii_lowercase + string.digits
    for comb in itertools.product(chars, repeat=length):
        yield f"http://{''.join(comb)}.com"

# -------------------------------
# HTML Output
# -------------------------------
def load_found_domains() -> set:
    """If OUTPUT_FILE exists, parse it to recover already-found domains."""
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
    """Overwrite the HTML file with all valid domains sorted alphanumerically."""
    sorted_domains = sorted(found, key=lambda x: x.lower())
    with open(OUTPUT_FILE, "w") as f:
        f.write("<html>\n<head>\n<title>Found Websites</title>\n</head>\n<body>\n")
        f.write("<h1>Probed Websites with Valid Content</h1>\n<ul>\n")
        for domain in sorted_domains:
            f.write(f'  <li><a href="{domain}" target="_blank">{domain}</a></li>\n')
        f.write("</ul>\n</body>\n</html>\n")
    print(f"Saved {len(sorted_domains)} valid domains to {OUTPUT_FILE}")

# -------------------------------
# Domain Probing
# -------------------------------
def probe_domains(candidates, batch_size: int, max_workers: int = 10, found: set = None) -> set:
    """Probe candidate domains in batches with parallel scanning, updating the HTML file periodically."""
    if found is None:
        found = set()
    last_processed = load_checkpoint()
    resume = last_processed is None  # If no checkpoint, process all

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        batch = []
        for candidate in candidates:
            # Resume logic: skip until we reach the last-processed candidate.
            if not resume:
                if candidate == last_processed:
                    resume = True
                continue

            batch.append(candidate)
            if len(batch) == batch_size:
                future_to_url = {executor.submit(probe_site, url): url for url in batch}
                for future in concurrent.futures.as_completed(future_to_url):
                    url = future_to_url[future]
                    if future.result():
                        found.add(url)
                batch = []  # Clear the batch

                # Update HTML file every SAVE_INTERVAL new valid domains
                if len(found) % SAVE_INTERVAL == 0:
                    save_results(found)
                    save_checkpoint(url)
        # Process any remaining candidates in the batch
        if batch:
            future_to_url = {executor.submit(probe_site, url): url for url in batch}
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                if future.result():
                    found.add(url)
            save_checkpoint(url)
    # Final update of the HTML file
    save_results(found)
    return found

# -------------------------------
# Main Function
# -------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Probe websites and generate one HTML file listing valid domains."
    )
    parser.add_argument("--dict", type=str, required=True, help="Path to dictionary file (one word per line).")
    parser.add_argument("--batch", type=int, default=5, help="Batch size for parallel probing.")
    parser.add_argument("--max-workers", type=int, default=10, help="Number of parallel workers.")
    parser.add_argument("--combo-length", type=int, default=5, help="Length for combination-based domain generation.")

    args = parser.parse_args()

    # Load any previously found valid domains from the HTML file.
    found = load_found_domains()

    print("Starting domain probing...\n")

    # Phase 1: Dictionary-based domains
    print("Phase 1: Probing dictionary-based candidates...")
    dict_candidates = generate_candidates_from_dictionary(args.dict)
    found = probe_domains(dict_candidates, args.batch, args.max_workers, found)

    # Phase 2: Generated combination domains
    print("Phase 2: Probing generated combination candidates...")
    combo_candidates = generate_candidates_from_combinations(args.combo_length)
    found = probe_domains(combo_candidates, args.batch, args.max_workers, found)

    print(f"\nCompleted probing. Total valid domains: {len(found)}")
    print(f"Results saved in {OUTPUT_FILE}.")

if __name__ == '__main__':
    main()

