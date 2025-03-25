import argparse
import os
import requests
import itertools
import string
import time
from bs4 import BeautifulSoup

def load_existing_domains(html_file):
    """Extract existing domains from the HTML file."""
    existing_domains = set()
    if os.path.exists(html_file):
        with open(html_file, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
            for link in soup.find_all("a", href=True):
                existing_domains.add(link["href"].strip())
    return existing_domains

def save_results(found, html_file):
    """Update the HTML file with new found domains while keeping existing ones."""
    existing_domains = load_existing_domains(html_file)
    all_domains = sorted(existing_domains | found)
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
        for i, domain in enumerate(all_domains, 1):
            f.write(f'    <li><a href="{domain}" target="_blank">[{i}] {domain}</a></li>\n')
        f.write("""  </ul>
</body>
</html>""")
    print(f"Updated HTML file with {len(all_domains)} valid domains.")

def probe_site(url):
    """Use a spoofed User-Agent to probe the URL. Return True if content appears valid."""
    print(f"Testing: {url}")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200 and len(response.text) > 100:
            return True
    except requests.RequestException:
        pass
    return False

def generate_candidates_from_dictionary(dict_file, tlds):
    """Generate domain candidates from a dictionary file."""
    with open(dict_file, "r", encoding="utf-8") as f:
        for word in f:
            word = word.strip()
            if word and len(word) <= 63:
                for tld in tlds:
                    yield f"http://{word}.{tld}"

def generate_candidates_from_combinations(length, tlds):
    """Generate domain candidates from letter-digit combinations."""
    chars = string.ascii_lowercase + string.digits
    for comb in itertools.product(chars, repeat=length):
        for tld in tlds:
            yield f"http://{''.join(comb)}.{tld}"

def main():
    parser = argparse.ArgumentParser(description="Probe websites and update an HTML file with new valid domains.")
    parser.add_argument("--dict", type=str, required=True, help="Path to dictionary file.")
    parser.add_argument("--combo-length", type=int, default=5, help="Length of generated domain names.")
    parser.add_argument("--tlds", type=str, default="com", help="Comma-separated list of TLDs.")
    parser.add_argument("--html", type=str, default="found_websites.html", help="Path to the HTML file storing valid domains.")
    args = parser.parse_args()

    tlds = [t.strip() for t in args.tlds.split(",") if t.strip()]
    found_domains = set()
    existing_domains = load_existing_domains(args.html)
    
    print("Starting domain probing...")
    
    for domain in generate_candidates_from_dictionary(args.dict, tlds):
        if domain not in existing_domains and probe_site(domain):
            found_domains.add(domain)
            save_results(found_domains, args.html)
    
    for domain in generate_candidates_from_combinations(args.combo_length, tlds):
        if domain not in existing_domains and probe_site(domain):
            found_domains.add(domain)
            save_results(found_domains, args.html)
    
    print("Probing complete.")

if __name__ == '__main__':
    main()

