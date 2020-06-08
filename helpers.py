"""Helper functions for the Crownstone integration"""


def crownstone_icon_to_mdi(icon: str):
    # strip left and right
    stripped = icon.split('-', 1)[1]
    term = stripped.split('-', 1)[0]

    if term == "crownstone":
        return "mdi:power-socket-de"
    # return an icon with the main term
    return f'mdi:{term}'