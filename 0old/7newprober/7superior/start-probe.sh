#!/bin/bash

python3 domain_probe_resumer.py  --dict path/to/your_dictionary.txt --combo-length 5 --tlds com --html found_websites.html --workers 10 --cleanup-interval 60
