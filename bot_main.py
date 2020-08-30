import asyncio
import logging
import os
import sys
import traceback

import discord
import dotenv

from bot.pk_bot import PluralKitBot
from libs import proxy, embeds

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s")

dotenv.load_dotenv(os.getenv("ENV"))

try:
    # uvloop doesn't work on Windows, therefore an optional dependency
    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

bot = PluralKitBot(command_prefix="pk;")
ext = [
    "cogs.api"
]

for e in ext:
    bot.load_extension(e)

@bot.event
async def on_raw_message_delete(payload: discord.RawMessageDeleteEvent):
    async with bot.db.acquire() as conn:
        await proxy.handle_deleted_message(conn, bot, payload.message_id, None)


@bot.event
async def on_raw_bulk_message_delete(payload: discord.RawBulkMessageDeleteEvent):
    async with bot.db.acquire() as conn:
        for message_id in payload.message_ids:
            await proxy.handle_deleted_message(conn, bot, message_id, None)


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.emoji.name == "\u274c":  # Red X
        async with bot.db.acquire() as conn:
            await proxy.try_delete_by_reaction(conn, bot, payload.message_id, payload.user_id)


@bot.event
async def on_error(event_name, *args, **kwargs):
    log_channel_id = os.environ.get("LOG_CHANNEL")
    if not log_channel_id:
        return

    log_channel = bot.get_channel(int(log_channel_id))

    # If this is a message event, we can attach additional information in an event
    # ie. username, channel, content, etc
    if args and isinstance(args[0], discord.Message):
        message: discord.Message = args[0]
        embed = embeds.exception_log(
            message.content,
            message.author.name,
            message.author.discriminator,
            message.author.id,
            message.guild.id if message.guild else None,
            message.channel.id
        )
    else:
        # If not, just post the string itself
        embed = None

    if sys.exc_info()[0].__name__ == "MissingPermissions":
        await message.channel.send(str(sys.exc_info()[1]))

    traceback_str = "```python\n{}```".format(traceback.format_exc())
    if len(traceback.format_exc()) >= (2000 - len("```python\n```")):
        traceback_str = "```python\n...{}```".format(
            traceback.format_exc()[- (2000 - len("```python\n...```")):])
    await log_channel.send(content=traceback_str, embed=embed)

    # Print it to stderr anyway, though
    logging.getLogger("pluralkit").exception("Exception while handling event {}".format(event_name))


bot.run(os.getenv("TOKEN"))