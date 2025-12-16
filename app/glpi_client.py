import requests
import logging
import json

GLPI_API_URL = "http://40.192.14.7/glpi/apirest.php/"
APP_TOKEN = "TyeRo8qYIYCF7hCrWYP9exCiyx1SSyyH07vcXop1"
USER_TOKEN = "RYMmbRwOPtH8aYHyITlLtshjk0PL8i7Hv94GRvkg"

# ---------------------------------------------------
# Ticket Logger (writes to logs/ticket.log)
# ---------------------------------------------------
ticket_logger = logging.getLogger("ticket_logger")
ticket_handler = logging.FileHandler("logs/ticket.log")
ticket_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
ticket_logger.addHandler(ticket_handler)
ticket_logger.setLevel(logging.INFO)


# ---------------------------------------------------
# 1. START GLPI SESSION
# ---------------------------------------------------
def glpi_start_session():
    try:
        headers = {
            "App-Token": APP_TOKEN,
            "Authorization": f"user_token {USER_TOKEN}",
        }

        resp = requests.get(GLPI_API_URL + "initSession", headers=headers)

        if resp.status_code != 200:
            ticket_logger.error(f"GLPI initSession failed: {resp.text}")
            return None

        session_token = resp.json().get("session_token")
        ticket_logger.info("GLPI session started successfully.")
        return session_token

    except Exception as e:
        ticket_logger.error(f"GLPI Session Error: {e}")
        return None


# ---------------------------------------------------
# 2. CREATE TICKET
# ---------------------------------------------------
def glpi_create_ticket(session_token, title, description):
    try:
        headers = {
            "App-Token": APP_TOKEN,
            "Session-Token": session_token,
            "Content-Type": "application/json",
        }

        payload = {
            "input": {
                "name": title,
                "content": description,
                "status": 1,           # 1 = New / Open
                "requesttypes_id": 2,  # Email request
            }
        }

        resp = requests.post(
            GLPI_API_URL + "Ticket",
            headers=headers,
            data=json.dumps(payload)
        )

        if resp.status_code != 201:
            ticket_logger.error(f"Failed to create ticket: {resp.text}")
            return None

        ticket_id = resp.json().get("id")
        ticket_logger.info(f"Ticket Created Successfully: {ticket_id}")
        return ticket_id

    except Exception as e:
        ticket_logger.error(f"GLPI Ticket Creation Error: {e}")
        return None


# ---------------------------------------------------
# 3. ADD FOLLOW-UP NOTE (AI Reply)
# ---------------------------------------------------
def glpi_add_followup(session_token, ticket_id, message):
    try:
        headers = {
            "App-Token": APP_TOKEN,
            "Session-Token": session_token,
            "Content-Type": "application/json",
        }

        payload = {
            "input": {
                "itemtype": "Ticket",
                "items_id": ticket_id,
                "content": message,
            }
        }

        resp = requests.post(
            GLPI_API_URL + f"Ticket/{ticket_id}/ITILFollowup",
            headers=headers,
            data=json.dumps(payload)
        )

        if resp.status_code != 201:
            ticket_logger.error(f"Failed to add follow-up: {resp.text}")
            return False

        ticket_logger.info(f"Follow-up added to Ticket {ticket_id}")
        return True

    except Exception as e:
        ticket_logger.error(f"GLPI Follow-up Error: {e}")
        return False


# ---------------------------------------------------
# 4. CLOSE TICKET (status = 6)
# ---------------------------------------------------
def glpi_close_ticket(session_token, ticket_id):
    """Close GLPI ticket (6 = Solved/Closed)."""
    try:
        headers = {
            "App-Token": APP_TOKEN,
            "Session-Token": session_token,
            "Content-Type": "application/json",
        }

        payload = {
            "input": {
                "id": ticket_id,
                "status": 6,  # Closed
            }
        }

        resp = requests.put(
            GLPI_API_URL + f"Ticket/{ticket_id}",
            headers=headers,
            data=json.dumps(payload)
        )

        if resp.status_code not in (200, 201):
            ticket_logger.error(f"Failed to close ticket {ticket_id}: {resp.text}")
            return False

        ticket_logger.info(f"Ticket {ticket_id} closed successfully.")
        return True

    except Exception as e:
        ticket_logger.error(f"GLPI Close Ticket Error: {e}")
        return False
