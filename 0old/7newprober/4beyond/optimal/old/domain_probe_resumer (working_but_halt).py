import argparse
import os
import requests
import itertools
import string
import random
import concurrent.futures
from bs4 import BeautifulSoup

def load_empty_domains():
    """Load previously probed empty domains and return them as a set, with the last checked domain."""
    empty_domains = set()
    last_checked = None
    if os.path.exists("empty_domains.txt"):
        with open("empty_domains.txt", "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
            if lines:
                last_checked = lines[-1]  # Get the last checked domain
                empty_domains.update(lines)
    return empty_domains, last_checked

def record_empty_domain(url):
    """Record a domain as empty by appending it to the empty_domains.txt file."""
    with open("empty_domains.txt", "a", encoding="utf-8") as f:
        f.write(url + "\n")

def load_existing_domains(html_file):
    """Extract existing domains from the HTML file."""
    existing_domains = set()
    if os.path.exists(html_file):
        with open(html_file, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
            for link in soup.find_all("a", href=True):
                existing_domains.add(link["href"].strip())
    return existing_domains

def save_results(new_domains, html_file):
    """Append only new domains to the existing HTML file without overwriting it."""
    existing_domains = load_existing_domains(html_file)
    updated_domains = sorted(existing_domains | new_domains)
    
    if not os.path.exists(html_file) or not existing_domains:
        mode = "w"  # Create new file if missing
    else:
        mode = "a"  # Append to existing file
    
    with open(html_file, mode, encoding="utf-8") as f:
        if mode == "w":
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

def probe_site(session, url, found, html_file, empty_set):
    """Use a randomized spoofed User-Agent to probe the URL. Return True if content appears valid."""
    print(f"Testing: {url}")
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36",
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:92.0) Gecko/20100101 Firefox/92.0",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/537.36"
    ]
    headers = {"User-Agent": random.choice(user_agents)}
    try:
        response = session.get(url, headers=headers, timeout=1.5)
        if response.status_code == 200 and len(response.text) > 100:
            found.add(url)
            save_results(found, html_file)
            return True
        else:
            record_empty_domain(url)
    except requests.RequestException:
        record_empty_domain(url)
    return False

def probe_domains(domains, html_file, empty_set, max_workers=10):
    """Probe domains in parallel using ThreadPoolExecutor."""
    found_domains = set()
    session = requests.Session()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(probe_site, session, url, found_domains, html_file, empty_set): url for url in domains}
        for future in concurrent.futures.as_completed(future_to_url):
            pass  # probe_site handles saving to HTML and empty domains
    return found_domains

def generate_candidates(dict_file, tlds, empty_set, last_checked):
    """Generate domain candidates from dictionary and letter-digit combinations."""
    resume = last_checked is None
    candidates = []
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
                        candidates.append(domain)
    return candidates

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
    
    print("Starting domain probing...")
    
    candidates = generate_candidates(args.dict, tlds, empty_domains, last_checked)
    probe_domains(candidates, args.html, empty_domains, args.workers)
    
    print("Probing complete.")

if __name__ == '__main__':
    main()

