"""
Facebook account settings module.

This module provides classes for managing Facebook account settings
including two-factor authentication, connected apps, and profile guard.
"""

import re
import time
import json
import datetime
import uuid
import logging

try:
    import pyotp
except ImportError:
    pyotp = None

from .Tools import get_session_data
from .GetInfo import TokenEAAG
from .constants import get_headers_get, get_headers_post, ENDPOINTS

logger = logging.getLogger('FBTools')

# English month names for date formatting
MONTH_NAMES = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
]


class A2F:
    """
    Enable two-factor authentication on a Facebook account.

    Args:
        r: Requests session object.
        cookie: Facebook authentication cookie.
        stat: True to enable 2FA.
        password: Account password.

    Example:
        >>> a2f = A2F(r=session, cookie=cookie, stat=True, password="pass123")
        >>> result = a2f.Auten()
        >>> if result['status'] == 'success':
        ...     print(f"2FA Key: {result['key']}")
        ...     print(f"Recovery Codes: {result['recovery']}")
    """

    def __init__(self, r=None, cookie: str = None, stat: bool = None, password: str = None):
        self.r = r
        self.cookie = cookie
        self.stat = stat
        self.password = password

        try:
            self.req = self.r.get(
                'https://www.facebook.com/',
                headers=get_headers_get(),
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ).text.replace('\\', '')
        except Exception as e:
            logger.error(f"Failed to fetch session: {e}")
            self.req = None

        self.Data = get_session_data(self.req) if self.req else {}

    def Auten(self):
        """
        Enable 2FA and return the secret key and recovery codes.

        Returns:
            Dict with keys:
            - status: 'success' or 'failed'
            - key: TOTP secret key if successful
            - recovery: List of recovery codes if successful
            - message: Error message if failed
        """
        if pyotp is None:
            return {
                'status': 'failed',
                'key': None,
                'recovery': None,
                'message': 'pyotp library not installed. Run: pip install pyotp'
            }

        if self.stat == True or self.stat == 1:
            x1 = self._post0('https://www.facebook.com/security/2fac/setup/qrcode/generate/')

            # Check if confirmation is required (password needed)
            if 'Confirmation Required' in str(x1) or 'Diperlukan Konfirmasi' in str(x1):
                x1 = self._post1('https://www.facebook.com/security/2fac/setup/qrcode/generate/')

            if 'Confirmation Required' in str(x1) or 'Diperlukan Konfirmasi' in str(x1):
                return {
                    'status': 'failed',
                    'key': None,
                    'recovery': None,
                    'message': 'Wrong password'
                }

            # Retry loop for getting serialized data
            limit = 0
            while 'serialized_data' not in str(x1) and limit < 10:
                x1 = self._post0('https://www.facebook.com/security/2fac/setup/qrcode/generate/')
                limit += 1

            if limit == 10 and 'serialized_data' not in str(x1):
                return {
                    'status': 'failed',
                    'key': None,
                    'recovery': None,
                    'message': 'Account may be rate limited or spam flagged'
                }

            if 'serialized_data' in str(x1):
                try:
                    redirect_match = re.search(r'"redirect":"(.*?)"', str(x1))
                    if not redirect_match:
                        return {
                            'status': 'failed',
                            'key': None,
                            'recovery': None,
                            'message': 'Could not find redirect URL'
                        }

                    next_url = 'https://www.facebook.com' + redirect_match.group(1)
                    pos1 = self._post1(next_url)

                    code_match = re.search(r'"code":"(.*?)"', str(pos1))
                    qr_match = re.search(r'"src":"(.*?)"', str(pos1))

                    if not code_match:
                        return {
                            'status': 'failed',
                            'key': None,
                            'recovery': None,
                            'message': 'Could not extract 2FA code'
                        }

                    key = {
                        'code': code_match.group(1).replace(' ', ''),
                        'qr': qr_match.group(1) if qr_match else ''
                    }

                    # Generate TOTP code
                    totp_code = pyotp.TOTP(key['code']).now()
                    final = self._verify_code(totp_code)

                    if '"/security/2fac/setup/outro/"' in str(final) or '"/security/2fac/settings/"' in str(final):
                        logger.info("2FA enabled successfully")
                        return {
                            'status': 'success',
                            'key': key['code'],
                            'recovery': self._get_recovery_codes(),
                            'message': None
                        }
                    else:
                        return {
                            'status': 'failed',
                            'key': None,
                            'recovery': None,
                            'message': 'Failed to enable 2FA - verification failed'
                        }

                except Exception as e:
                    logger.error(f"2FA setup failed: {e}")
                    return {
                        'status': 'failed',
                        'key': None,
                        'recovery': None,
                        'message': f'Error during 2FA setup: {e}'
                    }

        return {
            'status': 'failed',
            'key': None,
            'recovery': None,
            'message': 'Unknown error'
        }

    def _post0(self, url: str) -> str:
        """Make a POST request without password confirmation."""
        pos = self.r.post(
            url,
            data=self.Data,
            headers=get_headers_post(),
            cookies={'cookie': self.cookie},
            allow_redirects=True
        ).text.replace('\\', '')
        return pos

    def _post1(self, url: str) -> str:
        """Make a POST request with password confirmation."""
        Data = self.Data.copy()
        Data.update({'__asyncDialog': 1, 'ajax_password': self.password, 'confirmed': 1})
        pos = self.r.post(
            url,
            data=Data,
            headers=get_headers_post(),
            cookies={'cookie': self.cookie},
            allow_redirects=True
        ).text.replace('\\', '')
        return pos

    def _verify_code(self, code: str) -> str:
        """Verify the TOTP code."""
        Data = self.Data.copy()
        Data.update({'code': code, 'dialog_loaded': True})
        pos = self.r.post(
            'https://www.facebook.com/security/2fac/setup/verify_code/',
            data=Data,
            headers=get_headers_post(),
            cookies={'cookie': self.cookie},
            allow_redirects=True
        ).text.replace('\\', '')
        return pos

    def _get_recovery_codes(self) -> list:
        """Get the recovery codes after enabling 2FA."""
        try:
            Data = self.Data.copy()
            Data.update({'reset': True})
            pos = self.r.post(
                'https://www.facebook.com/security/2fac/factors/recovery-code/',
                data=Data,
                headers=get_headers_post(),
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ).text.replace('\\', '')
            return re.findall(r'"value":"(.*?)"', str(pos))
        except Exception as e:
            logger.error(f"Failed to get recovery codes: {e}")
            return []


