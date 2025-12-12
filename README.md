# Banking AI Auto-Reply Bot

This project is an automated banking support bot that:

- Reads unread emails from Gmail
- Identifies the customer using S3 datasets
- Detects the customer's loan / EMI details
- Generates a reply using AWS Bedrock (Claude 3 Haiku)
- Sends a professional email response
- Runs continuously inside a Docker container

---

## 📂 Project Structure
bank-support-bot/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env (not uploaded - used only on EC2)
├── app/
│ ├── main.py
│ ├── bedrock_gen.py
│ ├── s3_loader.py
│ └── init.py
├── logs/
│ └── .gitkeep
└── README.md
