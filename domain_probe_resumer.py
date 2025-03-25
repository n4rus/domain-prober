import argparse
import os
import requests
import itertools
import string
import random
import concurrent.futures
import gc
import threading
import time
import json
from bs4 import BeautifulSoup

def clear_terminal():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def memory_cleanup():
    """Force garbage collection to free up memory."""
    gc.collect()

def periodic_cleanup(interval=60):
    """Periodically clear terminal log and clean memory every 'interval' seconds."""
    while True:
        time.sleep(interval)
        clear_terminal()
        memory_cleanup()
        print("[INFO] Terminal cleared and memory cleaned.")

def start_cleanup_thread(interval=60):
    """Start a background thread for periodic cleanup."""
    thread = threading.Thread(target=periodic_cleanup, args=(interval,), daemon=True)
    thread.start()

def load_empty_domains():
    """
    Load previously probed empty domains from "empty_domains.txt" 
    and return them as a set, along with the last checked domain.
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

def record_empty_domain(url, empty_set):
    """
    Record a domain as empty by appending it to "empty_domains.txt"
    and update the in-memory empty_set.
    """
    with open("empty_domains.txt", "a", encoding="utf-8") as f:
        f.write(url + "\n")
    empty_set.add(url)

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

def save_results(new_domains, html_file="found_websites.html", json_file="domains.json"):
    """
    Merge existing valid domains from the JSON file with new ones,
    update the JSON file, and generate an HTML file that dynamically loads them.
    """
    # Load existing domains from JSON if it exists
    existing_domains = set()
    if os.path.exists(json_file):
        with open(json_file, "r", encoding="utf-8") as jf:
            try:
                existing_domains = set(json.load(jf))
            except Exception as e:
                print("Error loading JSON domains:", e)

    # Merge and sort the domains
    updated_domains = sorted(existing_domains | new_domains)

    # Save the updated domains to JSON
    with open(json_file, "w", encoding="utf-8") as jf:
        json.dump(updated_domains, jf, indent=2)

    # Generate the HTML shell
    with open(html_file, "w", encoding="utf-8") as f:
        f.write("""<html>
<head>
  <title>Found Websites</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; }
    #searchBar { position: fixed; top: 20px; right: 20px; width: 200px; }
    ul { margin-top: 140px; }
    li { margin-bottom: 5px; }
    .pagination { margin-top: 20px; }
    .pagination button { margin: 0 5px; }
    .settings { margin-top: 60px; }
  </style>
