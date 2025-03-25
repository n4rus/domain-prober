import argparse
import os
import requests
import itertools
import string
import time

def load_empty_domains():
    """Load previously probed empty domains and return them as a set."""
    empty_domains = set()
    last_checked = None
    if os.path.exists("empty_domains.txt"):
        with open("empty_domains.txt", "r") as f:
            for line in f:
                domain = line.strip()
                if domain:
                    empty_domains.add(domain)
                    last_checked = domain  # Track last checked domain
    return empty_domains, last_checked

def record_empty_domain(url):
    """Record a domain as empty if it returns no useful content."""
    with open("empty_domains.txt", "a") as f:
        f.write(url + "\n")

def probe_site(url):
    """Check if a site contains valid content."""
    print(f"Testing: {url}")
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200 and len(response.text) > 100:
            return True
    except requests.RequestException:
        pass
    return False

def generate_candidates_from_dictionary(dict_file, tlds, empty_set, last_checked):
    """Generate domain candidates from a dictionary file, resuming from last_checked."""
    resume = last_checked is None
    with open(dict_file, "r") as f:
        for word in f:
            word = word.strip()
            if word and len(word) <= 63:
                for tld in tlds:
                    domain = f"http://{word}.{tld}"
                    if domain in empty_set:
                        if domain == last_checked:
                            resume = True  # Resume when last_checked is reached
                        continue
                    if resume:
                        yield domain
                        time.sleep(0.1)  # Prevent CPU overload

def generate_candidates_from_combinations(length, tlds, empty_set, last_checked):
    """Generate domain candidates from letter-digit combinations, resuming from last_checked."""
    chars = string.ascii_lowercase + string.digits
    resume = last_checked is None
    for comb in itertools.product(chars, repeat=length):
        for tld in tlds:
            domain = f"http://{''.join(comb)}.{tld}"
            if domain in empty_set:
                if domain == last_checked:
                    resume = True
                continue
            if resume:
                yield domain
                time.sleep(0.1)  # Prevent CPU overload

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dict", type=str, required=True, help="Path to dictionary file.")
    parser.add_argument("--combo-length", type=int, default=5, help="Length of generated domain names.")
    parser.add_argument("--tlds", type=str, default=".com", help="Comma-separated list of TLDs.")
    args = parser.parse_args()
    
    tlds = [t.strip() for t in args.tlds.split(",") if t.strip()]
    empty_domains, last_checked = load_empty_domains()
    
    print("Starting domain probing...")
    
    for domain in generate_candidates_from_dictionary(args.dict, tlds, empty_domains, last_checked):
        if not probe_site(domain):
            record_empty_domain(domain)
    
    for domain in generate_candidates_from_combinations(args.combo_length, tlds, empty_domains, last_checked):
        if not probe_site(domain):
            record_empty_domain(domain)
    
    print("Probing complete.")

if __name__ == '__main__':
    main()

