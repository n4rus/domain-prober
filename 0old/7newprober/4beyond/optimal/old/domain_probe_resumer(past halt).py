import argparse
import os
import requests
import itertools
import string
import random
import concurrent.futures
from bs4 import BeautifulSoup

def load_empty_domains():
    """
    Load previously probed empty domains from "empty_domains.txt".
    Returns a set of empty domains and the last checked domain.
    """
    empty_domains = set()
    last_checked = None
    if os.path.exists("empty_domains.txt"):
        with open("empty_domains.txt", "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
            if lines:
                last_checked = lines[-1]  # Resume from this domain
                empty_domains.update(lines)
    return empty_domains, last_checked

def record_empty_domain(url):
    """
    Record a domain as empty by appending it to "empty_domains.txt".
    """
    with open("empty_domains.txt", "a", encoding="utf-8") as f:
        f.write(url + "\n")

def load_existing_domains(html_file):
    """
    Extract valid domains already stored in the HTML file.
    """
    existing_domains = set()
    if os.path.exists(html_file):
        with open(html_file, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
            for link in soup.find_all("a", href=True):
                existing_domains.add(link["href"].strip())
    return existing_domains

def save_results(new_domains, html_file):
    """
    Merge existing valid domains from the HTML file with new ones
    and update the HTML file without removing previous entries.
    """
    existing_domains = load_existing_domains(html_file)
    updated_domains = sorted(existing_domains | new_domains)
    with open(html_file, "w", encoding="utf-8") as f:
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
        for i, domain in enumerate(updated_domains, 1):
            f.write(f'    <li><a href="{domain}" target="_blank">[{i}] {domain}</a></li>\n')
        f.write("""  </ul>
</body>
</html>""")
    print(f"Updated HTML file with {len(updated_domains)} valid domains.")

def probe_site(url):
    """
    Probe a domain using a randomized User-Agent.
    Returns True if the site's HTTP status is 200 and content length > 100.
    Otherwise returns False.
    """
    print(f"Testing: {url}")
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36",
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:92.0) Gecko/20100101 Firefox/92.0",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/537.36"
    ]
    headers = {"User-Agent": random.choice(user_agents)}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200 and len(response.text) > 100:
            return True
    except requests.RequestException as e:
        print(f"Error probing {url}: {e}")
    return False

def generate_candidates_from_dictionary(dict_file, tlds, empty_set, last_checked):
    """
    Generate domain candidates from a dictionary file.
    If last_checked is set, resume generating candidates starting after that domain.
    """
    resume = last_checked is None
    with open(dict_file, "r", encoding="utf-8") as f:
        for word in f:
            word = word.strip()
            if word and len(word) <= 63:
                for tld in tlds:
                    domain = f"http://{word}.{tld}"
                    if domain in empty_set:
                        if domain == last_checked:
                            resume = True
                        continue
                    if resume:
                        yield domain

def generate_candidates_from_combinations(length, tlds, empty_set, last_checked):
    """
    Generate domain candidates from letter-digit combinations.
    If last_checked is set, resume generating candidates starting after that domain.
    """
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

def probe_domains(domains, html_file, empty_set, max_workers=10):
    """
    Probe domains in parallel using ThreadPoolExecutor.
    For each domain, if probe_site returns True, add it to the found set and update the HTML.
    Otherwise, record it as empty.
    """
    found_domains = set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(probe_site, url): url for url in domains}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                if future.result():
                    found_domains.add(url)
                    save_results(found_domains, html_file)
                else:
                    record_empty_domain(url)
            except Exception as e:
                print(f"Unexpected error with {url}: {e}")
                record_empty_domain(url)
    return found_domains

def main():
    parser = argparse.ArgumentParser(description="Probe websites and update an HTML file with new valid domains.")
    parser.add_argument("--dict", type=str, required=True, help="Path to dictionary file.")
    parser.add_argument("--combo-length", type=int, default=5, help="Length of generated domain names.")
    parser.add_argument("--tlds", type=str, default="com", help="Comma-separated list of TLDs.")
    parser.add_argument("--html", type=str, default="found_websites.html", help="Path to the HTML file storing valid domains.")
    parser.add_argument("--workers", type=int, default=10, help="Number of concurrent workers.")
    args = parser.parse_args()

    tlds = [t.strip() for t in args.tlds.split(",") if t.strip()]
    empty_domains, last_checked = load_empty_domains()
    found_domains = set()

    print("Starting domain probing...")

    # Probe candidates generated from the dictionary file.
    dict_candidates = list(generate_candidates_from_dictionary(args.dict, tlds, empty_domains, last_checked))
    probe_domains(dict_candidates, args.html, empty_domains, args.workers)

    # Probe candidates generated from letter-digit combinations.
    combo_candidates = list(generate_candidates_from_combinations(args.combo_length, tlds, empty_domains, last_checked))
    probe_domains(combo_candidates, args.html, empty_domains, args.workers)

    print("Probing complete.")

if __name__ == '__main__':
    main()

