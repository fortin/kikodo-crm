#!/Users/antonio/micromamba/envs/kikodo-crm/bin/python

import json
import sys

import requests
from decouple import config

BEARER_TOKEN = config("ADMIN_TOKEN")
BASE_URL = config("BASE_URL")
URL = f"{BASE_URL}/api/newsletter/subscribe/"


def main():
    if len(sys.argv) != 2:
        print("Usage: script.py <input_file>")
        sys.exit(1)

    filepath = sys.argv[1]

    with open(filepath, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines()]

    if len(lines) < 2:
        print("Input file must contain at least two lines: name and email")
        sys.exit(1)

    name = lines[0]
    email = lines[1]

    payload = {"name": name, "email": email}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BEARER_TOKEN}",
    }

    response = requests.post(URL, headers=headers, json=payload)

    print("Status:", response.status_code)
    print("Response:", response.text)


if __name__ == "__main__":
    main()
