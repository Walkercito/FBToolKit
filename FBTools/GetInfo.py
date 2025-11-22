"""
Facebook information scraping module.

This module provides classes for extracting information from Facebook
profiles, pages, and groups using the internal GraphQL API.
"""

import re
import json
import logging
from typing import Optional

from .Tools import convert_url, get_session_data, safe_regex_search, safe_regex_findall
from .constants import get_headers_get, get_headers_post, ENDPOINTS, DOC_IDS

logger = logging.getLogger('FBTools')


def TokenEAAG(r, cookie: str) -> str:
    """
    Extract EAAG token from business locations page.

    Args:
        r: Requests session object.
        cookie: Facebook authentication cookie.

    Returns:
        EAAG token string, or empty string if extraction fails.
    """
    try:
        url = ENDPOINTS['business_locations']
        req = r.get(url, cookies={'cookie': cookie})
        tok = safe_regex_search(r'(\["EAAG\w+)', req.text, default='')
        return tok.replace('["', '') if tok else ''
    except Exception as e:
        logger.error(f"Failed to extract EAAG token: {e}")
        return ''


def TokenEAAB(r, cookie: str) -> str:
    """
    Extract EAAB token from ads manager.

    Args:
        r: Requests session object.
        cookie: Facebook authentication cookie.

    Returns:
        EAAB token string, or empty string if extraction fails.
    """
    try:
        req1 = r.get(
            ENDPOINTS['ads_manager'],
            cookies={'cookie': cookie},
            allow_redirects=True
        ).text
        next_url = safe_regex_search(r'window\.location\.replace\("(.*?)"\)', req1)
        if not next_url:
            return ''
        next_url = next_url.replace('\\', '')
        req2 = r.get(next_url, cookies={'cookie': cookie}, allow_redirects=True).text
        tok = safe_regex_search(r'accessToken="(.*?)"', req2, default='')
        return tok
    except Exception as e:
        logger.error(f"Failed to extract EAAB token: {e}")
        return ''


