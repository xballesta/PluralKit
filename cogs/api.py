from __future__ import annotations

from typing import TYPE_CHECKING
from bot.context import CommandContext

from discord.ext import commands

disclaimer = "Please note that this grants access to modify (and delete!) all your system data, " \
             "so keep it safe and secure. If it leaks or you need a new one, you can invalidate this " \
             "one with `pk;token refresh`."


class ApiCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group()
    async def token(self, ctx: CommandContext):
        if not ctx.invoked_subcommand:
            system = await ctx.ensure_system()

            if system.token:
                token = system.token
            else:
                token = await system.refresh_token(ctx.conn)

            token_message = "Here's your API token: \n**`{}`**\n{}".format(token, disclaimer)
            return await ctx.reply_ok_dm(token_message)

    @commands.command(
        name="update",
        aliases=["refresh", "expire", "invalidate"]
    )
    async def token_refresh(self, ctx: CommandContext):
        system = await ctx.ensure_system()

        token = await system.refresh_token(ctx.conn)
        token_message = "Your previous API token has been invalidated. You will need to change it anywhere " \
                        "it's currently " \
                        "used.\nHere's your new API token:\n**`{}`**\n{}".format(token, disclaimer)
        return await ctx.reply_ok_dm(token_message)


def setup(bot):
    bot.add_cog(ApiCog(bot))
