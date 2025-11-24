"""
Facebook authentication module.

This module provides functions for authenticating with Facebook
using cookies or email/phone credentials.
"""

import re
import random
import logging
import time
from typing import Optional, Dict, Any
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


def LoginEmail(r, ua: str, email: str, password: str, wait_for_approval: bool = True, approval_timeout: int = 60) -> Optional[str]:
    """
    Login to Facebook using email and password.

    Args:
        r: Requests session object.
        ua: User agent string.
        email: Facebook email address.
        password: Account password.
        wait_for_approval: If True, wait for security approval (default: True).
        approval_timeout: Seconds to wait for approval (default: 60).

    Returns:
        Cookie string if login successful, False otherwise.

    Note:
        If Facebook requires security approval (notification to your phone/email),
        this function will wait up to approval_timeout seconds for you to approve.
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

        # Log the URL we ended up at (after redirects)
        logger.debug(f"Login page URL: {r.url}")

        # Check if we got redirected to Instagram or something else
        if '/ig/' in Req or 'instagram' in Req.lower():
            logger.error("Facebook redirected to Instagram login. This might be due to:")
            logger.error("  1. Email format issue")
            logger.error("  2. Facebook detecting automation")
            logger.error("  3. Account linked to Instagram")
            logger.error(f"Response preview: {Req[:500]}")
            return False

        # Extract form data with better error handling
        try:
            m_ts = re.search(r'name="m_ts" value="(.*?)"', Req)
            if not m_ts:
                logger.error("Could not find 'm_ts' field in login form")
                logger.debug(f"Response preview: {Req[:1000]}")
                return False

            li = re.search(r'name="li" value="(.*?)"', Req)
            try_number = re.search(r'name="try_number" value="(.*?)"', Req)
            unrecognized_tries = re.search(r'name="unrecognized_tries" value="(.*?)"', Req)
            bi_xrwh = re.search(r'name="bi_xrwh" value="(.*?)"', Req)
            fb_dtsg = re.search(r'\{"dtsg":\{"token":"(.*?)"', Req)
            jazoest = re.search(r'name="jazoest" value="(.*?)"', Req)
            lsd = re.search(r'name="lsd" value="(.*?)"', Req)
            encrypted = re.search(r'"encrypted":"(.*?)"', Req)
            ajax_uri = re.search(r'ajaxURI:"(.*?)"', Req)

            # Check which fields are missing
            missing_fields = []
            if not li: missing_fields.append('li')
            if not try_number: missing_fields.append('try_number')
            if not unrecognized_tries: missing_fields.append('unrecognized_tries')
            if not bi_xrwh: missing_fields.append('bi_xrwh')
            if not fb_dtsg: missing_fields.append('fb_dtsg')
            if not jazoest: missing_fields.append('jazoest')
            if not lsd: missing_fields.append('lsd')
            if not encrypted: missing_fields.append('__a')
            if not ajax_uri: missing_fields.append('ajaxURI')

            if missing_fields:
                logger.error(f"Missing form fields: {', '.join(missing_fields)}")
                logger.debug(f"Response preview: {Req[:1000]}")
                return False

            Data = {
                'm_ts': m_ts.group(1),
                'li': li.group(1),
                'try_number': try_number.group(1),
                'unrecognized_tries': unrecognized_tries.group(1),
                'email': email,
                'prefill_contact_point': email,
                'prefill_source': 'browser_dropdown',
                'prefill_type': 'contact_point',
                'first_prefill_source': 'browser_dropdown',
                'first_prefill_type': 'contact_point',
                'had_cp_prefilled': True,
                'had_password_prefilled': False,
                'is_smart_lock': False,
                'bi_xrwh': bi_xrwh.group(1),
                'bi_wvdp': '{"hwc":true,"hwcr":false,"has_dnt":true,"has_standalone":false,"wnd_toStr_toStr":"function toString() { [native code] }","hasPerm":false,"has_seWo":true,"has_meDe":true,"has_creds":true,"has_hwi_bt":false,"has_agjsi":false,"iframeProto":"function get contentWindow() { [native code] }","remap":false,"iframeData":{"hwc":true,"hwcr":false,"has_dnt":true,"has_standalone":false,"wnd_toStr_toStr":"function toString() { [native code] }","hasPerm":false,"has_seWo":true,"has_meDe":true,"has_creds":true,"has_hwi_bt":false,"has_agjsi":false}}',
                'pass': password,
                'fb_dtsg': fb_dtsg.group(1),
                'jazoest': jazoest.group(1),
                'lsd': lsd.group(1),
                '__dyn': '',
                '__csr': '',
                '__req': str(random.randrange(1, 6)),
                '__a': encrypted.group(1),
                '__user': '0'
            }
        except AttributeError as e:
            logger.error(f"Failed to extract form field: {e}")
            logger.debug(f"Response preview: {Req[:1000]}")
            return False

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

        Next = 'https://%s%s' % (Host, ajax_uri.group(1))
        r.post(Next, data=Data, headers=HeadersPost, cookies={'cookie': Cookie}, allow_redirects=True)

        # Get updated cookies
        cookies_dict = r.cookies.get_dict()
        Cookie = '; '.join([f'{x}={y}' for x, y in cookies_dict.items()])
        Cookie += '; dpr=4; locale=en_US; m_pixel_ratio=4; wd=360x800;'

        # Check if login was immediate or needs approval
        if 'c_user' in Cookie:
            logger.info("Email login successful (immediate)")
            return convert_cookie(Cookie)
        elif wait_for_approval:
            # Check if approval is needed and wait for it
            approval_result = check_login_approval(r, cookies_dict, timeout=approval_timeout)

            if approval_result['status'] == 'success':
                logger.info("Email login successful (after approval)")
                return convert_cookie(approval_result['cookie'])
            elif approval_result['status'] == 'pending':
                logger.warning(f"Email login pending: {approval_result['message']}")
                return False
            else:
                logger.warning(f"Email login failed: {approval_result['message']}")
                return False
        else:
            logger.warning("Email login failed - no c_user cookie and not waiting for approval")
            return False

    except Exception as e:
        logger.error(f"Email login failed: {e}")
        return False


def check_login_approval(r, cookies_dict: dict, timeout: int = 60) -> Dict[str, Any]:
    """
    Check if login requires approval and wait for it.

    Args:
        r: Requests session object.
        cookies_dict: Current cookies dict.
        timeout: Maximum seconds to wait for approval (default: 60).

    Returns:
        Dict with 'status', 'cookie', and 'message' keys.
    """
    logger.info("Checking for login approval requirement...")

    # Check if we already have c_user (no approval needed)
    Cookie = '; '.join([f'{x}={y}' for x, y in cookies_dict.items()])
    if 'c_user' in Cookie:
        return {'status': 'success', 'cookie': Cookie, 'message': None}

    # Check if this is a checkpoint/approval situation
    try:
        test_req = r.get(
            'https://m.facebook.com/checkpoint/',
            cookies=cookies_dict,
            allow_redirects=True
        ).text

        # Patterns that indicate approval needed
        approval_patterns = [
            'approve.*login',
            'verify.*identity',
            'security.*check',
            'checkpoint',
            'two.*factor',
            'confirm.*this.*was.*you',
        ]

        needs_approval = any(re.search(pattern, test_req, re.IGNORECASE) for pattern in approval_patterns)

        if needs_approval:
            logger.info("⏳ Login requires approval. Please check your Facebook app/email for notification.")
            logger.info(f"⏳ Waiting up to {timeout} seconds for approval...")

            start_time = time.time()
            check_interval = 3  # Check every 3 seconds

            while (time.time() - start_time) < timeout:
                time.sleep(check_interval)

                # Try to get profile page
                check_req = r.get(
                    'https://www.facebook.com/me',
                    cookies=cookies_dict,
                    allow_redirects=True
                )

                # Update cookies
                cookies_dict.update(check_req.cookies.get_dict())
                Cookie = '; '.join([f'{x}={y}' for x, y in cookies_dict.items()])

                # Check if c_user now exists
                if 'c_user' in Cookie:
                    logger.info("✓ Login approved successfully!")
                    return {'status': 'success', 'cookie': Cookie, 'message': 'Approved'}

                elapsed = int(time.time() - start_time)
                remaining = timeout - elapsed
                if remaining > 0 and elapsed % 10 == 0:  # Log every 10 seconds
                    logger.info(f"⏳ Still waiting... ({remaining}s remaining)")

            logger.warning(f"⏱ Timeout after {timeout} seconds. Login not approved.")
            return {
                'status': 'pending',
                'cookie': None,
                'message': f'Login approval timeout after {timeout}s. Please approve and try again with the same credentials.'
            }

        # If no approval patterns found, might be another error
        logger.warning("Login failed - unexpected response")
        return {'status': 'failed', 'cookie': None, 'message': 'Unexpected login response'}

    except Exception as e:
        logger.error(f"Error checking approval: {e}")
        return {'status': 'error', 'cookie': None, 'message': str(e)}


def LoginPhone(r, ua: str, phone: str, password: str, wait_for_approval: bool = True, approval_timeout: int = 60) -> Optional[str]:
    """
    Login to Facebook using phone number and password.

    Args:
        r: Requests session object.
        ua: User agent string.
        phone: Facebook phone number.
        password: Account password.
        wait_for_approval: If True, wait for security approval (default: True).
        approval_timeout: Seconds to wait for approval (default: 60).

    Returns:
        Cookie string if login successful, False otherwise.

    Note:
        If Facebook requires security approval (notification to your phone/email),
        this function will wait up to approval_timeout seconds for you to approve.
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

        # Log the URL we ended up at (after redirects)
        logger.debug(f"Login page URL: {r.url}")

        # Check if we got redirected to Instagram or something else
        if '/ig/' in Req or 'instagram' in Req.lower():
            logger.error("Facebook redirected to Instagram login. This might be due to:")
            logger.error("  1. Phone number format issue")
            logger.error("  2. Facebook detecting automation")
            logger.error("  3. Account linked to Instagram")
            logger.error(f"Response preview: {Req[:500]}")
            return False

        # Extract form data with better error handling
        try:
            m_ts = re.search(r'name="m_ts" value="(.*?)"', Req)
            if not m_ts:
                logger.error("Could not find 'm_ts' field in login form")
                logger.debug(f"Response preview: {Req[:1000]}")
                return False

            li = re.search(r'name="li" value="(.*?)"', Req)
            try_number = re.search(r'name="try_number" value="(.*?)"', Req)
            unrecognized_tries = re.search(r'name="unrecognized_tries" value="(.*?)"', Req)
            bi_xrwh = re.search(r'name="bi_xrwh" value="(.*?)"', Req)
            fb_dtsg = re.search(r'\{"dtsg":\{"token":"(.*?)"', Req)
            jazoest = re.search(r'name="jazoest" value="(.*?)"', Req)
            lsd = re.search(r'name="lsd" value="(.*?)"', Req)
            encrypted = re.search(r'"encrypted":"(.*?)"', Req)
            ajax_uri = re.search(r'ajaxURI:"(.*?)"', Req)

            # Check which fields are missing
            missing_fields = []
            if not li: missing_fields.append('li')
            if not try_number: missing_fields.append('try_number')
            if not unrecognized_tries: missing_fields.append('unrecognized_tries')
            if not bi_xrwh: missing_fields.append('bi_xrwh')
            if not fb_dtsg: missing_fields.append('fb_dtsg')
            if not jazoest: missing_fields.append('jazoest')
            if not lsd: missing_fields.append('lsd')
            if not encrypted: missing_fields.append('__a')
            if not ajax_uri: missing_fields.append('ajaxURI')

            if missing_fields:
                logger.error(f"Missing form fields: {', '.join(missing_fields)}")
                logger.debug(f"Response preview: {Req[:1000]}")
                return False

            Data = {
                'm_ts': m_ts.group(1),
                'li': li.group(1),
                'try_number': try_number.group(1),
                'unrecognized_tries': unrecognized_tries.group(1),
                'email': phone,
                'prefill_contact_point': phone,
                'prefill_source': 'browser_dropdown',
                'prefill_type': 'contact_point',
                'first_prefill_source': 'browser_dropdown',
                'first_prefill_type': 'contact_point',
                'had_cp_prefilled': True,
                'had_password_prefilled': False,
                'is_smart_lock': False,
                'bi_xrwh': bi_xrwh.group(1),
                'bi_wvdp': '{"hwc":true,"hwcr":false,"has_dnt":true,"has_standalone":false,"wnd_toStr_toStr":"function toString() { [native code] }","hasPerm":false,"has_seWo":true,"has_meDe":true,"has_creds":true,"has_hwi_bt":false,"has_agjsi":false,"iframeProto":"function get contentWindow() { [native code] }","remap":false,"iframeData":{"hwc":true,"hwcr":false,"has_dnt":true,"has_standalone":false,"wnd_toStr_toStr":"function toString() { [native code] }","hasPerm":false,"has_seWo":true,"has_meDe":true,"has_creds":true,"has_hwi_bt":false,"has_agjsi":false}}',
                'pass': password,
                'fb_dtsg': fb_dtsg.group(1),
                'jazoest': jazoest.group(1),
                'lsd': lsd.group(1),
                '__dyn': '',
                '__csr': '',
                '__req': str(random.randrange(1, 6)),
                '__a': encrypted.group(1),
                '__user': '0'
            }
        except AttributeError as e:
            logger.error(f"Failed to extract form field: {e}")
            logger.debug(f"Response preview: {Req[:1000]}")
            return False

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

        Next = 'https://%s%s' % (Host, ajax_uri.group(1))
        r.post(Next, data=Data, headers=HeadersPost, cookies={'cookie': Cookie}, allow_redirects=True)

        # Get updated cookies
        cookies_dict = r.cookies.get_dict()
        Cookie = '; '.join([f'{x}={y}' for x, y in cookies_dict.items()])
        Cookie += '; dpr=4; locale=en_US; m_pixel_ratio=4; wd=360x800;'

        # Check if login was immediate or needs approval
        if 'c_user' in Cookie:
            logger.info("Phone login successful (immediate)")
            return convert_cookie(Cookie)
        elif wait_for_approval:
            # Check if approval is needed and wait for it
            approval_result = check_login_approval(r, cookies_dict, timeout=approval_timeout)

            if approval_result['status'] == 'success':
                logger.info("Phone login successful (after approval)")
                return convert_cookie(approval_result['cookie'])
            elif approval_result['status'] == 'pending':
                logger.warning(f"Phone login pending: {approval_result['message']}")
                return False
            else:
                logger.warning(f"Phone login failed: {approval_result['message']}")
                return False
        else:
            logger.warning("Phone login failed - no c_user cookie and not waiting for approval")
            return False

    except Exception as e:
        logger.error(f"Phone login failed: {e}")
        return False