class GetInfoProfile:
    """
    Extract information from a Facebook user profile.

    Scrapes profile data including name, work, education, location,
    relationships, and friend/follower counts.

    Args:
        r: Requests session object.
        cookie: Facebook authentication cookie.
        profile: Profile URL, username, or ID.

    Attributes:
        id: User's Facebook ID.
        name: Full name.
        username: Profile username/vanity URL.
        gender: Gender.
        short_name: Short name/nickname.
        work: Work information.
        education: Education information.
        current_city: Current city.
        hometown: Hometown.
        relationship: Relationship status.
        birthday: Birthday.
        language: Languages.
        website: Personal website.
        github: GitHub username.
        instagram: Instagram username.
        friend: Friend count.
        follower: Follower count.

    Example:
        >>> info = GetInfoProfile(r=session, cookie=cookie, profile="zuck")
        >>> print(info.name, info.follower)
    """

    def __init__(self, r=None, cookie: str = None, profile: str = None):
        self.r = r
        self.cookie = cookie
        self.url = convert_url(profile)

        # Initialize all attributes with defaults
        self.id = ''
        self.name = ''
        self.username = ''
        self.gender = ''
        self.short_name = ''
        self.work = ''
        self.education = ''
        self.current_city = ''
        self.hometown = ''
        self.relationship = ''
        self.birthday = ''
        self.language = ''
        self.website = ''
        self.github = ''
        self.instagram = ''
        self.friend = 0
        self.follower = 0

        # Fetch profile page
        try:
            self.req = self.r.get(
                self.url,
                headers=get_headers_get(),
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ).text
        except Exception as e:
            logger.error(f"Failed to fetch profile: {e}")
            self.req = None
            return

        self.Data = get_session_data(self.req) if self.req else {}
        self.token_eaag = TokenEAAG(self.r, self.cookie)
        self.token_eaab = TokenEAAB(self.r, self.cookie)

        if self.req:
            self._main_scrape()

    def _main_scrape(self):
        """Execute main scraping workflow."""
        Data = self.Data.copy()
        Target = safe_regex_search(r'"userID":"(.*?)"', self.req, default='')
        if not Target:
            logger.warning("Could not extract user ID from profile")
            return

        self._extract_basic_data(self.req)
        raw_section_token, section_token = self._navigate(Data, Target, 'about')

        if raw_section_token and section_token:
            collection_token = self._scrape_section(Data, Target, raw_section_token, section_token, 1, None)
            if collection_token and collection_token.get('BasicContact'):
                self._scrape_section(Data, Target, raw_section_token, section_token, 2, collection_token['BasicContact'])

        self._extract_counts(Target)

    def _navigate(self, Data: dict, Target: str, Route: str) -> tuple:
        """Navigate to profile section and extract tokens."""
        try:
            Data.update({
                'client_previous_actor_id': Data.get('__user', ''),
                'route_url': f'/{Target}/{Route}',
                'routing_namespace': 'fb_comet'
            })
            pos = self.r.post(
                ENDPOINTS['navigation'],
                data=Data,
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ).text.replace('\\', '')

            raw_section_token = safe_regex_search(r'"rawSectionToken":"(.*?)"', pos)
            section_token = safe_regex_search(r'"sectionToken":"(.*?)"', pos)
            return raw_section_token, section_token
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return None, None

    def _scrape_section(self, Data: dict, target_id: str, raw_section_token: str,
                        section_token: str, section_type: int, collection_token: str) -> Optional[dict]:
        """Scrape a profile section for data."""
        try:
            Var = {
                "UFI2CommentsProvider_commentsKey": "ProfileCometAboutAppSectionQuery",
                "appSectionFeedKey": f"ProfileCometAppSectionFeed_timeline_nav_app_sections__{raw_section_token}",
                "collectionToken": collection_token,
                "pageID": target_id,
                "rawSectionToken": raw_section_token,
                "scale": 2,
                "sectionToken": section_token,
                "showReactions": True,
                "userID": target_id,
                "__relay_internal__pv__CometUFIReactionsEnableShortNamerelayprovider": False
            }
            Data.update({
                'fb_api_req_friendly_name': 'ProfileCometAboutAppSectionQuery',
                'variables': json.dumps(Var),
                'server_timestamps': True,
                'doc_id': DOC_IDS['profile_about']
            })
            pos = self.r.post(
                ENDPOINTS['graphql'],
                data=Data,
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ).text.replace('\\', '')

            self._extract_section_data(pos, section_type)

            # Extract collection tokens for next section
            # Note: These strings are from Facebook's internal API structure
            basic_contact = safe_regex_search(r'"name":"Basic Contact Information","id":"(.*?)"', pos)
            if not basic_contact:
                basic_contact = safe_regex_search(r'"name":"Info Kontak dan Dasar","id":"(.*?)"', pos)

            family = safe_regex_search(r'"name":"Family and Relationships","id":"(.*?)"', pos)
            if not family:
                family = safe_regex_search(r'"name":"Keluarga dan Hubungan","id":"(.*?)"', pos)

            return {'BasicContact': basic_contact, 'Family': family}

        except Exception as e:
            logger.error(f"Section scrape failed: {e}")
            return None

    def _extract_basic_data(self, pos: str):
        """Extract basic profile data from initial page load."""
        try:
            match = re.findall(
                r'"ProfileActionBlock","profile_owner":\{"id":"(.*?)","name":"(.*?)","gender":"(.*?)","short_name":"(.*?)"',
                str(pos)
            )
            if match:
                self.id, self.name, self.gender, self.short_name = match[0]
        except Exception as e:
            logger.debug(f"Basic data extraction failed: {e}")

        self.username = safe_regex_search(r'"userVanity":"(.*?)"', pos, default='')

    def _extract_section_data(self, pos: str, section_type: int):
        """Extract data from a specific section response."""
        if section_type == 1:
            self.work = self._extract_field(pos, 'work')
            self.education = self._extract_field(pos, 'education')
            self.current_city = self._extract_field(pos, 'current_city')
            self.hometown = self._extract_field(pos, 'hometown')
            self.relationship = self._extract_field(pos, 'relationship')
        elif section_type == 2:
            birthday_parts = re.findall(r'"text":"(.*?)"\},"field_type":"birthday"', str(pos))
            if birthday_parts:
                self.birthday = ' '.join([p.split('"text":"')[-1] for p in birthday_parts])
            self.language = self._extract_field(pos, 'languages')
            self.website = self._extract_field(pos, 'website')
            self.github = self._extract_social(pos, 'GitHub')
            self.instagram = self._extract_social(pos, 'Instagram')

    def _extract_field(self, pos: str, field_type: str) -> str:
        """Extract a field value by type."""
        pattern = rf'"text":"(.*?)"\}},"field_type":"{field_type}"'
        match = safe_regex_search(pattern, pos, default='')
        if match:
            return match.split('"text":"')[-1]
        return ''

    def _extract_social(self, pos: str, platform: str) -> str:
        """Extract a social media username."""
        pattern = rf'"text":"(.*?)"\}},"field_type":"screenname".*?"text":"{platform}"\}}'
        match = safe_regex_search(pattern, pos, default='')
        if match:
            parts = match.split('"text":"')
            if len(parts) >= 2:
                return parts[-2].split('"}')[0]
        return ''

    def _extract_counts(self, target_id: str):
        """Extract friend and follower counts."""
        try:
            if self.token_eaab:
                url = f"{ENDPOINTS['graph']}/{target_id}/friends?limit=0&access_token={self.token_eaab}"
                resp = self.r.get(url, cookies={'cookie': self.cookie}).json()
                self.friend = resp.get('summary', {}).get('total_count', 0)
        except Exception as e:
            logger.debug(f"Friend count extraction failed: {e}")

        try:
            if self.token_eaag:
                url = f"{ENDPOINTS['graph']}/{target_id}/subscribers?limit=0&access_token={self.token_eaag}"
                resp = self.r.get(url, cookies={'cookie': self.cookie}).json()
                self.follower = resp.get('summary', {}).get('total_count', 0)
        except Exception as e:
            logger.debug(f"Follower count extraction failed: {e}")


