"""
Constants and shared configurations for FBTools.

This module centralizes all constant values, headers, and configurations
used throughout the library to avoid duplication and ease maintenance.
"""

# Default User Agents
USER_AGENT_WINDOWS = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/120.0.0.0 Safari/537.36'
)

USER_AGENT_ANDROID = (
    'Mozilla/5.0 (Linux; Android 13; SM-G991B) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/120.0.0.0 Mobile Safari/537.36'
)

# Facebook endpoints
ENDPOINTS = {
    'base': 'https://web.facebook.com',
    'www': 'https://www.facebook.com',
    'graph': 'https://graph.facebook.com',
    'graphql': 'https://web.facebook.com/api/graphql/',
    'upload_photo': 'https://upload.facebook.com/ajax/react_composer/attachments/photo/upload',
    'upload_comment_photo': 'https://web.facebook.com/ajax/ufi/upload/',
    'navigation': 'https://www.facebook.com/ajax/navigation/',
    'login': 'https://m.prod.facebook.com/login.php',
    'business_locations': 'https://business.facebook.com/business_locations',
    'ads_manager': 'https://www.facebook.com/adsmanager/manage/campaigns',
}

# GraphQL document IDs (these may need updating if Facebook changes them)
DOC_IDS = {
    'composer_create': '7338317599553815',
    'comment_create': '7128740410521626',
    'reaction': '6623712531077310',
    'profile_about': '6958968654184286',
    'group_about': '7342142219152385',
}

# Reaction type mappings
REACTIONS = {
    1: {'name': 'Like', 'id': '1635855486666999'},
    2: {'name': 'Love', 'id': '1678524932434102'},
    3: {'name': 'Haha', 'id': '115940658764963'},
    4: {'name': 'Wow', 'id': '478547315650144'},
    5: {'name': 'Care', 'id': '613557422527858'},
    6: {'name': 'Sad', 'id': '908563459236466'},
    7: {'name': 'Angry', 'id': '444813342392137'},
}

# Privacy levels
PRIVACY_LEVELS = {
    1: 'EVERYONE',
    2: 'FRIENDS',
    3: 'SELF',
}

# Supported image formats
SUPPORTED_IMAGE_FORMATS = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'image/webp': '.webp',
}

# Image download settings
IMAGE_DOWNLOAD_TIMEOUT = 30  # seconds
IMAGE_MAX_SIZE = 25 * 1024 * 1024  # 25 MB


def get_headers_get(user_agent: str = USER_AGENT_WINDOWS) -> dict:
    """
    Generate headers for GET requests.

    Args:
        user_agent: User agent string to use. Defaults to Windows Chrome.

    Returns:
        Dictionary of HTTP headers.
    """
    return {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'max-age=0',
        'Sec-Ch-Prefers-Color-Scheme': 'light',
        'Sec-Ch-Ua': '"Chromium";v="120", "Not_A Brand";v="24"',
        'Sec-Ch-Ua-Full-Version-List': '',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Ch-Ua-Platform-Version': '',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': user_agent,
        'Viewport-Width': '1920',
    }


def get_headers_post(user_agent: str = USER_AGENT_WINDOWS) -> dict:
    """
    Generate headers for POST requests.

    Args:
        user_agent: User agent string to use. Defaults to Windows Chrome.

    Returns:
        Dictionary of HTTP headers.
    """
    return {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'en-US,en;q=0.9',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': 'https://www.facebook.com',
        'Sec-Ch-Prefers-Color-Scheme': 'dark',
        'Sec-Ch-Ua': '"Chromium";v="120", "Not_A Brand";v="24"',
        'Sec-Ch-Ua-Full-Version-List': '',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Model': '',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Ch-Ua-Platform-Version': '',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': user_agent,
    }
