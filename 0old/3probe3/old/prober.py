import os
import json
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import product, islice

# Configuration - Safe for background operation
CONFIG = {
    "state_file": "scanner_state.json",
    "report_file": "web_discovery_report.log",  # Simple log instead of HTML
    "dictionary_file": "wordlist.txt",
    "tlds": ['.com', '.net', '.org'],
    "char_set": 'abcdefghijklmnopqrstuvwxyz0123456789',
    "batch_size": 5,
    "max_workers": 8,
    "timeout": 8,
    "progress_interval": 5.0,  # Seconds between progress updates
    "log_file": "scan_results.txt"
}

class PeripheralSafeScanner:
    def __init__(self):
        self.state = self.load_state()
        self.dictionary = self.load_dictionary()
        self.running = True
        self.last_progress = 0
        self.results = []
        
    def load_state(self):
        try:
            with open(CONFIG['state_file'], 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "dict_index": 0,
                "combo_index": 0,
                "total_scanned": 0,
                "dict_complete": False
            }

    def save_state(self):
        with open(CONFIG['state_file'], 'w') as f:
            json.dump(self.state, f)

    def load_dictionary(self):
        try:
            with open(CONFIG['dictionary_file'], 'r') as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            return []

    def generate_combinations(self):
        length = 1
        while True:
            for combo in product(CONFIG['char_set'], repeat=length):
                yield ''.join(combo)
            length += 1

    def get_next_batch(self):
        if not self.state['dict_complete'] and self.dictionary:
            start = self.state['dict_index']
            end = start + CONFIG['batch_size']
            batch = self.dictionary[start:end]
            self.state['dict_index'] = end
            if end >= len(self.dictionary):
                self.state['dict_complete'] = True
            return [(word, tld) for word in batch for tld in CONFIG['tlds']]
        
        combo_gen = self.generate_combinations()
        batch = list(islice(combo_gen, 
                      self.state['combo_index'], 
                      self.state['combo_index'] + CONFIG['batch_size']))
        self.state['combo_index'] += len(batch)
        return [(base, tld) for base in batch for tld in CONFIG['tlds']]

    def probe_url(self, base, tld):
        url = f"http://{base}{tld}"
        try:
            response = requests.head(url, timeout=CONFIG['timeout'])
            if response.status_code == 200:
                with open(CONFIG['log_file'], 'a') as f:
                    f.write(f"Valid: {url}\n")
                return True
        except Exception:
            pass
        return False

    def show_progress(self):
        elapsed = time.time() - self.last_progress
        if elapsed >= CONFIG['progress_interval']:
            print(f"Scanned: {self.state['total_scanned']} | Valid: {len(self.results)}")
            self.last_progress = time.time()

    def run(self):
        try:
            with ThreadPoolExecutor(max_workers=CONFIG['max_workers']) as executor:
                while self.running:
                    batch = self.get_next_batch()
                    if not batch:
                        break

                    futures = {executor.submit(self.probe_url, base, tld): (base, tld)
                              for base, tld in batch}

                    for future in as_completed(futures):
                        self.state['total_scanned'] += 1
                        if future.result():
                            self.results.append(future.result())
                        self.show_progress()
                        self.save_state()

                    # Yield to system for peripheral responsiveness
                    time.sleep(0.1)

        except KeyboardInterrupt:
            print("\nScan paused. Current state saved.")
        finally:
            self.save_state()
            print(f"Scan results logged to {CONFIG['log_file']}")

if __name__ == '__main__':
    scanner = PeripheralSafeScanner()
    print("Starting background-safe web scan...")
    scanner.run()
