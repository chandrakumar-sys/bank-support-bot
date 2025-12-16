import time
import imaplib
import email
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
import os
import logging

from app.s3_loader import load_all_datasets
from app.bedrock_gen import generate_reply, detect_intents

# GLPI handler functions (separate clean module)
from app.glpi_handler import (
    process_ticketing
)

load_dotenv()

LOG_FILE = os.getenv("LOG_FILE", "logs/bankbot.log")
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s %(message)s")

EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT")
APP_PASSWORD = os.getenv("APP_PASSWORD")
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", 10))


# -------------------------------------------------------
# SAFE EMAIL BODY EXTRACTOR 
# (prevents crash when mail has no body)
# -------------------------------------------------------
def extract_body(msg):
    """Safely extract email body from single-part or multi-part emails."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition")):
                try:
                    return part.get_payload(decode=True).decode(errors="ignore")
                except:
                    return "No message body."
        return "No message body."
    else:
        try:
            return msg.get_payload(decode=True).decode(errors="ignore")
        except:
            return "No message body."


# -------------------------------------------------------
# EMAIL / IMAP HELPERS
# -------------------------------------------------------
def connect_imap():
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL_ACCOUNT, APP_PASSWORD)
    return mail


def fetch_unread_emails(mail):
    mail.select("inbox")
    status, data = mail.search(None, "UNSEEN")
    return data[0].split()


def send_email(to_addr, body):
    msg = MIMEText(body)
    msg["Subject"] = "Re: Your Query"
    msg["From"] = EMAIL_ACCOUNT
    msg["To"] = to_addr

    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(EMAIL_ACCOUNT, APP_PASSWORD)
    server.sendmail(EMAIL_ACCOUNT, [to_addr], msg.as_string())
    server.quit()


# -------------------------------------------------------
# MAIN LOOP
# -------------------------------------------------------
def main():
    logging.info("Starting Banking AI Bot…")
    print("Starting Banking AI Bot…")

    logging.info("Loading datasets from S3…")
    customers, fees, loans = load_all_datasets()
    logging.info("Datasets loaded successfully.")

    logging.info("Waiting for emails…")

    while True:
        try:
            mail = connect_imap()
            unread = fetch_unread_emails(mail)

            if not unread:
                time.sleep(POLL_INTERVAL)
                continue

            for eid in unread:
                status, data = mail.fetch(eid, "(RFC822)")
                if status != "OK":
                    continue

                msg = email.message_from_bytes(data[0][1])

                from_addr = email.utils.parseaddr(msg["From"])[1]
                subject = msg.get("Subject", "")
                body = extract_body(msg)

                logging.info(f"Received email from {from_addr}")

                # ------------------------------
                # 1) Generate reply using Bedrock
                # ------------------------------
                ai_reply = generate_reply(from_addr, body, customers, fees, loans)

                # Detect intents for ticket logic
                intents = detect_intents(body)

                # ------------------------------
                # 2) Process ticketing (create / update / auto-close)
                # ------------------------------
                ticket_id, final_reply = process_ticketing(
                    from_email=from_addr,
                    user_message=body,
                    ai_reply=ai_reply,
                    intents=intents
                )

                # ------------------------------
                # 3) Send email to customer
                # ------------------------------
                send_email(from_addr, final_reply)
                logging.info(f"Sent reply to {from_addr} (ticket={ticket_id})")

            mail.logout()

        except Exception as e:
            logging.error(f"MAIN LOOP ERROR: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
