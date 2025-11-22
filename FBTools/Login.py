"""
Facebook authentication module.

This module provides functions for authenticating with Facebook
using cookies or email/phone credentials.
"""

import re
import random
import logging
from typing import Optional

from .constants import get_headers_get, USER_AGENT_WINDOWS

logger = logging.getLogger('FBTools')


def convert_cookie(cookie: str) -> str:
    """
    Convert and clean a Facebook cookie string.

    Extracts essential cookie values and formats them properly.

    Args:
        cookie: Raw cookie string.

    Returns:
        Cleaned cookie string with essential values.
    """
    try:
        sb = re.search(r'sb=(.*?);', str(cookie)).group(1)
        datr = re.search(r'datr=(.*?);', str(cookie)).group(1)
        c_user = re.search(r'c_user=(.*?);', str(cookie)).group(1)
        xs = re.search(r'xs=(.*?);', str(cookie)).group(1)
        fr = re.search(r'fr=(.*?);', str(cookie)).group(1)
        return f'sb={sb}; datr={datr}; c_user={c_user}; xs={xs}; fr={fr};'
    except Exception as e:
        logger.debug(f"Cookie conversion fallback: {e}")
        return cookie


def LoginCookie(r, ua: str, cookie: str) -> Optional[str]:
    """
    Validate and login using an existing Facebook cookie.

    Args:
        r: Requests session object.
        ua: User agent string.
        cookie: Facebook authentication cookie.

    Returns:
        Cleaned cookie string if valid, False if invalid.

    Example:
        >>> cookie = LoginCookie(session, user_agent, "sb=xxx; c_user=yyy; ...")
        >>> if cookie:
        ...     print("Login successful")
    """
    try:
        req = r.get(
            'https://www.facebook.com/profile.php',
            headers=get_headers_get(ua),
            cookies={'cookie': cookie},
            allow_redirects=True
        ).text

        # Check if we got a valid response with user data
        actor_id = re.search(r'"actorID":"(.*?)"', str(req))
        name = re.search(r'"NAME":"(.*?)"', str(req))

        if actor_id and name:
            logger.info(f"Cookie login successful for user: {name.group(1)}")
            return convert_cookie(cookie)
        else:
            logger.warning("Cookie validation failed - no user data found")
            return False

    except Exception as e:
        logger.error(f"Cookie login failed: {e}")
        return False


