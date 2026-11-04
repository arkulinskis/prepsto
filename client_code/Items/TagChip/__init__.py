from anvil import *

from ._anvil_designer import TagChipTemplate


class TagChip(TagChipTemplate):
    """A small tag in a feedback row or a board card. item = the text to show ("#onboarding")."""

    def __init__(self, **properties):
        super().__init__(**properties)
