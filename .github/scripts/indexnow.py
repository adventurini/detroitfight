"""Submit the pages changed by a production deploy to IndexNow.

usage: indexnow.py <deployed-sha> [--dry-run]

IndexNow is read by Bing (which feeds ChatGPT and Copilot search), Yandex, Naver,
Seznam and Yep. Google does not take IndexNow; it reads sitemap.xml on its own
schedule, so keep the sitemap lastmod dates current in every pull request.

What this does:
1. Diffs the deployed commit against its first parent (the previous main).
2. Maps each changed .html file to its clean URL (vercel.json has cleanUrls on).
3. POSTs the list to api.indexnow.org with the site's key.

The key is public by design: IndexNow verifies it by fetching
https://detroitfight.com/<key>.txt, which is the file at the repo root.
"""
import glob
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request

HOST = "detroitfight.com"
ENDPOINT = "https://api.indexnow.org/indexnow"
# Pages marked noindex are never submitted. The googled...html file is the
# Search Console verification file, not a page.
NEVER = {"thank-you.html", "lp.html"}


def url_for(path):
    """Changed file -> public URL, or None if it is not an indexable page."""
    path = path.strip()
    if "/" in path or not path.endswith(".html"):
        return None
    if path in NEVER or path.startswith("googled"):
        return None
    if path == "index.html":
        return f"https://{HOST}/"
    return f"https://{HOST}/{path[:-5]}"


def changed_urls(sha):
    out = subprocess.check_output(
        ["git", "diff", "--name-only", "--diff-filter=ACDMR", f"{sha}^1", sha], text=True
    )
    return sorted({u for u in (url_for(p) for p in out.splitlines()) if u})


def read_key():
    for f in glob.glob("*.txt"):
        stem = f[:-4]
        if re.fullmatch(r"[0-9a-f]{32}", stem) and open(f, encoding="utf-8").read().strip() == stem:
            return stem
    sys.exit("no IndexNow key file found at the repo root (expected <key>.txt containing the key)")


def main(argv):
    if not argv or argv[0].startswith("-"):
        sys.exit(__doc__)
    sha, dry_run = argv[0], "--dry-run" in argv
    urls = changed_urls(sha)
    if not urls:
        print("no indexable page changed in this deploy; nothing to submit")
        return
    key = read_key()
    payload = {
        "host": HOST,
        "key": key,
        "keyLocation": f"https://{HOST}/{key}.txt",
        "urlList": urls,
    }
    print(f"submitting {len(urls)} URL(s):")
    for u in urls:
        print("  " + u)
    if dry_run:
        print("dry run, not sent")
        return
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
    # 200 OK and 202 Accepted both mean the list was taken.
    # 400 bad request, 403 key not valid, 422 URLs or key do not match the host, 429 too many.
    print(f"IndexNow responded {status}")
    if status not in (200, 202):
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
