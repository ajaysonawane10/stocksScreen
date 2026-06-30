"""
Slack Bot — Send Excel reports to a Slack channel.

Usage:
    python -m utils.send_slack

Requires environment variables:
    SLACK_BOT_TOKEN   — Bot token (xoxb-...) with files:write and chat:write scopes
    SLACK_CHANNEL_ID  — Target channel ID (e.g., C0123456789)
"""

import glob
import json
import os
import sys
import urllib.request
import urllib.error
import datetime


SLACK_API = "https://slack.com/api"


def get_env(name: str) -> str:
    """Get a required environment variable or exit."""
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"ERROR: Environment variable {name} is not set.")
        sys.exit(1)
    return value


def slack_api(token: str, method: str, payload: dict) -> dict:
    """Call a Slack Web API method (JSON body)."""
    url = f"{SLACK_API}/{method}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        print(f"  [FAIL] Slack API error ({method}): {e}")
        return {"ok": False, "error": str(e)}


def send_message(token: str, channel: str, text: str, blocks: list | None = None) -> bool:
    """Post a text message to a Slack channel."""
    payload = {"channel": channel, "text": text}
    if blocks:
        payload["blocks"] = blocks
    result = slack_api(token, "chat.postMessage", payload)
    if result.get("ok"):
        print(f"  [OK] Text message posted to channel.")
        return True
    print(f"  [FAIL] chat.postMessage: {result.get('error')}")
    return False


def upload_file(token: str, channel: str, filepath: str, title: str, initial_comment: str = "") -> bool:
    """
    Upload a file to Slack using the new multi-step upload API.
    Steps:
      1. files.getUploadURLExternal  → get upload_url + file_id
      2. POST file bytes to upload_url
      3. files.completeUploadExternal → finalize and share to channel
    """
    filename = os.path.basename(filepath)
    filesize = os.path.getsize(filepath)

    # Step 1: Get upload URL
    step1 = slack_api(token, "files.getUploadURLExternal", {
        "filename": filename,
        "length": filesize,
    })
    if not step1.get("ok"):
        print(f"  [FAIL] getUploadURLExternal: {step1.get('error')}")
        return False

    upload_url = step1["upload_url"]
    file_id = step1["file_id"]

    # Step 2: Upload file content
    with open(filepath, "rb") as f:
        file_data = f.read()

    req = urllib.request.Request(upload_url, data=file_data, method="POST")
    req.add_header("Content-Type", "application/octet-stream")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status not in (200, 201):
                print(f"  [FAIL] File upload HTTP {resp.status}")
                return False
    except urllib.error.URLError as e:
        print(f"  [FAIL] File upload error: {e}")
        return False

    # Step 3: Complete upload and share to channel
    step3 = slack_api(token, "files.completeUploadExternal", {
        "files": [{"id": file_id, "title": title}],
        "channel_id": channel,
        "initial_comment": initial_comment,
    })
    if step3.get("ok"):
        print(f"  [OK] Uploaded: {filename}")
        return True
    print(f"  [FAIL] completeUploadExternal: {step3.get('error')}")
    return False


def find_latest_file(pattern: str) -> str | None:
    """Find the most recently modified file matching a glob pattern."""
    files = glob.glob(pattern)
    if not files:
        return None
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]


def main():
    token = get_env("SLACK_BOT_TOKEN")
    channel = get_env("SLACK_CHANNEL_ID")

    today = datetime.datetime.now().strftime("%d %b %Y")

    # Find Excel files
    ew_file = find_latest_file("output/EW_*.xlsx")
    ww_file = find_latest_file("output/WW_*.xlsx")

    if not ew_file and not ww_file:
        print("ERROR: No Excel files found (output/EW_*.xlsx / output/WW_*.xlsx).")
        sys.exit(1)

    sent_count = 0

    # Header message
    header = (
        f":chart_with_upwards_trend: *Stock Screener Report — {today}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    send_message(token, channel, header)

    # Upload Elliott Wave Excel
    if ew_file:
        comment = (
            f":ocean: *Elliott Wave Screener Report*\n"
            f":calendar: {today}\n"
            f":bar_chart: NSE Stocks (Nifty 50 + Next 50 + Midcaps)"
        )
        if upload_file(token, channel, ew_file, f"Elliott Wave Report — {today}", comment):
            sent_count += 1
    else:
        print("  [SKIP] No Elliott Wave Excel found.")

    # Upload Wolfe Wave Excel
    if ww_file:
        comment = (
            f":wolf: *Wolfe Wave Screener Report*\n"
            f":calendar: {today}\n"
            f":bar_chart: NSE Stocks (Nifty 50 + Next 50 + Midcaps)"
        )
        if upload_file(token, channel, ww_file, f"Wolfe Wave Report — {today}", comment):
            sent_count += 1
    else:
        print("  [SKIP] No Wolfe Wave Excel found.")

    # Footer
    if sent_count > 0:
        send_message(token, channel, f":white_check_mark: {sent_count} report(s) delivered successfully.")
        print(f"\nDone — {sent_count} file(s) sent to Slack.")
    else:
        print("\nERROR: No files were sent successfully.")
        sys.exit(1)


if __name__ == "__main__":
    main()
