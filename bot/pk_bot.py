import asyncio
import logging
import os
import sys

import aiohttp
import asyncpg
import discord
from discord.ext import commands

from bot import db
from libs import channel_logger, proxy


def connect_to_database() -> asyncpg.pool.Pool:
    username = os.environ["DATABASE_USER"]
    password = os.environ["DATABASE_PASS"]
    name = os.environ["DATABASE_NAME"]
    host = os.environ["DATABASE_HOST"]
    port = os.environ["DATABASE_PORT"]

    if username is None or password is None or name is None or host is None or port is None:
        print(
            "Database credentials not specified. Please pass valid PostgreSQL database credentials in the "
            "DATABASE_[USER|PASS|NAME|HOST|PORT] environment variable.",
            file=sys.stderr)
        sys.exit(1)

    try:
        port = int(port)
    except ValueError:
        print("Please pass a valid integer as the DATABASE_PORT environment variable.", file=sys.stderr)
        sys.exit(1)

    return asyncio.get_event_loop().run_until_complete(db.connect(
        username=username,
        password=password,
        database=name,
        host=host,
        port=port
    ))


class PluralKitBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super(PluralKitBot, self).__init__(*args, **kwargs)
        self.db = connect_to_database()
        self.logger = channel_logger.ChannelLogger(self)

    async def start(self, *args, **kwargs):
        """|coro|
        A shorthand coroutine for :meth:`login` + :meth:`connect`.
        Raises
        -------
        TypeError
            An unexpected keyword argument was received.
        """
        bot = kwargs.pop('bot', True)
        reconnect = kwargs.pop('reconnect', True)

        if kwargs:
            raise TypeError("unexpected keyword argument(s) %s" % list(kwargs.keys()))

        for i in range(0, 6):
            try:
                await self.login(*args, bot=bot)
                break
            except aiohttp.ClientConnectionError as e:
                logging.warning(f"bot:Connection {i}/6 failed")
                logging.warning(f"bot:  {e}")
                logging.warning(f"bot: waiting {2 ** (i + 1)} seconds")
                await asyncio.sleep(2 ** (i + 1))
                logging.info("bot:attempting to reconnect")
        else:
            logging.error("bot: FATAL failed after 6 attempts")
            return

        logging.info("Making database tables")
        async with self.db.acquire() as conn:
            await db.create_tables(conn)

        await self.connect(reconnect=reconnect)

    async def on_message(self, message: discord.Message):
        # Ignore messages from bots
        if message.author.bot:
            return
        async with self.db.acquire() as conn:
            ctx: commands.Context = await self.get_context(message, cls=commands.Context)
            await self.invoke(ctx)
            if not ctx.command:
                await proxy.try_proxy_message(conn, message, self.logger, self.user)
