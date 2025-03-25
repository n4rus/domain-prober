import json
from bs4 import BeautifulSoup

def extract_links_from_html(html_file, json_file):
    """
    Extracts all the href values from <a> tags in the HTML file
    and saves them as a JSON array in the json_file.
    """
    # Open and read the HTML file
    with open(html_file, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
    
    # Extract href values from all <a> tags with href attributes
    links = [a.get("href") for a in soup.find_all("a", href=True)]
    
    # Remove duplicates and sort the list
    links = sorted(set(links))
    
    # Save the links to a JSON file
    with open(json_file, "w", encoding="utf-8") as jf:
        json.dump(links, jf, indent=2)
    
    print(f"Extracted {len(links)} links and saved to {json_file}.")

if __name__ == "__main__":
    # Set the names of your input HTML file and output JSON file
    html_file = "found_websites.html"
    json_file = "domains.json"
    
    extract_links_from_html(html_file, json_file)

