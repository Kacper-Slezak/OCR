# check_mail_config.py
from dotenv import load_dotenv
import os
load_dotenv()  # подхватывает .env из рабочего каталога

print("EMAIL_HOST       →", os.getenv('EMAIL_HOST'))
print("EMAIL_PORT       →", os.getenv('EMAIL_PORT'))
print("EMAIL_USE_TLS    →", os.getenv('EMAIL_USE_TLS'))
print("EMAIL_USER       →", os.getenv('EMAIL_USER'))

from config import Config
cfg = Config()
print("\nConfig.MAIL_SERVER     →", cfg.MAIL_SERVER)
print("Config.MAIL_PORT       →", cfg.MAIL_PORT)
print("Config.MAIL_USE_TLS    →", cfg.MAIL_USE_TLS)
print("Config.MAIL_USERNAME   →", cfg.MAIL_USERNAME)
print("Config.MAIL_DEFAULT_SENDER →", cfg.MAIL_DEFAULT_SENDER)