class UnA2F:
    """
    Disable two-factor authentication on a Facebook account.

    Args:
        r: Requests session object.
        cookie: Facebook authentication cookie.
        stat: False to disable 2FA.
        password: Account password.
    """

    def __init__(self, r=None, cookie: str = None, stat: bool = None, password: str = None):
        self.r = r
        self.cookie = cookie
        self.stat = stat
        self.password = password

        try:
            self.req = self.r.get(
                'https://www.facebook.com/',
                headers=get_headers_get(),
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ).text.replace('\\', '')
        except Exception as e:
            logger.error(f"Failed to fetch session: {e}")
            self.req = None

        self.Data = get_session_data(self.req) if self.req else {}

    def UnAuten(self):
        """
        Disable 2FA.

        Returns:
            Dict with keys:
            - status: 'success' or 'failed'
            - key: Always None
            - recovery: Always None
            - message: Error message if failed
        """
        try:
            if self.stat == False or self.stat == 0:
                Data = self.Data.copy()
                Data.update({
                    'next': 'https://www.facebook.com/security/2fac/settings/',
                    'encpass': f'#PWD_BROWSER:0:{int(time.time())}:{self.password}'
                })

                self.r.post(
                    'https://www.facebook.com/login/reauth.php',
                    data=Data,
                    headers=get_headers_post(),
                    cookies={'cookie': self.cookie},
                    allow_redirects=True
                )

                pos2 = self.r.post(
                    'https://www.facebook.com/security/2fac/setup/turn_off/',
                    data=self.Data,
                    headers=get_headers_post(),
                    cookies={'cookie': self.cookie},
                    allow_redirects=True
                ).text.replace('\\', '')

                if 'REMOVEMETHOD' in str(pos2):
                    action_match = re.search(r'"action":"(.*?)"', str(pos2))
                    if action_match:
                        next_url = 'https://www.facebook.com' + action_match.group(1)
                        pos3 = self.r.post(
                            next_url,
                            data=self.Data,
                            headers=get_headers_post(),
                            cookies={'cookie': self.cookie},
                            allow_redirects=True
                        ).text.replace('\\', '')

                        if 'onTwoFactorSetupChange' in str(pos3) and 'redirectPageTo' in str(pos3):
                            logger.info("2FA disabled successfully")
                            return {
                                'status': 'success',
                                'key': None,
                                'recovery': None,
                                'message': None
                            }

                    return {
                        'status': 'failed',
                        'key': None,
                        'recovery': None,
                        'message': 'Failed to remove 2FA'
                    }
                else:
                    return {
                        'status': 'failed',
                        'key': None,
                        'recovery': None,
                        'message': 'Wrong password'
                    }

        except Exception as e:
            logger.error(f"Failed to disable 2FA: {e}")
            return {
                'status': 'failed',
                'key': None,
                'recovery': None,
                'message': f'Error: {e}'
            }

        return {
            'status': 'failed',
            'key': None,
            'recovery': None,
            'message': 'Invalid stat parameter'
        }


