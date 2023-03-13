from email.message import EmailMessage, Message
from email.utils import formataddr, parseaddr
from typing import List, Optional

import requests

import config

aliases = []
contacts = {}


def get_alias_id(alias: str) -> Optional[int]:
    if not any([alias.endswith(s) for s in config.suffixes]):
        return None
    global aliases
    if aliases == []:
        page_id = 0
        while True:
            resp = requests.get(
                f"{config.host}/api/v2/aliases?page_id={page_id}",
                headers={"Authentication": config.apikey},
            ).json()["aliases"]
            aliases += resp
            if resp == [] or len(resp) != 20:
                break
            page_id += 1
    for a in aliases:
        if a["email"] == alias:
            return a["id"]
    # create a new alias
    options = requests.get(
        f"{config.host}/api/v5/alias/options", headers={"Authentication": config.apikey}
    ).json()
    suffix = None
    for s in options["suffixes"]:
        if alias.endswith(s["suffix"]):
            suffix = s
            break
    if suffix is None:
        return None
    resp = requests.post(
        f"{config.host}/api/v3/alias/custom/new",
        headers={
            "Authentication": config.apikey,
        },
        json={
            "alias_prefix": alias.replace(suffix["suffix"], ""),
            "signed_suffix": suffix["signed_suffix"],
            "mailbox_ids": [config.mailbox_id],
        },
    ).json()
    if "error" in resp:
        if "already exists" in resp["error"]:
            aliases = []
            return get_alias_id(alias)
        else:
            print(resp)
            return None
    aliases.append(resp)
    return resp["id"]


def get_contact_alias(alias: str, to: List[str]) -> Optional[List[str]]:
    alias_id = get_alias_id(alias)
    if alias_id is None:
        return None
    # get contacts
    page_id = 0
    global contacts
    if alias_id not in contacts:
        ncontacts = []
        while True:
            resp = requests.get(
                f"{config.host}/api/aliases/{alias_id}/contacts?page_id={page_id}",
                headers={
                    "Authentication": config.apikey,
                },
            ).json()["contacts"]
            ncontacts += resp
            if resp == [] or len(resp) != 20:
                break
            page_id += 1
        ncontacts = {i["contact"]: i for i in ncontacts}
        contacts[alias_id] = ncontacts
    for j in range(len(to)):
        if to[j][1] in contacts[alias_id]:
            to[j] = contacts[alias_id][to[j][1]]["reverse_alias"]
        else:
            print(to[j])
            # create a new alias
            # POST /api/aliases/:alias_id/contacts
            resp = requests.post(
                f"{config.host}/api/aliases/{alias_id}/contacts",
                headers={
                    "Authentication": config.apikey,
                },
                json={"contact": formataddr(to[j])},
            ).json()
            print(resp)
            contacts[alias_id][resp["contact"]] = resp
            to[j] = resp["reverse_alias"]
    return to


def add_or_replace_header(msg: Message, header: str, value: str):
    """
    Remove all occurrences of `header` and add `header` with `value`.
    """
    delete_header(msg, header)
    msg[header] = value


def delete_header(msg: Message, header: str):
    """a header can appear several times in message."""
    # inspired from https://stackoverflow.com/a/47903323/1428034
    for i in reversed(range(len(msg._headers))):
        header_name = msg._headers[i][0].lower()
        if header_name == header.lower():
            del msg._headers[i]


def sanitize_header(msg: Message, header: str):
    """remove trailing space and remove linebreak from a header"""
    for i in reversed(range(len(msg._headers))):
        header_name = msg._headers[i][0].lower()
        if header_name == header.lower():
            # msg._headers[i] is a tuple like ('From', 'hey@google.com')
            if msg._headers[i][1]:
                msg._headers[i] = (
                    msg._headers[i][0],
                    msg._headers[i][1].strip().replace("\n", " "),
                )


def sanitize_email(email_address: str, not_lower=False) -> str:
    if email_address:
        email_address = email_address.strip().replace(" ", "").replace("\n", " ")
        if not not_lower:
            email_address = email_address.lower()
    return email_address