def LoginEmail(r, ua: str, email: str, password: str) -> Optional[str]:
    """
    Login to Facebook using email and password.

    Args:
        r: Requests session object.
        ua: User agent string.
        email: Facebook email address.
        password: Account password.

    Returns:
        Cookie string if login successful, False otherwise.

    Note:
        This method uses Facebook's mobile login endpoint.
    """
    try:
        Host = 'm.prod.facebook.com'
        HeadersGet = {
            'Host': Host,
            'Dpr': '1.25',
            'Viewport-Width': '1000',
            'Sec-Ch-Ua': '"Chromium";v="119", "Not?A_Brand";v="24"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Android"',
            'Sec-Ch-Ua-Platform-Version': '',
            'Sec-Ch-Ua-Model': '',
            'Sec-Ch-Ua-Full-Version-List': '',
            'Sec-Ch-Prefers-Color-Scheme': 'dark',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-User': '?1',
            'Sec-Fetch-Dest': 'document',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'en-US,en;q=0.9',
            'Priority': 'u=0, i',
        }

        Url = f'https://{Host}/login.php?'
        Req = r.get(Url, headers=HeadersGet, allow_redirects=True).text

        # Extract form data
        Data = {
            'm_ts': re.search(r'name="m_ts" value="(.*?)"', Req).group(1),
            'li': re.search(r'name="li" value="(.*?)"', Req).group(1),
            'try_number': re.search(r'name="try_number" value="(.*?)"', Req).group(1),
            'unrecognized_tries': re.search(r'name="unrecognized_tries" value="(.*?)"', Req).group(1),
            'email': email,
            'prefill_contact_point': email,
            'prefill_source': 'browser_dropdown',
            'prefill_type': 'contact_point',
            'first_prefill_source': 'browser_dropdown',
            'first_prefill_type': 'contact_point',
            'had_cp_prefilled': True,
            'had_password_prefilled': False,
            'is_smart_lock': False,
            'bi_xrwh': re.search(r'name="bi_xrwh" value="(.*?)"', Req).group(1),
            'bi_wvdp': '{"hwc":true,"hwcr":false,"has_dnt":true,"has_standalone":false,"wnd_toStr_toStr":"function toString() { [native code] }","hasPerm":false,"has_seWo":true,"has_meDe":true,"has_creds":true,"has_hwi_bt":false,"has_agjsi":false,"iframeProto":"function get contentWindow() { [native code] }","remap":false,"iframeData":{"hwc":true,"hwcr":false,"has_dnt":true,"has_standalone":false,"wnd_toStr_toStr":"function toString() { [native code] }","hasPerm":false,"has_seWo":true,"has_meDe":true,"has_creds":true,"has_hwi_bt":false,"has_agjsi":false}}',
            'pass': password,
            'fb_dtsg': re.search(r'\{"dtsg":\{"token":"(.*?)"', Req).group(1),
            'jazoest': re.search(r'name="jazoest" value="(.*?)"', Req).group(1),
            'lsd': re.search(r'name="lsd" value="(.*?)"', Req).group(1),
            '__dyn': '',
            '__csr': '',
            '__req': str(random.randrange(1, 6)),
            '__a': re.search(r'"encrypted":"(.*?)"', Req).group(1),
            '__user': '0'
        }

        Cookie = '; '.join([f'{x}={y}' for x, y in r.cookies.get_dict().items()])
        Cookie += '; dpr=4; locale=en_US; m_pixel_ratio=4; wd=360x800;'

        HeadersPost = {
            'Host': Host,
            'Cookie': Cookie,
            'Content-Length': '2000',
            'Cache-Control': 'max-age=0',
            'Dpr': '1.25',
            'Viewport-Width': '1000',
            'Sec-Ch-Ua': '"Chromium";v="119", "Not?A_Brand";v="24"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Android"',
            'Sec-Ch-Ua-Platform-Version': '',
            'Sec-Ch-Ua-Model': '',
            'Sec-Ch-Ua-Full-Version-List': '',
            'Sec-Ch-Prefers-Color-Scheme': 'dark',
            'Upgrade-Insecure-Requests': '1',
            'Origin': f'https://{Host}',
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-User': '?1',
            'Sec-Fetch-Dest': 'document',
            'Referer': Url,
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'en-US,en;q=0.9',
            'Priority': 'u=0, i'
        }

        Next = 'https://%s%s' % (Host, re.search(r'ajaxURI:"(.*?)"', Req).group(1))
        r.post(Next, data=Data, headers=HeadersPost, cookies={'cookie': Cookie}, allow_redirects=True)

        Cookie = '; '.join([f'{x}={y}' for x, y in r.cookies.get_dict().items()])
        Cookie += '; dpr=4; locale=en_US; m_pixel_ratio=4; wd=360x800;'

        if 'c_user' in Cookie:
            logger.info("Email login successful")
            return convert_cookie(Cookie)
        else:
            logger.warning("Email login failed - no c_user cookie")
            return False

    except Exception as e:
        logger.error(f"Email login failed: {e}")
        return False


