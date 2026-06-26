import os
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOTENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path=DOTENV_PATH)


class Settings(BaseSettings):
    SECRET_KEY: str = "supersecretkey"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    DATABASE_URL: str = "postgresql://user:password@localhost/business_suite_db"
    DATABASE_NAME: str = "business_suite_db"
    API_HOST: str = "https://us-west-2.api.thenile.dev/v2/databases/019ed429-f542-7277-a13f-29f08d50a550"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_API_KEY2: str = ""
    
    ACCOUNTS_OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    EVENT_BUS_URL: str = "memory://local"
    ENVIRONMENT: str = "development"
    RAZORPAY_KEY_ID: str = "rzp_test_T5O7M81YGrowq2"
    RAZORPAY_KEY_SECRET: str = "E7H9HK1GZNMknGHeb9E0h1PX"

    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173"

    model_config = ConfigDict(env_file=DOTENV_PATH, extra="ignore")


settings = Settings()
