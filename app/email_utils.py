import email
from bs4 import BeautifulSoup

def extract_email_body(msg):
    """
    Extracts the email body safely.
    Returns plain text or 'no body' if nothing found.
    """

    body = None

    # ---- 1. If multipart, find text/plain ----
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            # skip attachments
            if "attachment" in content_disposition:
                continue

            # use text/plain if available
            if content_type == "text/plain":
                try:
                    body = part.get_payload(decode=True).decode(errors="ignore")
                except:
                    body = None
                break

        # ---- 2. If no text/plain, fallback to HTML ----
        if body is None:
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    try:
                        html = part.get_payload(decode=True).decode(errors="ignore")
                        body = BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
                    except:
                        body = None
                    break

    else:
        # ---- 3. Not multipart: decode directly ----
        try:
            body = msg.get_payload(decode=True).decode(errors="ignore")
        except:
            body = None

    # ---- 4. Final fallback ----
    if not body or body.strip() == "":
        return "no body"

    return body.strip()
