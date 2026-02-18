# Re-export from shared package
from fastfetchbot_shared.utils.network import *  # noqa: F401,F403
from fastfetchbot_shared.utils.network import (  # noqa: F401
    get_response,
    get_response_json,
    get_selector,
    get_redirect_url,
    get_content_async,
    download_file_by_metadata_item,
    download_file_to_local,
    get_random_user_agent,
    HEADERS,
)
