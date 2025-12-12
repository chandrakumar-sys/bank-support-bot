import boto3
import pandas as pd
from io import BytesIO
import logging
import os

# S3 bucket and file paths
BUCKET = "banking-ai-datasets"
CUSTOMERS_KEY = "datasets/customers.xlsx"
FEES_KEY = "datasets/fees.xlsx"
LOANS_KEY = "datasets/loans.xlsx"


def load_excel_from_s3(bucket, key):
    """Load and return an Excel file from S3 as a pandas DataFrame."""
    try:
        s3 = boto3.client("s3")
        obj = s3.get_object(Bucket=bucket, Key=key)
        data = obj["Body"].read()

        return pd.read_excel(BytesIO(data))

    except Exception as e:
        logging.error(f"S3 LOAD ERROR for {key}: {e}")
        raise


def load_all_datasets():
    """Load customers, fees, and loans from S3 bucket."""
    logging.info("Loading datasets from S3...")

    customers = load_excel_from_s3(BUCKET, CUSTOMERS_KEY)
    fees = load_excel_from_s3(BUCKET, FEES_KEY)
    loans = load_excel_from_s3(BUCKET, LOANS_KEY)

    logging.info("All datasets loaded successfully.")

    return customers, fees, loans