class GetAPP:
    """
    Get list of connected apps and websites.

    Args:
        r: Requests session object.
        cookie: Facebook authentication cookie.

    Example:
        >>> apps = GetAPP(r=session, cookie=cookie)
        >>> result = apps.Execute()
        >>> print(f"Active apps: {len(result['active'])}")
        >>> print(f"Expired apps: {len(result['expired'])}")
    """

    def __init__(self, r=None, cookie: str = None):
        self.ActiveApps = []
        self.ExpiredApps = []
        self.r = r
        self.cookie = cookie

        try:
            self.req = self.r.get(
                'https://www.facebook.com/',
                headers=get_headers_get(),
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ).text.replace('\\', '')
        except Exception as e:
            logger.error(f"Failed to fetch session: {e}")
            self.req = None

        self.Data = get_session_data(self.req) if self.req else {}
        self.Data.update({
            'fb_api_caller_class': 'RelayModern',
            'server_timestamps': True
        })

    def Execute(self):
        """
        Get all connected apps.

        Returns:
            Dict with 'active' and 'expired' lists of app info.
        """
        self._check_apps(1)  # Active apps
        self._check_apps(2)  # Expired apps
        return {'active': self.ActiveApps, 'expired': self.ExpiredApps}

    def _check_apps(self, stat: int):
        """Check apps by status (1=active, 2=expired)."""
        if stat == 1:
            Data = self.Data.copy()
            node = 'activeApps'
            Data.update({
                'fb_api_req_friendly_name': 'ApplicationAndWebsitePaginatedSettingAppGridListActiveQuery',
                'doc_id': '4711129059016316'
            })
            self._check_loop(Data, node, stat, None)
        elif stat == 2:
            Data = self.Data.copy()
            node = 'expiredApps'
            Data.update({
                'fb_api_req_friendly_name': 'ApplicationAndWebsitePaginatedSettingAppGridListExpiredQuery',
                'doc_id': '4802508009803010'
            })
            self._check_loop(Data, node, stat, None)

    def _check_loop(self, dta: dict, node: str, stat: int, cursor: str):
        """Recursively fetch paginated app list."""
        try:
            dta.update({
                'variables': json.dumps({
                    "after": cursor,
                    "first": 6,
                    "id": dta.get('__user', '')
                })
            })

            pos = self.r.post(
                'https://www.facebook.com/api/graphql/',
                data=dta,
                headers=get_headers_post(),
                cookies={'cookie': self.cookie}
            ).json()

            dat = pos.get('data', {}).get('node', {}).get(node, {}).get('edges', [])

            for x in dat:
                try:
                    dtk = x.get('node', {}).get('apps_and_websites_view', {}).get('detailView', {})
                    app_id = dtk.get('app_id', '')
                    app_name = dtk.get('app_name', '')
                    install_timestamp = dtk.get('install_timestamp', 0)

                    # Format date in English
                    tm = datetime.datetime.utcfromtimestamp(int(install_timestamp))
                    formatted_date = f'{tm.day} {MONTH_NAMES[tm.month - 1]} {tm.year}'

                    app_info = {
                        'id': app_id,
                        'name': app_name,
                        'date': formatted_date
                    }

                    if stat == 1:
                        self.ActiveApps.append(app_info)
                    elif stat == 2:
                        self.ExpiredApps.append(app_info)

                except Exception as e:
                    logger.debug(f"Failed to parse app: {e}")
                    continue

            # Check for more pages
            page_info = pos.get('data', {}).get('node', {}).get(node, {}).get('page_info', {})
            if page_info.get('has_next_page'):
                next_cursor = page_info.get('end_cursor')
                self._check_loop(dta, node, stat, next_cursor)

        except Exception as e:
            logger.error(f"Failed to fetch apps: {e}")


