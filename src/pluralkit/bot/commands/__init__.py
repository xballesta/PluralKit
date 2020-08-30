import asyncio
from datetime import datetime

import discord
import re
from typing import Tuple, Optional, Union


from libs import utils
from libs.errors import PluralKitError, PermError
from bot.classes.member import Member
from bot.classes.system import System


def next_arg(arg_string: str) -> Tuple[str, Optional[str]]:
    # A basic quoted-arg parser
    
    for quote in "“‟”":
        arg_string = arg_string.replace(quote, "\"")

    if arg_string.startswith("\""):
        end_quote = arg_string[1:].find("\"") + 1
        if end_quote > 0:
            return arg_string[1:end_quote], arg_string[end_quote + 1:].strip()
        else:
            return arg_string[1:], None

    next_space = arg_string.find(" ")
    if next_space >= 0:
        return arg_string[:next_space].strip(), arg_string[next_space:].strip()
    else:
        return arg_string.strip(), None


class CommandError(Exception):
    def __init__(self, text: str, help: Tuple[str, str] = None):
        self.text = text
        self.help = help

    def format(self):
        return "\u274c " + self.text, embeds.error("", self.help) if self.help else None


class CommandContext:
    def __init__(self, client: bot.PluralKitBot, message: discord.Message, conn, args: str, system: Optional[System]):
        self.client = client
        self.message = message
        self.conn = conn
        self.args = args
        self._system = system

    async def has_role(self, role_id: int):
        if not self.message.guild:
            return False
        author: discord.Member = self.message.author
        for r in author.roles:
            if r.id == role_id:
                return True
        raise PermError(f"You don't have the correct permissions to run this command! If you think this is an error, please contact a server admin.")

    async def get_system(self) -> Optional[System]:
        return self._system

    async def ensure_system(self) -> System:
        system = await self.get_system()

        if not system:
            raise CommandError("No system registered to this account. Use `pk;system new` to register one.")

        return system

    def has_next(self) -> bool:
        return bool(self.args)

    def format_time(self, dt: datetime):
        if self._system:
            return self._system.format_time(dt)
        return dt.isoformat(sep=" ", timespec="seconds") + " UTC"

    def pop_str(self, error: CommandError = None) -> Optional[str]:
        if not self.args:
            if error:
                raise error
            return None

        popped, self.args = next_arg(self.args)
        return popped

    def peek_str(self) -> Optional[str]:
        if not self.args:
            return None
        popped, _ = next_arg(self.args)
        return popped

    def match(self, next) -> bool:
        peeked = self.peek_str()
        if peeked and peeked.lower() == next.lower():
            self.pop_str()
            return True
        return False

    async def pop_system(self, error: CommandError = None) -> System:
        name = self.pop_str(error)
        system = await utils.get_system_fuzzy(self.conn, self.client, name)

        if not system:
            raise CommandError("Unable to find system '{}'.".format(name))

        return system

    async def pop_member(self, error: CommandError = None, system_only: bool = True) -> Member:
        name = self.pop_str(error)

        if system_only:
            system = await self.ensure_system()
        else:
            system = await self.get_system()

        member = await utils.get_member_fuzzy(self.conn, system.id if system else None, name, system_only)
        if not member:
            raise CommandError("Unable to find member '{}'{}.".format(name, " in your system" if system_only else ""))

        return member

    def remaining(self):
        return self.args

    async def reply(self, content=None, embed=None):
        return await self.message.channel.send(content=content, embed=embed)

    async def reply_ok(self, content=None, embed=None):
        return await self.reply(content="\u2705 {}".format(content or ""), embed=embed)

    async def reply_warn(self, content=None, embed=None):
        return await self.reply(content="\u26a0 {}".format(content or ""), embed=embed)

    async def reply_ok_dm(self, content: str):
        if isinstance(self.message.channel, discord.DMChannel):
            await self.reply_ok(content="\u2705 {}".format(content or ""))
        else:
            await self.message.author.send(content="\u2705 {}".format(content or ""))
            await self.reply_ok("DM'd!")

    async def confirm_react(self, user: Union[discord.Member, discord.User], message: discord.Message):
        await message.add_reaction("\u2705")  # Checkmark
        await message.add_reaction("\u274c")  # Red X

        try:
            reaction, _ = await self.client.wait_for("reaction_add",
                                                     check=lambda r, u: u.id == user.id and r.emoji in ["\u2705",
                                                                                                        "\u274c"],
                                                     timeout=60.0 * 5)
            return reaction.emoji == "\u2705"
        except asyncio.TimeoutError:
            raise CommandError("Timed out - try again.")

    async def confirm_text(self, user: discord.Member, channel: discord.TextChannel, confirm_text: str, message: str):
        await self.reply(message)

        try:
            message = await self.client.wait_for("message",
                                                 check=lambda m: m.channel.id == channel.id and m.author.id == user.id,
                                                 timeout=60.0 * 5)
            return message.content.lower() == confirm_text.lower()
        except asyncio.TimeoutError:
            raise CommandError("Timed out - try again.")

