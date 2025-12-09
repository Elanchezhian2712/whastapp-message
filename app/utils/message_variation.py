# app/utils/message_variation.py
import random


def mutate_message(template: str, name: str = "", link: str = "") -> str:
    """
    Replaces placeholders only if they exist in the template.
    Prevents {name} and {link} from appearing when not desired.
    """

    msg = template

    # Replace only if placeholder exists
    if "{name}" in msg:
        msg = msg.replace("{name}", name.strip())

    if "{link}" in msg:
        msg = msg.replace("{link}", link.strip())

    # Clean leftover braces
    msg = msg.replace("{", "").replace("}", "")

    return msg.strip()

