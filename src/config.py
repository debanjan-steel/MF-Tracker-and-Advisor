"""
config.py — Central configuration loaded from environment variables.
All secrets (Supabase URL/key, WhatsApp tokens) live in .env only.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # --- App ---
    app_name: str = "MF Analytics Platform"
    debug: bool = False

    # --- Supabase ---
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_publishable_key: str = ""
    supabase_secret_key: str = ""
    supabase_jwks_url: str = ""

    # --- WhatsApp (Twilio) ---
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""   # e.g. whatsapp:+14155238886

    # --- Data Sources ---
    mfapi_base_url: str = "https://api.mfapi.in/mf"
    amfi_nav_url: str = "https://portal.amfiindia.com/spages/NAVAll.txt"
    amfi_scheme_master_url: str = "https://portal.amfiindia.com/spages/NAVAll.txt"

    # --- Macro Tickers (via yfinance) ---
    macro_tickers: list[str] = [
        "BZ=F",        # Brent Crude Oil
        "^INDIAVIX",   # India Volatility Index
        "^TNX",        # US 10-Year Treasury Yield
        "DX-Y.NYB",    # US Dollar Index (DXY)
        "USDINR=X",    # USD/INR Exchange Rate
        "GC=F",        # Gold Futures
        "^NSEI",       # Nifty 50
        "^NSMIDCP",    # Nifty Midcap 150
    ]

    # --- Local DB ---
    db_path: str = "data/mf_platform.db"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()

