import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

CATEGORY_VC_MAPPING = {
    847514411471994890: "モクモク",
    860122345339093014: "ノンビリ",
    847514334460248084: "ワイワイ"
}

ADMIN_ROLE_ID = 946432769242845224