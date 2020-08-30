from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot import System, Member

import discord
import humanize
import re

import random
import string
from datetime import datetime, timedelta
from typing import List, Tuple, Union, Optional
from urllib.parse import urlparse

from bot import db
from libs.errors import InvalidAvatarURLError


def display_relative(time: Union[datetime, timedelta]) -> str:
    if isinstance(time, datetime):
        time = datetime.utcnow() - time
    return humanize.naturaldelta(time)


async def get_fronter_ids(conn, system_id) -> (List[int], datetime):
    switches = await db.front_history(conn, system_id=system_id, count=1)
    if not switches:
        return [], None

    if not switches[0]["members"]:
        return [], switches[0]["timestamp"]

    return switches[0]["members"], switches[0]["timestamp"]


async def get_fronters(conn, system_id) -> (List["Member"], datetime):
    member_ids, timestamp = await get_fronter_ids(conn, system_id)

    # Collect in dict and then look up as list, to preserve return order
    members = {member.id: member for member in await db.get_members(conn, member_ids)}
    return [members[member_id] for member_id in member_ids], timestamp


async def get_front_history(conn, system_id, count) -> List[Tuple[datetime, List["pluMember"]]]:
    # Get history from DB
    switches = await db.front_history(conn, system_id=system_id, count=count)
    if not switches:
        return []

    # Get all unique IDs referenced
    all_member_ids = {id for switch in switches for id in switch["members"]}

    # And look them up in the database into a dict
    all_members = {member.id: member for member in await db.get_members(conn, list(all_member_ids))}

    # Collect in array and return
    out = []
    for switch in switches:
        timestamp = switch["timestamp"]
        members = [all_members[id] for id in switch["members"]]
        out.append((timestamp, members))
    return out


def generate_hid() -> str:
    return "".join(random.choices(string.ascii_lowercase, k=5))


def contains_custom_emoji(value):
    return bool(re.search("<a?:\w+:\d+>", value))


def validate_avatar_url_or_raise(url):
    u = urlparse(url)
    if not (u.scheme in ["http", "https"] and u.netloc and u.path):
        raise InvalidAvatarURLError()

    # TODO: check file type and size of image


def escape(s):
    return s.replace("`", "\\`")


def bounds_check_member_name(new_name, system_tag):
    if len(new_name) > 32:
        return "Name cannot be longer than 32 characters."

    if system_tag:
        if len("{} {}".format(new_name, system_tag)) > 32:
            return "This name, combined with the system tag ({}), would exceed the maximum length of 32 characters. Please reduce the length of the tag, or use a shorter name.".format(
                system_tag)


async def parse_mention(client: discord.Client, mention: str) -> Optional[discord.User]:
    # First try matching mention format
    match = re.fullmatch("<@!?(\\d+)>", mention)
    if match:
        try:
            return await client.get_user_info(int(match.group(1)))
        except discord.NotFound:
            return None

    # Then try with just ID
    try:
        return await client.get_user_info(int(mention))
    except (ValueError, discord.NotFound):
        return None


def parse_channel_mention(mention: str, server: discord.Guild) -> Optional[discord.TextChannel]:
    match = re.fullmatch("<#(\\d+)>", mention)
    if match:
        return server.get_channel(int(match.group(1)))

    try:
        return server.get_channel(int(mention))
    except ValueError:
        return None


async def get_system_fuzzy(conn, client: discord.Client, key) -> Optional[System]:
    if isinstance(key, discord.User):
        return await db.get_system_by_account(conn, account_id=key.id)

    if isinstance(key, str) and len(key) == 5:
        return await db.get_system_by_hid(conn, system_hid=key)

    account = await parse_mention(client, key)
    if account:
        system = await db.get_system_by_account(conn, account_id=account.id)
        if system:
            return system
    return None


async def get_member_fuzzy(conn, system_id: int, key: str, system_only=True) -> Member:
    # First search by hid
    if system_only:
        member = await db.get_member_by_hid_in_system(conn, system_id=system_id, member_hid=key)
    else:
        member = await db.get_member_by_hid(conn, member_hid=key)
    if member is not None:
        return member

    # Then search by name, if we have a system
    if system_id:
        member = await db.get_member_by_name(conn, system_id=system_id, member_name=key)
        if member is not None:
            return member


def sanitize(text):
    # Insert a zero-width space in @everyone so it doesn't trigger
    return text.replace("@everyone", "@\u200beveryone").replace("@here", "@\u200bhere")