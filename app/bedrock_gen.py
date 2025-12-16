import boto3
import json
import logging
import re

# -----------------------------------------------------------
# GLOBALS
# -----------------------------------------------------------

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

# In-memory conversation tracking
conversation_history = {}

# -----------------------------------------------------------
# EMAIL NORMALIZATION
# -----------------------------------------------------------

def normalize_email(raw_email):
    """Extract and clean email (Gmail format safe)."""
    if not raw_email:
        return None

    # Extract <email> if present
    match = re.search(r"<(.+?)>", raw_email)
    email_clean = match.group(1) if match else raw_email

    # Trim + lowercase
    email_clean = email_clean.strip().lower()

    return email_clean if "@" in email_clean else None


# -----------------------------------------------------------
# CONVERSATION MEMORY HANDLERS
# -----------------------------------------------------------

def get_history(email):
    """Return last 3 user+assistant messages."""
    hist = conversation_history.get(email, [])
    return hist[-6:]   # last 3 pairs (6 messages)


def add_to_history(email, role, message):
    """Store message for short-term memory."""
    conversation_history.setdefault(email, [])
    conversation_history[email].append({"role": role, "text": message})

    # Prevent memory from growing too large
    if len(conversation_history[email]) > 12:
        conversation_history[email] = conversation_history[email][-12:]


# -----------------------------------------------------------
# INTENT DETECTION (Rule-based)
# -----------------------------------------------------------

def detect_intents(message):
    message = message.lower()
    intents = []

    if any(k in message for k in ["emi", "due date", "next emi"]):
        intents.append("emi_due_date")

    if any(k in message for k in ["emi amount", "how much", "monthly amount"]):
        intents.append("emi_amount")

    if any(k in message for k in ["status", "paid", "payment status"]):
        intents.append("emi_status")

    if any(k in message for k in ["fee", "charges", "late fee", "penalty"]):
        intents.append("fee_details")

    if "statement" in message:
        intents.append("loan_statement")

    if not intents:
        intents.append("general_query")

    return intents


# -----------------------------------------------------------
# CUSTOMER VALIDATION
# -----------------------------------------------------------

def find_customer_by_email(raw_email, customers_df):
    """Match customer email ignoring <>, spaces, and case differences."""
    clean_email = normalize_email(raw_email)
    if not clean_email:
        return None

    df = customers_df.copy()
    df["email_clean"] = df["email"].astype(str).str.strip().str.lower()

    match = df[df["email_clean"] == clean_email]

    if match.empty:
        return None

    return match.iloc[0].to_dict()


# -----------------------------------------------------------
# LOAN LOOKUP
# -----------------------------------------------------------

def find_loan_details(customer_id, fees_df, loans_df):
    loan_row = loans_df[loans_df["customer_id"] == customer_id]
    if loan_row.empty:
        return None

    loan_row = loan_row.iloc[0].to_dict()

    fee_row = fees_df[fees_df["loan_id"] == loan_row["loan_id"]]
    loan_row["fees"] = fee_row.iloc[0].to_dict() if not fee_row.empty else {}

    return loan_row


# -----------------------------------------------------------
# PROMPT BUILDER
# -----------------------------------------------------------

def build_prompt(customer, loan_info, user_message, intents, history):
    fee_text = json.dumps(loan_info.get("fees", {}), indent=2)

    # Build conversation transcript
    history_text = ""
    for h in history:
        history_text += f"{h['role'].upper()}: {h['text']}\n"

    prompt = f"""
You are a professional banking support AI. Your replies must be factual, courteous, and based only on the loan data provided below.

---------------------------------
CONVERSATION HISTORY
---------------------------------
{history_text if history_text else "None"}

---------------------------------
CUSTOMER DETAILS
---------------------------------
Name: {customer['name']}
Email: {customer['email']}

---------------------------------
LOAN DETAILS
---------------------------------
Loan ID: {loan_info['loan_id']}
EMI Due Date: {loan_info['emi_due_date']}
EMI Amount: {loan_info['emi_amount']}
EMI Status: {loan_info['emi_status']}
Last Payment Date: {loan_info['last_payment_date']}

---------------------------------
FEE DETAILS
---------------------------------
{fee_text}

---------------------------------
DETECTED INTENTS
---------------------------------
{", ".join(intents)}

---------------------------------
CUSTOMER MESSAGE
---------------------------------
\"\"\"{user_message}\"\"\"


---------------------------------
REPLY INSTRUCTIONS
---------------------------------
- Answer in banking tone.
- Address every detected intent clearly.
- Use bullet points if multiple intents.
- Do NOT invent any data.
- Maintain conversation continuity using history.
- Keep reply concise.
- End with:

Regards,
Bank Support Team

Return ONLY the email body.
"""

    return prompt


# -----------------------------------------------------------
# CALL BEDROCK
# -----------------------------------------------------------

def call_bedrock(prompt):
    try:
        response = bedrock.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 450,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}]
            })
        )

        out = json.loads(response["body"].read())
        return out["content"][0]["text"]

    except Exception as e:
        logging.error(f"BEDROCK ERROR: {e}")
        return (
            "We are unable to process your request at the moment.\n\n"
            "Regards,\nBank Support Team"
        )


# -----------------------------------------------------------
# MAIN ENTRY POINT
# -----------------------------------------------------------

def generate_reply(from_email, user_message, customers, fees, loans):
    logging.info(f"Processing email from {from_email}")

    # 1️⃣ Customer lookup
    customer = find_customer_by_email(from_email, customers)
    if not customer:
        return (
            "Your email ID is not registered with our bank. "
            "Please contact support to update your records.\n\nRegards,\nBank Support Team"
        )

    # 2️⃣ Loan details
    loan_info = find_loan_details(customer["customer_id"], fees, loans)
    if not loan_info:
        return (
            f"Dear {customer['name']},\n\n"
            "We could not find any active loan linked to your account.\n\n"
            "Regards,\nBank Support Team"
        )

    # 3️⃣ Intent detection
    intents = detect_intents(user_message)

    # 4️⃣ Conversation history
    history = get_history(from_email)

    # 5️⃣ Build prompt
    prompt = build_prompt(customer, loan_info, user_message, intents, history)

    # 6️⃣ Get LLM reply
    reply = call_bedrock(prompt)

    # 7️⃣ Update memory
    add_to_history(from_email, "user", user_message)
    add_to_history(from_email, "assistant", reply)

    return reply