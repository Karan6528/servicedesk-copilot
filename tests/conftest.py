import os

# Never read the developer's .env during tests (no real ServiceNow / Power Automate calls).
os.environ["SDC_SKIP_DOTENV"] = "1"
