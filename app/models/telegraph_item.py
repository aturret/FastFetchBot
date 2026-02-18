# Re-export from shared package
from fastfetchbot_shared.models.telegraph_item import *  # noqa: F401,F403
from fastfetchbot_shared.models.telegraph_item import (  # noqa: F401
    TelegraphItem,
    telegraph_item_from_dict,
    telegraph_item_to_dict,
)
