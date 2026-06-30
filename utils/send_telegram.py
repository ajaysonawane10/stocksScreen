"""
Telegram Bot — Send Excel reports to a Telegram chat.

Usage:
    python send_telegram.py

Requires environment variables:
    TELEGRAM_BOT_TOKEN  — Bot token from @BotFather
    TELEGRAM_CHAT_ID    — Target chat/group ID
"""

import glob
import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
import datetime


def get_env(name: str) -> str:
    """Get a required environment variable or exit."""
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"ERROR: Environment variable {name} is not set.")
        sys.exit(1)
    return value


def send_message(token: str, chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
    """Send a text message via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                print(f"  [OK] Text message sent.")
                return True
            else:
                print(f"  [FAIL] Telegram API error: {result}")
                return False
    except urllib.error.URLError as e:
        print(f"  [FAIL] Network error sending message: {e}")
        return False


def send_document(token: str, chat_id: str, filepath: str, caption: str = "") -> bool:
    """Send a file as a document via Telegram Bot API (multipart/form-data)."""
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    filename = os.path.basename(filepath)

    # Build multipart/form-data manually (no 'requests' dependency)
    boundary = "----PythonFormBoundary7MA4YWxkTrZu0gW"
    lines = []

    # chat_id field
    lines.append(f"--{boundary}")
    lines.append('Content-Disposition: form-data; name="chat_id"')
    lines.append("")
    lines.append(chat_id)

    # caption field
    if caption:
        lines.append(f"--{boundary}")
        lines.append('Content-Disposition: form-data; name="caption"')
        lines.append("")
        lines.append(caption)

    # parse_mode field
    lines.append(f"--{boundary}")
    lines.append('Content-Disposition: form-data; name="parse_mode"')
    lines.append("")
    lines.append("HTML")

    # Build the text portion
    text_part = "\r\n".join(lines) + "\r\n"

    # File portion header
    file_header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'
        f"Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n"
        f"\r\n"
    )

    # Closing boundary
    file_footer = f"\r\n--{boundary}--\r\n"

    # Read file content
    with open(filepath, "rb") as f:
        file_data = f.read()

    # Assemble body
    body = text_part.encode("utf-8") + file_header.encode("utf-8") + file_data + file_footer.encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                print(f"  [OK] Sent: {filename}")
                return True
            else:
                print(f"  [FAIL] Telegram API error for {filename}: {result}")
                return False
    except urllib.error.URLError as e:
        print(f"  [FAIL] Network error sending {filename}: {e}")
        return False


def find_latest_file(pattern: str) -> str | None:
    """Find the most recently modified file matching a glob pattern."""
    files = glob.glob(pattern)
    if not files:
        return None
    # Sort by modification time, newest first
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]


def build_summary_caption(report_type: str, filepath: str) -> str:
    """Build a caption string for the document."""
    today = datetime.datetime.now().strftime("%d %b %Y")
    emoji = "🌊" if report_type == "Elliott Wave" else "🐺"
    return (
        f"{emoji} <b>{report_type} Screener Report</b>\n"
        f"📅 {today}\n"
        f"📊 NSE Stocks (Nifty 50 + Next 50 + Midcaps)"
    )


def main():
    token = get_env("TELEGRAM_BOT_TOKEN")
    chat_id = get_env("TELEGRAM_CHAT_ID")

    today = datetime.datetime.now().strftime("%d %b %Y")

    # Find the Excel files
    ew_file = find_latest_file("output/EW_*.xlsx")
    ww_file = find_latest_file("output/WW_*.xlsx")

    if not ew_file and not ww_file:
        print("ERROR: No Excel files found (EW_*.xlsx / WW_*.xlsx).")
        sys.exit(1)

    sent_count = 0

    # Send header message
    header = (
        f"📈 <b>Stock Screener Report — {today}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    send_message(token, chat_id, header)

    # Send Elliott Wave Excel
    if ew_file:
        caption = build_summary_caption("Elliott Wave", ew_file)
        if send_document(token, chat_id, ew_file, caption):
            sent_count += 1
    else:
        print("  [SKIP] No Elliott Wave Excel found.")

    # Send Wolfe Wave Excel
    if ww_file:
        caption = build_summary_caption("Wolfe Wave", ww_file)
        if send_document(token, chat_id, ww_file, caption):
            sent_count += 1
    else:
        print("  [SKIP] No Wolfe Wave Excel found.")

    # Final status
    if sent_count > 0:
        footer = f"✅ {sent_count} report(s) delivered successfully."
        send_message(token, chat_id, footer)
        print(f"\nDone — {sent_count} file(s) sent to Telegram.")
    else:
        print("\nERROR: No files were sent successfully.")
        sys.exit(1)


if __name__ == "__main__":
    main()