class ProfileGuard:
    """
    Enable or disable Facebook profile guard.

    Profile guard adds a shield to your profile picture and
    prevents others from downloading or sharing it.

    Args:
        r: Requests session object.
        cookie: Facebook authentication cookie.
        stat: True to enable, False to disable.
    """

    def __init__(self, r=None, cookie: str = None, stat: bool = True):
        self.r = r
        self.cookie = cookie
        self.token = TokenEAAG(self.r, self.cookie)
        self.stat = stat

    def Execute(self):
        """
        Toggle profile guard status.

        Returns:
            Dict with keys:
            - status: 'active', 'inactive', or 'failed'
            - message: Error message if failed
        """
        try:
            c_user_match = re.search(r'c_user=(.*?);', str(self.cookie))
            if not c_user_match:
                return {
                    'status': 'failed',
                    'message': 'Could not extract user ID from cookie'
                }

            user_id = c_user_match.group(1)
            Var = {
                '0': {
                    'is_shielded': self.stat,
                    'session_id': str(uuid.uuid4()),
                    'actor_id': user_id,
                    'client_mutation_id': str(uuid.uuid4())
                }
            }

            Data = {
                'variables': json.dumps(Var),
                'doc_id': '1477043292367183',
                'query_name': 'IsShieldedSetMutation',
                'strip_defaults': True,
                'strip_nulls': True,
                'locale': 'en_US',
                'client_country_code': 'US',
                'server_timestamps': True,
                'fb_api_req_friendly_name': 'IsShieldedSetMutation',
                'fb_api_caller_class': 'IsShieldedSetMutation'
            }

            hdp = get_headers_post().copy()
            hdp.update({'Authorization': f'OAuth {self.token}'})

            pos = self.r.post(
                'https://graph.facebook.com/graphql',
                data=Data,
                headers=hdp,
                cookies={'cookie': self.cookie}
            ).text

            if '"is_shielded":true' in str(pos):
                logger.info("Profile guard enabled")
                return {'status': 'active', 'message': None}
            elif '"is_shielded":false' in str(pos):
                logger.info("Profile guard disabled")
                return {'status': 'inactive', 'message': None}
            else:
                return {
                    'status': 'failed',
                    'message': 'Token EAAG invalid - you may need to disable 2FA first'
                }

        except Exception as e:
            logger.error(f"Profile guard update failed: {e}")
            return {
                'status': 'failed',
                'message': f'Error: {e}'
            }
