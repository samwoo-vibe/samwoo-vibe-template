import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["APP_BASE_URL"] = "https://app.example.invalid"