class GetInfoPage:
    """
    Extract information from a Facebook page.

    Args:
        r: Requests session object.
        cookie: Facebook authentication cookie.
        page: Page URL, username, or ID.

    Attributes:
        id: Page ID.
        name: Page name.
        username: Page username.
        follower: Follower/like count text.
        category: Page category.

    Example:
        >>> info = GetInfoPage(r=session, cookie=cookie, page="facebook")
        >>> print(info.name, info.category)
    """

    def __init__(self, r=None, cookie: str = None, page: str = None):
        self.r = r
        self.cookie = cookie
        self.url = convert_url(page)

        # Initialize attributes
        self.id = ''
        self.name = ''
        self.username = ''
        self.follower = ''
        self.category = ''

        # Fetch page
        try:
            self.req = self.r.get(
                self.url,
                headers=get_headers_get(),
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ).text
        except Exception as e:
            logger.error(f"Failed to fetch page: {e}")
            self.req = None
            return

        self.Data = get_session_data(self.req) if self.req else {}

        if self.req:
            self._scrape_general()

    def _scrape_general(self):
        """Extract general page information."""
        self.id = safe_regex_search(r'"userID":"(.*?)"', self.req, default='')
        self.username = safe_regex_search(r'"userVanity":"(.*?)"', self.req, default='')

        if self.id:
            name_pattern = rf'"ProfileActionBlock","profile_owner":\{{"id":"{self.id}","name":"(.*?)","gender"'
            self.name = safe_regex_search(name_pattern, self.req, default='')

        # Extract follower text
        try:
            matches = re.findall(r'"text":"(.*?)"\},"uri"', str(self.req))
            if len(matches) >= 2:
                self.follower = f'{matches[0]} | {matches[1]}'.replace('\\u00a0', ' ')
        except Exception as e:
            logger.debug(f"Follower extraction failed: {e}")

        self.category = safe_regex_search(r'"category_name":"(.*?)"', self.req, default='')


