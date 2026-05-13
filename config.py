import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token from @BotFather
BOT_TOKEN = os.getenv('BOT_TOKEN')

# The Name of Your Bot
BOT_NAME = 'TamilanScrapper_bot'

# Your Telegram User ID
ADMIN_ID = int(os.getenv('ADMIN_ID', 1072002664))

# Database connection string
DATABASE_URL = os.getenv('DATABASE_URL')
