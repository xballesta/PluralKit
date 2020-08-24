import asyncio
import dotenv
from pluralkit import bot
import os

dotenv.load_dotenv(os.getenv("ENV"))

try:
    # uvloop doesn't work on Windows, therefore an optional dependency
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

bot.run()