class GetInfoGroup:
    """
    Extract information from a Facebook group.

    Args:
        r: Requests session object.
        cookie: Facebook authentication cookie.
        group: Group URL, ID, or address.

    Attributes:
        id: Group ID.
        name: Group name.
        username: Group address/username.
        privacy: Privacy level text.
        membership: Viewer's join state.
        description: Group description.
        admin: Number of admins.
        moderator: Number of moderators.
        member: Total member count.
        new_member: New member info text.
        post_last_day: Posts in last 24 hours.
        post_last_month: Posts in last month.
        visibility: Visibility info.
        history: Group history info.

    Example:
        >>> info = GetInfoGroup(r=session, cookie=cookie, group="123456789")
        >>> print(info.name, info.member)
    """

    def __init__(self, r=None, cookie: str = None, group: str = None):
        self.r = r
        self.cookie = cookie
        self.url = convert_url(group)

        # Initialize attributes
        self.id = ''
        self.name = ''
        self.username = ''
        self.privacy = ''
        self.membership = ''
        self.description = ''
        self.admin = 0
        self.moderator = 0
        self.member = 0
        self.new_member = ''
        self.post_last_day = 0
        self.post_last_month = 0
        self.visibility = ''
        self.history = ''

        # Fetch group
        try:
            self.req = self.r.get(
                self.url,
                headers=get_headers_get(),
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ).text
        except Exception as e:
            logger.error(f"Failed to fetch group: {e}")
            self.req = None
            return

        self.Data = get_session_data(self.req) if self.req else {}

        if self.req:
            self._scrape_general()
            self._scrape_detail()

    def _scrape_general(self):
        """Extract general group information from page."""
        self.id = safe_regex_search(r'"groupID":"(.*?)"', self.req, default='')
        self.username = safe_regex_search(r'"group_address":"(.*?)"', self.req, default='')

        if self.id:
            name_pattern = rf'"id":"{self.id}","name":"(.*?)"'
            self.name = safe_regex_search(name_pattern, self.req, default='')

        privacy_text = safe_regex_search(r'"text":"(.*?)"\}\},"group_member_profiles"', self.req, default='')
        if privacy_text:
            self.privacy = privacy_text.split('"text":"')[-1]

        self.membership = safe_regex_search(r'"viewer_join_state":"(.*?)"', self.req, default='')

    def _scrape_detail(self):
        """Extract detailed group information via GraphQL."""
        if not self.id:
            return

        try:
            Data = self.Data.copy()
            Data.update({
                'fb_api_caller_class': 'RelayModern',
                'fb_api_req_friendly_name': 'CometGroupAboutRootQuery',
                'variables': json.dumps({"groupID": self.id, "scale": 2}),
                'server_timestamps': True,
                'doc_id': DOC_IDS['group_about']
            })

            response = self.r.post(
                ENDPOINTS['graphql'],
                data=Data,
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ).json()

            group_data = response.get('data', {}).get('group', {})

            self.description = group_data.get('description_with_entities', {}).get('text', '')
            self.admin = int(group_data.get('facepile_admin_profiles', {}).get('count', 0))
            self.moderator = int(group_data.get('facepile_moderator_profiles', {}).get('count', 0))

            # Activity section
            activity = group_data.get('if_viewer_can_see_activity_section', {})
            if activity:
                member_text = activity.get('group_total_members_info_text', '')
                if member_text:
                    # Extract number from string like "1.234 members"
                    member_num = member_text.split()[0].replace('.', '').replace(',', '')
                    try:
                        self.member = int(member_num)
                    except ValueError:
                        self.member = 0

                self.new_member = activity.get('group_new_members_info_text', '')
                self.post_last_day = activity.get('number_of_posts_in_last_day', 0)
                self.post_last_month = activity.get('number_of_posts_in_last_month', 0)

            # About info items
            about_items = group_data.get('about_info_items', [])
            if len(about_items) > 1:
                visibility_data = about_items[1].get('group', {}).get('discoverability_info', {})
                self.visibility = visibility_data.get('description', {}).get('text', '')
            if len(about_items) > 2:
                history_data = about_items[2].get('group', {}).get('group_history', {})
                self.history = history_data.get('group_history_summary', {}).get('text', '')

        except Exception as e:
            logger.error(f"Detail scrape failed: {e}")
