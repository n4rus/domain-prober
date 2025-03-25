# Domain Prober

## Overview
This Python script probes randomly generated and dictionary-based domain names to check for valid websites with content. It records successful probes in an HTML file and tracks empty domains to avoid redundant checks. Additionally, it includes a memory cleanup function to prevent memory overflow.

## Features
- Generates domain names using a dictionary file and random character combinations.
- Probes websites for valid content.
- Stores valid domains in an HTML file with a search feature.
- Avoids redundant checks by maintaining a list of empty domains.
- Runs multiple probes in parallel for efficiency.
- Periodically clears memory and terminal logs to prevent overflow.

## Requirements
- Python 3.x
- Required libraries:
  - `requests`
  - `beautifulsoup4`
  - `argparse`
  - `itertools`
  - `concurrent.futures`

Install dependencies using:
```bash
pip install requests beautifulsoup4
```

## Usage
Run the script with the following command:
```bash
python3 domain_probe_resumer.py  --dict path/to/your_dictionary.txt --combo-length 5 --tlds com --html found_websites.html --workers 10 --cleanup-interval 23
```

### Command-line Arguments
| Argument          | Description |
|------------------|-------------|
| `--dict` | Path to the dictionary file containing words to generate domains. |
| `--combo-length` | Length of generated domain names using random combinations. Default is `5`. |
| `--tlds` | Comma-separated list of TLDs to use. Default is `com`. |
| `--html` | Path to the HTML file to store valid domains. |
| `--workers` | Number of concurrent workers for domain probing. Default is `10`. |
| `--cleanup-interval` | Time interval (in seconds) for memory and log cleanup. Default is `60`. |

## Output
- **Valid Domains**: Stored in an HTML file with a search feature.
- **Empty Domains**: Logged in `empty_domains.txt` to avoid re-checking them.
- **Log Cleanup**: The script periodically clears the terminal logs and frees up memory.

## License
This project is licensed under the MIT License.


