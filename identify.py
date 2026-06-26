import os
from dotenv import load_dotenv
import requests

load_dotenv()
api_token = os.getenv("AUDD_API_TOKEN")

with open("sample.wav", "rb") as f:
    response = requests.post(
        "https://api.audd.io/",
        data={"api_token": api_token},
        files={"file": f},
    )

result = response.json()
print(f"{result['result']['artist']} - {result['result']['title']}")