</head>
<body>
  <div id="searchBar">
    <input type="text" id="searchInput" onkeyup="searchDomains()" placeholder="Search domains...">
  </div>
  <h1>Probed Websites with Valid Content</h1>
  <div class="settings">
    <label for="itemsPerPageSelect">Links per page: </label>
    <select id="itemsPerPageSelect" onchange="changeItemsPerPage()">
      <option value="10">10</option>
      <option value="25">25</option>
      <option value="50" selected>50</option>
      <option value="100">100</option>
      <option value="500">500</option>
      <option value="1000">1000</option>
      <option value="5000">5000</option>
      <option value="10000">10000</option>
    </select>
  </div>
  <ul id="domainList"></ul>
  <div class="pagination">
    <button onclick="prevPage()">Prev</button>
    <span id="pageInfo"></span>
    <button onclick="nextPage()">Next</button>
  </div>
  <script>
    var domains = [];
    var filteredDomains = [];
    var currentPage = 1;
    var itemsPerPage = 50;

    // Load domains from JSON
    fetch('""" + json_file + """')
      .then(response => response.json())
      .then(data => {
        domains = data;
        displayPage(currentPage);
      })
      .catch(error => console.error('Error loading domains:', error));

    // Display a paginated list
    function displayPage(page, listData) {
      var data = listData || domains;
      var startIndex = (page - 1) * itemsPerPage;
      var endIndex = startIndex + itemsPerPage;
      var list = document.getElementById('domainList');
      list.innerHTML = "";

      for (var i = startIndex; i < Math.min(endIndex, data.length); i++) {
        var li = document.createElement("li");
        var a = document.createElement("a");
        a.href = data[i];
        a.target = "_blank";
        a.textContent = "[" + (i + 1) + "] " + data[i];
        li.appendChild(a);
        list.appendChild(li);
      }

      document.getElementById("pageInfo").textContent = "Page " + page + " of " + Math.ceil(data.length / itemsPerPage) +
        (listData ? " (filtered)" : "");
    }

    // Navigate pages
    function nextPage() {
      var data = (filteredDomains.length > 0) ? filteredDomains : domains;
      if (currentPage < Math.ceil(data.length / itemsPerPage)) {
        currentPage++;
        displayPage(currentPage, data);
      }
    }

    function prevPage() {
      if (currentPage > 1) {
        currentPage--;
        displayPage(currentPage, (filteredDomains.length > 0) ? filteredDomains : null);
      }
    }

    // Change items per page
    function changeItemsPerPage() {
      itemsPerPage = parseInt(document.getElementById("itemsPerPageSelect").value);
      currentPage = 1;
      displayPage(currentPage, (filteredDomains.length > 0) ? filteredDomains : null);
    }

    // Search with pagination
    function searchDomains() {
      var filter = document.getElementById("searchInput").value.toLowerCase();
      if (filter === "") {
        filteredDomains = [];
        currentPage = 1;
        displayPage(currentPage);
        return;
      }
      filteredDomains = domains.filter(domain => domain.toLowerCase().includes(filter));
      currentPage = 1;
      displayPage(currentPage, filteredDomains);
    }

    window.onload = function() {
      displayPage(currentPage);
    };
  </script>
</body>
</html>""")

    print(f"Updated JSON and HTML files with {len(updated_domains)} valid domains.")


def probe_site(url):
    """
    Use a randomized spoofed User-Agent to probe the URL.
    Return True if the site's HTTP status is 200 and content length > 100.
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
    Generate domain candidates from a dictionary file,
    resuming from the last checked domain (if provided).
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
    Generate domain candidates from letter-digit combinations,
    resuming from the last checked domain (if provided).
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
    For each domain, if probe_site returns True, add it to the found set and update the HTML file.
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
                    record_empty_domain(url, empty_set)
            except Exception as e:
                print(f"Unexpected error with {url}: {e}")
                record_empty_domain(url, empty_set)
    return found_domains

def main():
    parser = argparse.ArgumentParser(
        description="Probe websites and update an HTML file with new valid domains."
    )
    parser.add_argument("--dict", type=str, required=True, help="Path to dictionary file.")
    parser.add_argument("--combo-length", type=int, default=5, help="Length of generated domain names.")
    parser.add_argument("--tlds", type=str, default="com", help="Comma-separated list of TLDs.")
    parser.add_argument("--html", type=str, default="found_websites.html", help="Path to the HTML file storing valid domains.")
    parser.add_argument("--workers", type=int, default=10, help="Number of concurrent workers.")
    parser.add_argument("--cleanup-interval", type=int, default=60, help="Interval (in seconds) for terminal and memory cleanup.")
    args = parser.parse_args()

    # Start the periodic cleanup thread
    start_cleanup_thread(args.cleanup_interval)

    tlds = [t.strip() for t in args.tlds.split(",") if t.strip()]
    empty_domains, last_checked = load_empty_domains()
    found_domains = set()

    print("Starting domain probing...")

    # Generate and probe candidates from the dictionary file.
    dict_candidates = list(generate_candidates_from_dictionary(args.dict, tlds, empty_domains, last_checked))
    probe_domains(dict_candidates, args.html, empty_domains, args.workers)

    # Generate and probe candidates from letter-digit combinations.
    combo_candidates = list(generate_candidates_from_combinations(args.combo_length, tlds, empty_domains, last_checked))
    probe_domains(combo_candidates, args.html, empty_domains, args.workers)

    print("Probing complete.")

if __name__ == '__main__':
    main()

