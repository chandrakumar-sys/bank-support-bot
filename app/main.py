import time
import imaplib
import email
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
import os
from app.s3_loader import load_all_datasets
from app.bedrock_gen import generate_reply
import logging

load_dotenv()

LOG_FILE = os.getenv("LOG_FILE", "/var/log/bankbot.log")
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s %(message)s")

EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT")
APP_PASSWORD = os.getenv("APP_PASSWORD")
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", 10))


def connect_imap():
    """Connect to Gmail IMAP"""
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL_ACCOUNT, APP_PASSWORD)
    return mail


def fetch_unread_emails(mail):
    """Fetch unread emails"""
    mail.select("inbox")
    status, data = mail.search(None, "UNSEEN")
    email_ids = data[0].split()
    return email_ids


def send_email(to_addr, body):
    """Send email reply"""
    msg = MIMEText(body)
    msg["Subject"] = "Re: Your Query"
    msg["From"] = EMAIL_ACCOUNT
    msg["To"] = to_addr

    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(EMAIL_ACCOUNT, APP_PASSWORD)
    server.sendmail(EMAIL_ACCOUNT, [to_addr], msg.as_string())
    server.quit()


def main():
    logging.info("Starting Banking AI Bot...")
    print("Starting Banking AI Bot...")

    # Load datasets from S3
    logging.info("Loading datasets from S3...")
    customers, fees, loans = load_all_datasets()
    logging.info("Datasets loaded successfully.")

    logging.info("Waiting for emails...")

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
                subject = msg["Subject"]
                body = msg.get_payload(decode=True).decode(errors="ignore")

                logging.info(f"Received email from {from_addr}: {subject}")

                # Generate reply
                reply = generate_reply(from_addr, body, customers, fees, loans)

                # Send reply
                send_email(from_addr, reply)
                logging.info(f"Sent reply to {from_addr}")

            mail.logout()

        except Exception as e:
            logging.error(f"MAIN LOOP ERROR: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
