# Simple Login SMTP Relay

SMTP relay for Simple Login.

Will relay all your emails sent to the relay to your actual mailbox (e.g. gmail), replacing all recipient emails with revert alias.

Only supports custom domain or custom subdomain.
## Steps
1. copy `config.py.example` to `config.py` and replace variables
2. `python server.py`
3. then use it like a regular smtp server:
```python
server = smtplib.SMTP("relay_server", 8025)
server.starttls()
server.login("some_really_cool_username", "password")
server.sendmail("any_alias@your_domain.com", ["any_recipient@example.com"], """
From: Someone <any_alias@your_domain.com>
To: any_recipient@example.com
Subject: A test

Hi Bart, this is Anne.
""")
```
