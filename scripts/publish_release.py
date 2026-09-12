"""Upload prepared firmware ZIPs/checksums to GitHub; publish only with --publish.

Uses the configured Git credential helper without printing or saving credentials.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request

from prepare_release import ROOT, VERSION, BOARDS

REPOSITORY = "thelastoutpostworkshop/ESPImageFirmware"
API = f"https://api.github.com/repos/{REPOSITORY}"


def credentials():
    result = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
        capture_output=True, text=True, cwd=ROOT,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"})
    fields = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if result.returncode or not fields.get("password"):
        raise ValueError("Sign in to GitHub through the configured Git credential manager first.")
    return fields["password"]


class GitHub:
    def __init__(self, token):
        self.token = token

    def request(self, url, method="GET", payload=None, content_type="application/json"):
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in ("api.github.com", "uploads.github.com") or not parsed.path.startswith(f"/repos/{REPOSITORY}/"):
            raise ValueError("Unexpected GitHub endpoint")
        body = json.dumps(payload).encode() if payload is not None and content_type == "application/json" else payload
        request = urllib.request.Request(url, data=body, method=method, headers={
            "Authorization": "Bearer " + self.token, "User-Agent": "ESPImageFirmware-release",
            "Accept": "application/vnd.github+json", "Content-Type": content_type})
        # Authenticated API/upload endpoints must never redirect credentials.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        with urllib.request.build_opener(NoRedirect).open(request, timeout=120) as response:
            return json.load(response)


def prepared_assets(directory, version):
    directory = Path(directory)
    assets = {}
    for line in (directory / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([a-f0-9]{64})  (ESPImageDisplay-[A-Z0-9_]+-[A-Za-z0-9.+-]+\.zip)", line)
        if not match:
            raise ValueError("Invalid checksum list")
        digest, name = match.groups()
        if name not in {f"ESPImageDisplay-{board}-{version}.zip" for board in BOARDS} or name in assets:
            raise ValueError("Unexpected or duplicate release asset")
        data = (directory / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f"Checksum mismatch: {name}")
        assets[name] = data
    if not assets:
        raise ValueError("No firmware ZIPs prepared")
    assets["SHA256SUMS.txt"] = (directory / "SHA256SUMS.txt").read_bytes()
    return assets


def publish(version, directory, prerelease=False, publish_now=False):
    if not VERSION.fullmatch(version):
        raise ValueError("Invalid version")
    assets = prepared_assets(directory, version)
    notes = (Path(directory) / "release-notes.md").read_text(encoding="utf-8")
    github = GitHub(credentials())
    tag = "v" + version
    # Token-authenticated listing also includes drafts from an interrupted upload.
    releases = github.request(API + "/releases?per_page=100")
    existing = next((release for release in releases if release["tag_name"] == tag), None)
    if existing and not existing["draft"]:
        raise ValueError(f"{tag} is already published. Published release assets are never replaced.")
    release = existing or github.request(API + "/releases", "POST", {
        "tag_name": tag, "target_commitish": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "name": f"ESPImageDisplay {version}" + (" (preview)" if prerelease else ""),
        "body": notes, "draft": True, "prerelease": prerelease})
    uploaded = {asset["name"]: asset for asset in release["assets"]}
    if set(uploaded) - set(assets):
        raise ValueError("Draft contains unexpected assets; review it before continuing.")
    for name, data in assets.items():
        digest = "sha256:" + hashlib.sha256(data).hexdigest()
        if name in uploaded:
            if uploaded[name].get("digest") != digest or uploaded[name].get("size") != len(data):
                raise ValueError(f"Draft asset differs: {name}. No files were replaced.")
        else:
            url = f"https://uploads.github.com/repos/{REPOSITORY}/releases/{release['id']}/assets?" + urllib.parse.urlencode({"name": name})
            asset = github.request(url, "POST", data, "application/zip" if name.endswith(".zip") else "text/plain")
            if asset.get("digest") != digest or asset.get("size") != len(data):
                raise ValueError(f"GitHub upload verification failed: {name}; release remains a draft.")
        print(f"Verified upload: {name}")
    result = github.request(API + f"/releases/{release['id']}", "PATCH", {
        "body": notes, "draft": not publish_now, "prerelease": prerelease,
        "make_latest": "false" if prerelease else "true"})
    print(("Published: " if publish_now else "Draft ready: ") + result["html_url"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--prerelease", action="store_true")
    parser.add_argument("--publish", action="store_true", help="Publish after all uploads verify; otherwise leave a draft")
    args = parser.parse_args()
    try:
        publish(args.version, args.directory or ROOT / "dist" / ("v" + args.version), args.prerelease, args.publish)
    except urllib.error.HTTPError as error:
        parser.exit(1, f"GitHub request failed (HTTP {error.code}); any incomplete release remains a draft.\n")
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Release upload failed: {error}\n")
