"""
Utility functions for FBTools.

This module provides helper functions for URL conversion, data extraction,
and safe regex operations used throughout the library.
"""

import re
import random
import logging
from typing import Optional, Any

from .exceptions import ScrapingError

logger = logging.getLogger('FBTools')


def safe_regex_search(
    pattern: str,
    text: str,
    group: int = 1,
    default: Any = None,
    raise_on_fail: bool = False
) -> Optional[str]:
    """
    Safely search for a regex pattern and return a group.

    This function wraps re.search() to prevent AttributeError when
    the pattern is not found.

    Args:
        pattern: Regular expression pattern to search for.
        text: Text to search in.
        group: Group number to return (default: 1).
        default: Value to return if pattern is not found (default: None).
        raise_on_fail: If True, raise ScrapingError instead of returning default.

    Returns:
        The matched group if found, otherwise the default value.

    Raises:
        ScrapingError: If raise_on_fail is True and pattern is not found.

    Example:
        >>> safe_regex_search(r'"id":"(\\d+)"', '{"id":"12345"}')
        '12345'
        >>> safe_regex_search(r'"missing":"(.*?)"', '{"id":"12345"}', default='')
        ''
    """
    match = re.search(pattern, str(text))
    if match:
        try:
            return match.group(group)
        except IndexError:
            if raise_on_fail:
                raise ScrapingError(f"Group {group} not found in pattern: {pattern}")
            return default

    if raise_on_fail:
        raise ScrapingError(f"Pattern not found: {pattern}")
    return default


def safe_regex_findall(
    pattern: str,
    text: str,
    index: int = -1,
    default: Any = None
) -> Optional[str]:
    """
    Safely find all matches and return a specific index.

    Args:
        pattern: Regular expression pattern to search for.
        text: Text to search in.
        index: Index of match to return (default: -1, last match).
        default: Value to return if not found (default: None).

    Returns:
        The matched string at the specified index, or default if not found.

    Example:
        >>> safe_regex_findall(r'"id":"(\\d+)"', '{"id":"1"}{"id":"2"}', index=0)
        '1'
        >>> safe_regex_findall(r'"id":"(\\d+)"', '{"id":"1"}{"id":"2"}', index=-1)
        '2'
    """
    matches = re.findall(pattern, str(text))
    if matches:
        try:
            return matches[index]
        except IndexError:
            return default
    return default


def convert_url(url: str) -> str:
    """
    Convert various Facebook URL formats to standard www.facebook.com format.

    Handles URLs from different Facebook domains (m.facebook.com, mbasic.facebook.com,
    web.facebook.com) and converts them to the standard www.facebook.com format.
    Also handles relative paths and IDs.

    Args:
        url: The Facebook URL or identifier to convert.

    Returns:
        Standardized Facebook URL starting with https://www.facebook.com/

    Example:
        >>> convert_url('m.facebook.com/profile.php?id=123')
        'https://www.facebook.com/profile.php?id=123'
        >>> convert_url('123456789')
        'https://www.facebook.com/123456789'
    """
    url_str = str(url)

    # Mapping of Facebook domains to replace
    domain_replacements = {
        'm.facebook.com': 'www.facebook.com',
        'mbasic.facebook.com': 'www.facebook.com',
        'web.facebook.com': 'www.facebook.com',
    }

    if 'http' in url_str:
        # URL already has protocol
        if 'www.facebook.com' in url_str:
            return url_str
        for old_domain, new_domain in domain_replacements.items():
            if old_domain in url_str:
                return url_str.replace(old_domain, new_domain)
        return url_str
    else:
        # URL without protocol
        if 'www.facebook.com' in url_str:
            return 'https://' + url_str
        for old_domain, new_domain in domain_replacements.items():
            if old_domain in url_str:
                return 'https://' + url_str.replace(old_domain, new_domain)

        # Handle facebook.com without subdomain
        if 'facebook.com' in url_str.lower():
            cleaned = url_str.replace('facebook.com', '').replace('Facebook.com', '')
            return 'https://www.facebook.com' + cleaned

        # Assume it's an ID or username
        return f'https://www.facebook.com/{url_str}'


def get_session_data(response_text: str) -> dict:
    """
    Extract session data from Facebook page response.

    Parses the HTML/JavaScript response from Facebook to extract
    necessary tokens and session information for API calls.

    Args:
        response_text: Raw HTML/JavaScript response from Facebook.

    Returns:
        Dictionary containing session data with keys:
        - av: Actor ID (viewer)
        - __user: User ID
        - __a: Request identifier
        - __hs: Haste session
        - __ccg: Connection class
        - __rev, __spin_r, __spin_b, __spin_t: Spin parameters
        - __hsi: HSI token
        - fb_dtsg: DTSG token (CSRF protection)
        - jazoest: Jazoest token
        - lsd: LSD token

    Raises:
        ScrapingError: If critical session data cannot be extracted.

    Note:
        Returns an empty dict if extraction fails to maintain
        backwards compatibility.
    """
    try:
        # Extract required values using safe regex
        actor_id = safe_regex_search(r'"actorID":"(.*?)"', response_text)
        if not actor_id:
            logger.warning("Could not extract actorID from response")
            return {}

        data = {
            'av': actor_id,
            '__user': actor_id,
            '__a': str(random.randrange(1, 6)),
            '__hs': safe_regex_search(r'"haste_session":"(.*?)"', response_text, default=''),
            'dpr': '1.5',
            '__ccg': safe_regex_search(r'"connectionClass":"(.*?)"', response_text, default=''),
            '__rev': safe_regex_search(r'"__spin_r":(.*?),', response_text, default=''),
            '__spin_r': safe_regex_search(r'"__spin_r":(.*?),', response_text, default=''),
            '__spin_b': safe_regex_search(r'"__spin_b":"(.*?)"', response_text, default=''),
            '__spin_t': safe_regex_search(r'"__spin_t":(.*?),', response_text, default=''),
            '__hsi': safe_regex_search(r'"hsi":"(.*?)"', response_text, default=''),
            '__comet_req': '15',
            'fb_dtsg': safe_regex_search(r'"DTSGInitialData",\[\],\{"token":"(.*?)"\}', response_text, default=''),
            'jazoest': safe_regex_search(r'jazoest=(.*?)"', response_text, default=''),
            'lsd': safe_regex_search(r'"LSD",\[\],\{"token":"(.*?)"\}', response_text, default=''),
        }

        # Log warning if critical tokens are missing
        if not data['fb_dtsg']:
            logger.warning("fb_dtsg token not found in response")
        if not data['lsd']:
            logger.warning("lsd token not found in response")

        return data

    except Exception as e:
        logger.error(f"Failed to extract session data: {e}")
        return {}


# Backwards compatibility aliases
ConvertURL = convert_url
GetData = get_session_data
