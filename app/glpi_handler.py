import logging
from app.glpi_client import (
    glpi_start_session,
    glpi_create_ticket,
    glpi_add_followup,
    glpi_close_ticket
)

# ------------------------------------------
# Ticket Logger (separate log file)
# ------------------------------------------
ticket_logger = logging.getLogger("ticket_logger")
handler = logging.FileHandler("logs/ticket.log")
handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
ticket_logger.addHandler(handler)
ticket_logger.setLevel(logging.INFO)

# Map user → last ticket ID (POC only)
_last_ticket_map = {}


# ----------------------------------------------------------
# AUTO-CLOSE detection (improved — no false triggers)
# ----------------------------------------------------------
def customer_wants_close(message):
    """Only close when user clearly confirms resolution."""
    message = message.lower().strip()

    strong_close_phrases = [
        "issue resolved",
        "this is resolved",
        "problem solved",
        "you can close the ticket",
        "please close the ticket",
        "the issue is fixed",
        "yes resolved",
        "now it's resolved",
        "everything is fixed"
    ]

    return any(phrase in message for phrase in strong_close_phrases)


# ----------------------------------------------------------
# Helper: Get/Set last ticket
# ----------------------------------------------------------
def get_last_ticket_id_for_user(email):
    return _last_ticket_map.get(email)


def set_last_ticket_user(email, ticket_id):
    _last_ticket_map[email] = ticket_id


# ----------------------------------------------------------------
# MAIN TICKETING HANDLER
# ----------------------------------------------------------------
def process_ticketing(from_email, user_message, ai_reply, intents):
    """
    Handles:
    - Auto-close detection
    - New ticket creation
    - Follow-up on existing ticket
    - Inject ticket ID into AI reply
    """
    user_email = from_email.strip().lower()

    # ---------------------------------------
    # 1️⃣ AUTO-CLOSE LOGIC
    # ---------------------------------------
    if customer_wants_close(user_message):
        ticket_logger.info(f"[AUTO-CLOSE REQUEST] From: {user_email}")

        session = glpi_start_session()
        if not session:
            ticket_logger.error("Auto-close failed: cannot start session.")
            return None, "Your ticket is resolved. (But auto-close failed.)"

        last_ticket = get_last_ticket_id_for_user(user_email)
        if not last_ticket:
            ticket_logger.error(f"No ticket found to close for {user_email}")
            return None, "Your issue is marked as resolved."

        # Close ticket
        glpi_close_ticket(session, last_ticket)
        ticket_logger.info(f"[AUTO-CLOSED] Ticket #{last_ticket} for {user_email}")

        reply = (
            f"Your ticket #{last_ticket} has been closed.\n\n"
            "If you need anything else, feel free to contact us again.\n\n"
            "Regards,\nBank Support Team"
        )
        return last_ticket, reply

    # ---------------------------------------
    # 2️⃣ CHECK IF USER ALREADY HAS A TICKET
    # (Send follow-up instead of creating new)
    # ---------------------------------------
    existing_ticket = get_last_ticket_id_for_user(user_email)

    if existing_ticket:
        session = glpi_start_session()
        if session:
            glpi_add_followup(session, existing_ticket, f"Customer reply:\n{user_message}")
            glpi_add_followup(session, existing_ticket, f"AI reply:\n{ai_reply}")

            ticket_logger.info(
                f"[FOLLOW-UP] Added follow-up to Ticket #{existing_ticket} for {user_email}"
            )

            final_reply = (
                ai_reply
                + f"\n\nTicket Reference ID: #{existing_ticket}\n(Your message has been added as a follow-up)"
            )

            return existing_ticket, final_reply

    # ---------------------------------------
    # 3️⃣ CREATE NEW TICKET
    # ---------------------------------------
    session = glpi_start_session()
    if not session:
        ticket_logger.error("GLPI session startup failed.")
        return None, ai_reply + "\n\n(Note: Ticketing system unavailable.)"

    title = f"Loan Support Request - {user_email}"

    description = f"""
Customer Email: {user_email}

Message:
{user_message}

Intents: {", ".join(intents)}

AI Reply:
{ai_reply}
"""

    ticket_id = glpi_create_ticket(session, title, description)

    if not ticket_id:
        ticket_logger.error(f"Failed to create ticket for {user_email}")
        return None, ai_reply + "\n\n(Note: Could not create ticket.)"

    # Save mapping for POC
    set_last_ticket_user(user_email, ticket_id)

    # Add AI reply as follow-up
    glpi_add_followup(session, ticket_id, f"AI Response:\n{ai_reply}")

    ticket_logger.info(f"[CREATED] Ticket #{ticket_id} for {user_email}")

    # Inject Ticket ID into customer email
    final_reply = (
        ai_reply
        + f"\n\nTicket Reference ID: #{ticket_id}\n(Use this ID for any follow-up queries)"
    )

    return ticket_id, final_reply
