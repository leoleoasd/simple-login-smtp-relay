import asyncio
import email
import logging
import ssl
from email.message import Message
from email.utils import getaddresses, parseaddr
from smtplib import SMTP as SMTPCLient

from aiosmtpd.controller import Controller
from aiosmtpd.smtp import AuthResult, LoginPassword

import config
from utils import (
    add_or_replace_header,
    get_contact_alias,
    sanitize_email,
    sanitize_header,
)

DEST_PORT = 25


class Authenticator:
    def __call__(self, server, session, envelope, mechanism, auth_data):
        fail_nothandled = AuthResult(success=False, handled=False)
        if mechanism not in ("LOGIN", "PLAIN"):
            return fail_nothandled
        if not isinstance(auth_data, LoginPassword):
            return fail_nothandled
        username = auth_data.login.decode("utf-8")
        password = auth_data.password.decode("utf-8")
        if username != config.username or password != config.password:
            return AuthResult(
                success=False, handled=True, message="Invalid username or password"
            )
        return AuthResult(success=True, handled=True)


def get_from_header(msg: Message, header: str):
    """
    Replace CC or To Reply emails by original emails
    """
    new_addrs: [str] = []
    headers = msg.get_all(header, [])
    # headers can be an array of Header, convert it to string here
    headers = [str(h) for h in headers]

    # headers can contain \r or \n
    headers = [h.replace("\r", "") for h in headers]
    headers = [h.replace("\n", "") for h in headers]
    return getaddresses(headers)


class RelayHandler:
    async def handle_DATA(self, server, session, envelope):
        msg = email.message_from_bytes(envelope.original_content)
        print(msg)

        # sanitize email headers
        sanitize_header(msg, "from")
        sanitize_header(msg, "to")
        sanitize_header(msg, "cc")
        sanitize_header(msg, "reply-to")
        mail_from = sanitize_email(envelope.mail_from)
        rcpt_tos = [parseaddr(sanitize_email(rcpt_to)) for rcpt_to in envelope.rcpt_tos]
        envelope.mail_from = mail_from
        envelope.rcpt_tos = rcpt_tos

        if str(msg["To"]).lower() == "undisclosed-recipients:;":
            # no need to replace TO header
            del msg["To"]
        else:
            # replace_header_when_reply(copy_msg, alias, 'To')
            new_addrs = get_contact_alias(mail_from, get_from_header(msg, "To"))
            if new_addrs:
                add_or_replace_header(msg, "to", ",".join(new_addrs))

        new_addrs = get_contact_alias(mail_from, get_from_header(msg, "cc"))
        if new_addrs:
            add_or_replace_header(msg, "cc", ",".join(new_addrs))
        rcpt_tos = get_contact_alias(mail_from, rcpt_tos)
        print("new_message", msg.as_string())

        with SMTPCLient(config.smtp_host, config.smtp_port) as client:
            client.ehlo()
            client.starttls()
            client.login(config.smtp_username, config.smtp_password)
            client.sendmail(config.smtp_from, rcpt_tos, msg.as_bytes())
        return "250 Message accepted for delivery"


# noinspection PyShadowingNames
async def amain():
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    if config.ssl:
        context.load_cert_chain(config.cert, config.key)
    handler = RelayHandler()
    cont = Controller(
        handler,
        hostname="",
        port=8025,
        authenticator=Authenticator(),
        auth_required=True,
        auth_require_tls=config.ssl,
        require_starttls=config.ssl,
        tls_context=context,
    )
    cont.start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(amain())
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("User abort indicated")
