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
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/91.0.4472.124 Safari/537.36")
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
    """Load checkpoint data if it exists."""
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
    """Append url to the empty domains file if not already recorded."""
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
    """Test the URL (using a spoofed User-Agent) and return True if valid content is found."""
    print(f"Testing: {url}")
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        if response.status_code == 200 and is_valid_content(response.text):
            return True
    except (requests.RequestException, UnicodeError):
        pass
    return False

# -------------------------------
# Candidate Generation (with Skip Filter)
# -------------------------------
def generate_candidates_from_dictionary(dict_file: str, tlds: list, skip: set):
    """
    Yield candidate domains from the dictionary file (one word per line),
    using the specified TLDs and skipping those in the skip set.
    """
    with open(dict_file, "r") as f:
        for line in f:
            word = line.strip()
            if word and len(word) <= 63:
                for tld in tlds:
                    candidate = f"http://{word}.{tld}"
                    if candidate not in skip:
                        yield candidate

def generate_candidates_from_combinations(length: int, tlds: list, skip: set):
    """
    Yield candidate domains by generating all combinations of letters and digits
    of the given length, using the specified TLDs and skipping those in the skip set.
    """
    chars = string.ascii_lowercase + string.digits
    for comb in itertools.product(chars, repeat=length):
        for tld in tlds:
            candidate = f"http://{''.join(comb)}.{tld}"
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
    as clickable links with enumeration and a floating search bar.
    """
    sorted_domains = sorted(found, key=lambda x: x.lower())
    with open(OUTPUT_FILE, "w") as f:
        f.write("""<html>
<head>
  <title>Found Websites</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; }
    #searchBar { position: fixed; top: 20px; right: 20px; width: 200px; }
    ul { margin-top: 80px; }
    li { margin-bottom: 5px; }
  </style>
  <script>
    function searchDomains() {
      var input = document.getElementById('searchInput');
      var filter = input.value.toLowerCase();
      var ul = document.getElementById('domainList');
      var li = ul.getElementsByTagName('li');
      for (var i = 0; i < li.length; i++) {
        var a = li[i].getElementsByTagName('a')[0];
        if (a.innerHTML.toLowerCase().indexOf(filter) > -1) {
          li[i].style.display = '';
        } else {
          li[i].style.display = 'none';
        }
      }
    }
  </script>
</head>
<body>
  <div id='searchBar'>
    <input type='text' id='searchInput' onkeyup='searchDomains()' placeholder='Search domains...'>
  </div>
  <h1>Probed Websites with Valid Content</h1>
  <ul id='domainList'>
""")
        for i, domain in enumerate(sorted_domains, 1):
            f.write(f'    <li><a href="{domain}" target="_blank">[{i}] {domain}</a></li>\n')
        f.write("""  </ul>
</body>
</html>""")
    print(f"Updated HTML file with {len(sorted_domains)} valid domains.")

# -------------------------------
# Domain Probing with Resume & Empty Skip
# -------------------------------
def probe_domains(candidates, phase: str, batch_size: int, max_workers: int,
                  found: set, empty_set: set) -> set:
    """
    Probe candidate domains in batches with parallel scanning.
    Uses checkpoint data to resume processing and skips candidates in empty_set.
    Updates the HTML file each time a valid domain is found.
    """
    checkpoint = load_checkpoint()
    resume = True
    last_candidate = None
    if checkpoint and checkpoint.get("phase") == phase and checkpoint.get("last_candidate") is not None:
        last_candidate = checkpoint.get("last_candidate")
        resume = False  # We need to resume until we find the checkpoint candidate.
    skip_count = 0
    max_skip = 1000  # If we skip too many without finding the checkpoint, resume anyway.
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        batch = []
        for candidate in candidates:
            if not resume:
                if candidate == last_candidate:
                    resume = True
                    # Skip the checkpoint candidate (assumed processed already).
                    continue
                else:
                    skip_count += 1
                    if skip_count > max_skip:
                        print("Checkpoint candidate not found within threshold, resuming from current candidate.")
                        resume = True
                    else:
                        continue
            batch.append(candidate)
            if len(batch) == batch_size:
                future_to_url = {executor.submit(probe_site, url): url for url in batch}
                for future in concurrent.futures.as_completed(future_to_url):
                    url = future_to_url[future]
                    if future.result():
                        found.add(url)
                        save_results(found)
                    else:
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
    parser.add_argument("--tlds", type=str, default=".com", help="Comma-separated list of TLDs (e.g., .com,.net,.org).")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint.")
    args = parser.parse_args()
    
    # If not resuming, remove any existing checkpoint.
    if not args.resume and os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
    
    tlds = [t.strip() for t in args.tlds.split(",") if t.strip()]
    found = load_found_domains()
    empty_set = load_empty_domains()
    
    print("Starting domain probing...\n")
    
    # Phase 1: Process dictionary-based candidates.
    print("Phase 1: Probing dictionary-based candidates...")
    dict_candidates = generate_candidates_from_dictionary(args.dict, tlds, empty_set)
    found = probe_domains(dict_candidates, "dictionary", args.batch, args.max_workers, found, empty_set)
    
    # Mark checkpoint to start combination phase.
    save_checkpoint("combination", None)
    
    # Phase 2: Process combination-based candidates.
    print("Phase 2: Probing combination-based candidates...")
    combo_candidates = generate_candidates_from_combinations(args.combo_length, tlds, empty_set)
    found = probe_domains(combo_candidates, "combination", args.batch, args.max_workers, found, empty_set)
    
    print(f"\nCompleted probing. Total valid domains: {len(found)}")
    print(f"Results saved in {OUTPUT_FILE}")
    print(f"Empty/invalid domains recorded in {EMPTY_DOMAINS_FILE}")

if __name__ == '__main__':
    main()