def LoginPhone(r, ua: str, phone: str, password: str) -> Optional[str]:
    """
    Login to Facebook using phone number and password.

    Args:
        r: Requests session object.
        ua: User agent string.
        phone: Facebook phone number.
        password: Account password.

    Returns:
        Cookie string if login successful, False otherwise.

    Note:
        This method uses the same endpoint as email login.
    """
    try:
        Host = 'm.prod.facebook.com'
        HeadersGet = {
            'Host': Host,
            'Dpr': '1.25',
            'Viewport-Width': '1000',
            'Sec-Ch-Ua': '"Chromium";v="119", "Not?A_Brand";v="24"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Android"',
            'Sec-Ch-Ua-Platform-Version': '',
            'Sec-Ch-Ua-Model': '',
            'Sec-Ch-Ua-Full-Version-List': '',
            'Sec-Ch-Prefers-Color-Scheme': 'dark',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-User': '?1',
            'Sec-Fetch-Dest': 'document',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'en-US,en;q=0.9',
            'Priority': 'u=0, i',
        }

        Url = f'https://{Host}/login.php?'
        Req = r.get(Url, headers=HeadersGet, allow_redirects=True).text

        Data = {
            'm_ts': re.search(r'name="m_ts" value="(.*?)"', Req).group(1),
            'li': re.search(r'name="li" value="(.*?)"', Req).group(1),
            'try_number': re.search(r'name="try_number" value="(.*?)"', Req).group(1),
            'unrecognized_tries': re.search(r'name="unrecognized_tries" value="(.*?)"', Req).group(1),
            'email': phone,
            'prefill_contact_point': phone,
            'prefill_source': 'browser_dropdown',
            'prefill_type': 'contact_point',
            'first_prefill_source': 'browser_dropdown',
            'first_prefill_type': 'contact_point',
            'had_cp_prefilled': True,
            'had_password_prefilled': False,
            'is_smart_lock': False,
            'bi_xrwh': re.search(r'name="bi_xrwh" value="(.*?)"', Req).group(1),
            'bi_wvdp': '{"hwc":true,"hwcr":false,"has_dnt":true,"has_standalone":false,"wnd_toStr_toStr":"function toString() { [native code] }","hasPerm":false,"has_seWo":true,"has_meDe":true,"has_creds":true,"has_hwi_bt":false,"has_agjsi":false,"iframeProto":"function get contentWindow() { [native code] }","remap":false,"iframeData":{"hwc":true,"hwcr":false,"has_dnt":true,"has_standalone":false,"wnd_toStr_toStr":"function toString() { [native code] }","hasPerm":false,"has_seWo":true,"has_meDe":true,"has_creds":true,"has_hwi_bt":false,"has_agjsi":false}}',
            'pass': password,
            'fb_dtsg': re.search(r'\{"dtsg":\{"token":"(.*?)"', Req).group(1),
            'jazoest': re.search(r'name="jazoest" value="(.*?)"', Req).group(1),
            'lsd': re.search(r'name="lsd" value="(.*?)"', Req).group(1),
            '__dyn': '',
            '__csr': '',
            '__req': str(random.randrange(1, 6)),
            '__a': re.search(r'"encrypted":"(.*?)"', Req).group(1),
            '__user': '0'
        }

        Cookie = '; '.join([f'{x}={y}' for x, y in r.cookies.get_dict().items()])
        Cookie += '; dpr=4; locale=en_US; m_pixel_ratio=4; wd=360x800;'

        HeadersPost = {
            'Host': Host,
            'Cookie': Cookie,
            'Content-Length': '2000',
            'Cache-Control': 'max-age=0',
            'Dpr': '1.25',
            'Viewport-Width': '1000',
            'Sec-Ch-Ua': '"Chromium";v="119", "Not?A_Brand";v="24"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Android"',
            'Sec-Ch-Ua-Platform-Version': '',
            'Sec-Ch-Ua-Model': '',
            'Sec-Ch-Ua-Full-Version-List': '',
            'Sec-Ch-Prefers-Color-Scheme': 'dark',
            'Upgrade-Insecure-Requests': '1',
            'Origin': f'https://{Host}',
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-User': '?1',
            'Sec-Fetch-Dest': 'document',
            'Referer': Url,
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'en-US,en;q=0.9',
            'Priority': 'u=0, i'
        }

        Next = 'https://%s%s' % (Host, re.search(r'ajaxURI:"(.*?)"', Req).group(1))
        r.post(Next, data=Data, headers=HeadersPost, cookies={'cookie': Cookie}, allow_redirects=True)

        Cookie = '; '.join([f'{x}={y}' for x, y in r.cookies.get_dict().items()])
        Cookie += '; dpr=4; locale=en_US; m_pixel_ratio=4; wd=360x800;'

        if 'c_user' in Cookie:
            logger.info("Phone login successful")
            return convert_cookie(Cookie)
        else:
            logger.warning("Phone login failed - no c_user cookie")
            return False

    except Exception as e:
        logger.error(f"Phone login failed: {e}")
        return False
