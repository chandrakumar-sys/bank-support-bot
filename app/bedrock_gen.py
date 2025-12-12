import boto3
import json
import logging


bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")


def find_customer_by_email(email, customers_df):
    """Return customer row based on email."""
    row = customers_df[customers_df["email"] == email]
    if row.empty:
        return None
    return row.iloc[0].to_dict()


def find_loan_details(customer_id, fees_df, loans_df):
    """Get fee details and loan details for the customer."""
    loan_row = loans_df[loans_df["customer_id"] == customer_id]
    if loan_row.empty:
        return None

    loan_row = loan_row.iloc[0].to_dict()

    fee_row = fees_df[fees_df["loan_id"] == loan_row["loan_id"]]
    if not fee_row.empty:
        loan_row["fees"] = fee_row.iloc[0].to_dict()
    else:
        loan_row["fees"] = {}

    return loan_row


def build_prompt(customer, loan_info, user_message):
    """Builds a structured prompt for the LLM."""
    name = customer.get("name", "Customer")
    email = customer.get("email", "")

    emi_date = loan_info.get("emi_due_date", "N/A")
    emi_amt = loan_info.get("emi_amount", "N/A")
    emi_status = loan_info.get("emi_status", "N/A")

    fees = loan_info.get("fees", {})

    prompt = f"""
You are a professional banking support AI.

Customer details:
- Name: {name}
- Email: {email}

Loan details:
- EMI Due Date: {emi_date}
- EMI Amount: {emi_amt}
- EMI Status: {emi_status}

Fees:
{json.dumps(fees, indent=2)}

User question:
\"\"\"{user_message}\"\"\"

Write a helpful reply in banking tone. 
Keep it short and factual based only on the above data.
End with:
"Regards,
Bank Support Team"
"""

    return prompt


def call_bedrock(prompt):
    """Invoke Claude Haiku to generate banking email."""
    try:
        response = bedrock.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 500,
                "temperature": 0,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            })
        )

        model_output = json.loads(response["body"].read())
        text = model_output["content"][0]["text"]
        return text

    except Exception as e:
        logging.error(f"BEDROCK ERROR: {e}")
        return "We're unable to process your request right now."


def generate_reply(from_email, user_message, customers, fees, loans):
    """Main entry point: find customer -> find loan -> generate email."""
    customer = find_customer_by_email(from_email, customers)
    if not customer:
        return f"Your email is not registered in our system.\n\nRegards,\nBank Support Team"

    loan_info = find_loan_details(customer["customer_id"], fees, loans)

    if not loan_info:
        return f"We could not find any loan details for your account.\n\nRegards,\nBank Support Team"

    prompt = build_prompt(customer, loan_info, user_message)
    reply = call_bedrock(prompt)
    return reply
