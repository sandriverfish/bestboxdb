import os
from dotenv import load_dotenv

load_dotenv()


class SmartTradeConfig:
    server:      str = os.environ["SMARTTRADE_SERVER"]
    port:        str = os.environ["SMARTTRADE_PORT"]
    database:    str = os.environ["SMARTTRADE_DATABASE"]
    user:        str = os.environ["SMARTTRADE_USER"]
    password:    str = os.environ["SMARTTRADE_PASSWORD"]
    driver:      str = os.environ.get("SMARTTRADE_DRIVER", "SQL Server")
    trust_cert:  str = os.environ.get("SMARTTRADE_TRUST_CERT", "no")

    @classmethod
    def connection_string(cls) -> str:
        return (
            f"DRIVER={{{cls.driver}}};"
            f"SERVER={cls.server},{cls.port};"
            f"DATABASE={cls.database};"
            f"UID={cls.user};"
            f"PWD={cls.password};"
            f"TrustServerCertificate={cls.trust_cert};"
        )
