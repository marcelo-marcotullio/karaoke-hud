import requests

artist = "Arch Enemy"
title = "Symphony of Destruction"

response = requests.get(
    "https://lrclib.net/api/search",
    params={"artist_name": artist, "track_name": title},
    headers={"User-Agent": "karaoke-hud v0.1"},
)

results = response.json()
print(results[0]["syncedLyrics"])
