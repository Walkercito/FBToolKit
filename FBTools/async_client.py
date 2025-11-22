"""
Async client for FBTools.

This module provides asynchronous versions of all FBTools functionality
using aiohttp for non-blocking HTTP requests.

Example:
    >>> import asyncio
    >>> from FBTools.async_client import AsyncStart
    >>>
    >>> async def main():
    ...     async with AsyncStart(cookie="your_cookie") as fb:
    ...         if fb.IsValid:
    ...             result = await fb.PostToFeed(text="Hello async world!")
    ...             print(result)
    >>>
    >>> asyncio.run(main())
"""

import re
import json
import logging
import mimetypes
import aiohttp
from pathlib import Path
from typing import Optional, List, Dict, Any

from .Tools import safe_regex_search, safe_regex_findall, convert_url
from .constants import (
    get_headers_get,
    get_headers_post,
    ENDPOINTS,
    DOC_IDS,
    REACTIONS,
    PRIVACY_LEVELS,
    USER_AGENT_WINDOWS,
    USER_AGENT_ANDROID,
    IMAGE_DOWNLOAD_TIMEOUT,
)
from .exceptions import (
    ValidationError,
    AuthenticationError,
    PostError,
    ImageUploadError,
    SessionError,
)

logger = logging.getLogger('FBTools.async')


async def async_load_image(
    session: aiohttp.ClientSession,
    source: str,
    timeout: int = IMAGE_DOWNLOAD_TIMEOUT
) -> tuple:
    """
    Asynchronously load an image from a URL or local file path.

    Args:
        session: aiohttp ClientSession.
        source: URL or file path to the image.
        timeout: Timeout in seconds for URL downloads.

    Returns:
        Tuple of (image_bytes, filename, content_type).

    Raises:
        ImageUploadError: If the image cannot be loaded.
    """
    source = str(source).strip()

    if source.startswith(('http://', 'https://')):
        try:
            logger.debug(f"Downloading image from URL: {source}")
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}

            async with session.get(source, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status != 200:
                    raise ImageUploadError(f"Failed to download image: HTTP {response.status}")

                image_data = await response.read()
                content_type = response.headers.get('Content-Type', 'image/jpeg')

                url_path = source.split('?')[0]
                filename = url_path.split('/')[-1]

                if '.' not in filename:
                    ext = mimetypes.guess_extension(content_type.split(';')[0]) or '.jpg'
                    filename = f'image{ext}'

                logger.debug(f"Downloaded image: {filename} ({len(image_data)} bytes)")
                return image_data, filename, content_type

        except aiohttp.ClientError as e:
            raise ImageUploadError(f"Failed to download image from URL: {e}")
        except Exception as e:
            raise ImageUploadError(f"Error loading image from URL: {e}")

    else:
        file_path = Path(source)
        if not file_path.exists():
            raise ImageUploadError(f"File not found: {source}")

        try:
            logger.debug(f"Loading image from file: {source}")
            image_data = file_path.read_bytes()
            filename = file_path.name
            content_type = mimetypes.guess_type(source)[0] or 'image/jpeg'

            return image_data, filename, content_type

        except Exception as e:
            raise ImageUploadError(f"Error reading file: {e}")


async def async_get_session_data(session: aiohttp.ClientSession, cookie: str) -> tuple:
    """
    Asynchronously fetch and extract session data from Facebook.

    Args:
        session: aiohttp ClientSession.
        cookie: Facebook authentication cookie.

    Returns:
        Tuple of (response_text, session_data_dict).
    """
    try:
        async with session.get(
            ENDPOINTS['base'] + '/',
            headers=get_headers_get(),
            cookies={'cookie': cookie},
            allow_redirects=True
        ) as response:
            text = await response.text()

        actor_id = safe_regex_search(r'"actorID":"(.*?)"', text)
        if not actor_id:
            return text, {}

        import random
        data = {
            'av': actor_id,
            '__user': actor_id,
            '__a': str(random.randrange(1, 6)),
            '__hs': safe_regex_search(r'"haste_session":"(.*?)"', text, default=''),
            'dpr': '1.5',
            '__ccg': safe_regex_search(r'"connectionClass":"(.*?)"', text, default=''),
            '__rev': safe_regex_search(r'"__spin_r":(.*?),', text, default=''),
            '__spin_r': safe_regex_search(r'"__spin_r":(.*?),', text, default=''),
            '__spin_b': safe_regex_search(r'"__spin_b":"(.*?)"', text, default=''),
            '__spin_t': safe_regex_search(r'"__spin_t":(.*?),', text, default=''),
            '__hsi': safe_regex_search(r'"hsi":"(.*?)"', text, default=''),
            '__comet_req': '15',
            'fb_dtsg': safe_regex_search(r'"DTSGInitialData",\[\],\{"token":"(.*?)"\}', text, default=''),
            'jazoest': safe_regex_search(r'jazoest=(.*?)"', text, default=''),
            'lsd': safe_regex_search(r'"LSD",\[\],\{"token":"(.*?)"\}', text, default=''),
        }

        return text, data

    except Exception as e:
        logger.error(f"Failed to fetch session data: {e}")
        return '', {}


class AsyncPostToFeed:
    """
    Asynchronously create a post on the user's feed.

    Example:
        >>> async with aiohttp.ClientSession() as session:
        ...     post = AsyncPostToFeed(session, cookie, text="Hello!")
        ...     result = await post.execute()
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        cookie: str,
        text: str = None,
        url: List[str] = None,
        tag: List[str] = None,
        privacy: int = None
    ):
        self.session = session
        self.cookie = cookie
        self.text = text or ''
        self.tag = tag or []
        self.image_sources = url or []
        self.privacy = PRIVACY_LEVELS.get(privacy, 'EVERYONE')
        self.attachments = []
        self.upload_errors = []

    async def _upload_photo(self, source: str, data: dict) -> bool:
        """Upload a photo asynchronously."""
        try:
            image_data, filename, content_type = await async_load_image(self.session, source)

            form_data = aiohttp.FormData()
            form_data.add_field('file', image_data, filename=filename, content_type=content_type)

            upload_data = data.copy()
            upload_data.update({
                'source': '8',
                'profile_id': data.get('__user', ''),
                'waterfallxapp': 'comet',
                'upload_id': 'jsc_c_1g'
            })

            for key, value in upload_data.items():
                form_data.add_field(key, str(value))

            async with self.session.post(
                ENDPOINTS['upload_photo'],
                data=form_data,
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ) as response:
                text = await response.text()

            photo_id = safe_regex_search(r'"photoID":"(.*?)"', text)
            if photo_id:
                self.attachments.append({"photo": {"id": photo_id}})
                logger.info(f"Uploaded photo: {filename} (ID: {photo_id})")
                return True
            else:
                self.upload_errors.append(f"Failed to get photo ID: {filename}")
                return False

        except ImageUploadError as e:
            self.upload_errors.append(str(e))
            return False
        except Exception as e:
            self.upload_errors.append(f"Unexpected error: {e}")
            return False

    async def execute(self) -> Dict[str, Any]:
        """Execute the post creation asynchronously."""
        req_text, data = await async_get_session_data(self.session, self.cookie)

        if not data:
            return {
                'status': 'failed',
                'id': None,
                'message': 'Failed to extract session data',
                'upload_errors': self.upload_errors
            }

        # Upload images
        for source in self.image_sources:
            await self._upload_photo(source, data)

        try:
            session_id = safe_regex_search(r'"sessionID":"(.*?)"', req_text)
            if not session_id:
                raise SessionError("Could not extract session ID")

            variables = {
                "input": {
                    "composer_entry_point": "inline_composer",
                    "composer_source_surface": "timeline",
                    "idempotence_token": f"{session_id}_FEED",
                    "source": "WWW",
                    "attachments": self.attachments,
                    "audience": {
                        "privacy": {
                            "allow": [],
                            "base_state": self.privacy,
                            "deny": [],
                            "tag_expansion_state": "UNSPECIFIED"
                        }
                    },
                    "message": {"ranges": [], "text": self.text},
                    "with_tags_ids": self.tag,
                    "inline_activities": [],
                    "explicit_place_id": "0",
                    "text_format_preset_id": "0",
                    "logging": {"composer_session_id": session_id},
                    "navigation_data": {"attribution_id_v2": "ProfileCometTimelineListViewRoot.react,comet.profile.timeline.list,via_cold_start,1703620101353,887511,190055527696468,,"},
                    "tracking": [None],
                    "event_share_metadata": {"surface": "newsfeed"},
                    "actor_id": data['__user'],
                    "client_mutation_id": "1"
                },
                "displayCommentsFeedbackContext": None,
                "displayCommentsContextEnableComment": None,
                "displayCommentsContextIsAdPreview": None,
                "displayCommentsContextIsAggregatedShare": None,
                "displayCommentsContextIsStorySet": None,
                "feedLocation": "TIMELINE",
                "feedbackSource": 0,
                "focusCommentID": None,
                "gridMediaWidth": 230,
                "groupID": None,
                "scale": 1.5,
                "privacySelectorRenderLocation": "COMET_STREAM",
                "checkPhotosToReelsUpsellEligibility": True,
                "renderLocation": "timeline",
                "useDefaultActor": False,
                "inviteShortLinkKey": None,
                "isFeed": False,
                "isFundraiser": False,
                "isFunFactPost": False,
                "isGroup": False,
                "isEvent": False,
                "isTimeline": True,
                "isSocialLearning": False,
                "isPageNewsFeed": False,
                "isProfileReviews": False,
                "isWorkSharedDraft": False,
                "UFI2CommentsProvider_commentsKey": "ProfileCometTimelineRoute",
                "hashtag": None,
                "canUserManageOffers": False,
                "__relay_internal__pv__CometUFIIsRTAEnabledrelayprovider": False,
                "__relay_internal__pv__CometUFIReactionsEnableShortNamerelayprovider": False,
                "__relay_internal__pv__IsWorkUserrelayprovider": False,
                "__relay_internal__pv__IsMergQAPollsrelayprovider": False,
                "__relay_internal__pv__StoriesArmadilloReplyEnabledrelayprovider": False,
                "__relay_internal__pv__StoriesRingrelayprovider": False
            }

            data.update({
                'fb_api_caller_class': 'RelayModern',
                'fb_api_req_friendly_name': 'ComposerStoryCreateMutation',
                'variables': json.dumps(variables),
                'server_timestamps': True,
                'doc_id': DOC_IDS['composer_create']
            })

            async with self.session.post(
                ENDPOINTS['graphql'],
                data=data,
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ) as response:
                text = await response.text()

            # Check for duplicate post error (language-agnostic patterns)
            duplicate_patterns = ['duplicate', 'duplikat', 'duplicado', 'dupliziert', 'identique', '"error_summary"']
            if any(p in text.lower() for p in duplicate_patterns) and not safe_regex_search(r'"post_id":"(.*?)"', text):
                return {
                    'status': 'failed',
                    'id': None,
                    'message': 'Duplicate post detected',
                    'upload_errors': self.upload_errors
                }

            post_id = safe_regex_search(r'"post_id":"(.*?)"', text)
            if post_id:
                return {
                    'status': 'success',
                    'id': post_id,
                    'message': None,
                    'upload_errors': self.upload_errors if self.upload_errors else None
                }

            return {
                'status': 'failed',
                'id': None,
                'message': 'Failed to create post',
                'upload_errors': self.upload_errors
            }

        except Exception as e:
            logger.error(f"Async post creation failed: {e}")
            return {
                'status': 'failed',
                'id': None,
                'message': f'An error occurred: {e}',
                'upload_errors': self.upload_errors
            }


class AsyncPostToGroup:
    """
    Asynchronously create a post in a Facebook group.

    Example:
        >>> async with aiohttp.ClientSession() as session:
        ...     post = AsyncPostToGroup(session, cookie, group="123", text="Hello group!")
        ...     result = await post.execute()
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        cookie: str,
        group: str,
        text: str = None,
        url: List[str] = None,
        tag: List[str] = None
    ):
        if not group:
            raise ValidationError("Parameter 'group' is required")

        self.session = session
        self.cookie = cookie
        self.group = str(group)
        self.text = text or ''
        self.tag = tag or []
        self.image_sources = url or []
        self.attachments = []
        self.upload_errors = []

    async def _upload_photo(self, source: str, data: dict) -> bool:
        """Upload a photo asynchronously."""
        try:
            image_data, filename, content_type = await async_load_image(self.session, source)

            form_data = aiohttp.FormData()
            form_data.add_field('file', image_data, filename=filename, content_type=content_type)

            upload_data = data.copy()
            upload_data.update({
                'source': '8',
                'profile_id': data.get('__user', ''),
                'waterfallxapp': 'comet',
                'upload_id': 'jsc_c_1g'
            })

            for key, value in upload_data.items():
                form_data.add_field(key, str(value))

            async with self.session.post(
                ENDPOINTS['upload_photo'],
                data=form_data,
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ) as response:
                text = await response.text()

            photo_id = safe_regex_search(r'"photoID":"(.*?)"', text)
            if photo_id:
                self.attachments.append({"photo": {"id": photo_id}})
                return True
            else:
                self.upload_errors.append(f"Failed to get photo ID: {filename}")
                return False

        except ImageUploadError as e:
            self.upload_errors.append(str(e))
            return False
        except Exception as e:
            self.upload_errors.append(f"Unexpected error: {e}")
            return False

    async def execute(self) -> Dict[str, Any]:
        """Execute the group post creation asynchronously."""
        req_text, data = await async_get_session_data(self.session, self.cookie)

        if not data:
            return {
                'status': 'failed',
                'id': None,
                'message': 'Failed to extract session data',
                'upload_errors': self.upload_errors
            }

        for source in self.image_sources:
            await self._upload_photo(source, data)

        try:
            session_id = safe_regex_search(r'"sessionID":"(.*?)"', req_text)
            if not session_id:
                raise SessionError("Could not extract session ID")

            variables = {
                "input": {
                    "composer_entry_point": "publisher_bar_media",
                    "composer_source_surface": "group",
                    "composer_type": "group",
                    "logging": {"composer_session_id": session_id},
                    "source": "WWW",
                    "attachments": self.attachments,
                    "message": {"ranges": [], "text": self.text},
                    "with_tags_ids": self.tag,
                    "inline_activities": [],
                    "explicit_place_id": "0",
                    "text_format_preset_id": "0",
                    "navigation_data": {"attribution_id_v2": "CometGroupDiscussionRoot.react,comet.group,unexpected,1703627156789,472005,2361831622,,"},
                    "tracking": [None],
                    "event_share_metadata": {"surface": "newsfeed"},
                    "audience": {"to_id": self.group},
                    "actor_id": data['__user'],
                    "client_mutation_id": "1"
                },
                "displayCommentsFeedbackContext": None,
                "displayCommentsContextEnableComment": None,
                "displayCommentsContextIsAdPreview": None,
                "displayCommentsContextIsAggregatedShare": None,
                "displayCommentsContextIsStorySet": None,
                "feedLocation": "GROUP",
                "feedbackSource": 0,
                "focusCommentID": None,
                "gridMediaWidth": None,
                "groupID": None,
                "scale": 1.5,
                "privacySelectorRenderLocation": "COMET_STREAM",
                "checkPhotosToReelsUpsellEligibility": False,
                "renderLocation": "group",
                "useDefaultActor": False,
                "inviteShortLinkKey": None,
                "isFeed": False,
                "isFundraiser": False,
                "isFunFactPost": False,
                "isGroup": True,
                "isEvent": False,
                "isTimeline": False,
                "isSocialLearning": False,
                "isPageNewsFeed": False,
                "isProfileReviews": False,
                "isWorkSharedDraft": False,
                "UFI2CommentsProvider_commentsKey": "CometGroupDiscussionRootSuccessQuery",
                "hashtag": None,
                "canUserManageOffers": False,
                "__relay_internal__pv__CometUFIIsRTAEnabledrelayprovider": False,
                "__relay_internal__pv__CometUFIReactionsEnableShortNamerelayprovider": False,
                "__relay_internal__pv__IsWorkUserrelayprovider": False,
                "__relay_internal__pv__IsMergQAPollsrelayprovider": False,
                "__relay_internal__pv__StoriesArmadilloReplyEnabledrelayprovider": False,
                "__relay_internal__pv__StoriesRingrelayprovider": False
            }

            data.update({
                'fb_api_caller_class': 'RelayModern',
                'fb_api_req_friendly_name': 'ComposerStoryCreateMutation',
                'variables': json.dumps(variables),
                'server_timestamps': True,
                'doc_id': DOC_IDS['composer_create']
            })

            async with self.session.post(
                ENDPOINTS['graphql'],
                data=data,
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ) as response:
                text = (await response.text()).replace('\\', '')

            # Check for account restriction (language-agnostic patterns)
            restriction_patterns = [
                'restricted', 'dibatasi', 'restringido', 'eingeschränkt', 'restreint', 'limitado',
                '"is_restricted":true', '"can_post":false'
            ]
            if any(p in text.lower() for p in restriction_patterns) and not safe_regex_search(r'"post_id":"(.*?)"', text):
                return {
                    'status': 'failed',
                    'id': None,
                    'message': 'Your account is currently restricted from posting to groups',
                    'upload_errors': self.upload_errors
                }

            post_id = safe_regex_search(r'"post_id":"(.*?)"', text)
            if post_id:
                if f'pending_posts/{post_id}' in text:
                    return {
                        'status': 'pending',
                        'id': post_id,
                        'message': 'Post is pending admin approval',
                        'upload_errors': self.upload_errors if self.upload_errors else None
                    }

                return {
                    'status': 'success',
                    'id': post_id,
                    'message': None,
                    'upload_errors': self.upload_errors if self.upload_errors else None
                }

            return {
                'status': 'failed',
                'id': None,
                'message': 'Failed to create post',
                'upload_errors': self.upload_errors
            }

        except Exception as e:
            logger.error(f"Async group post failed: {e}")
            return {
                'status': 'failed',
                'id': None,
                'message': f'An error occurred: {e}',
                'upload_errors': self.upload_errors
            }


class AsyncReactToPost:
    """Asynchronously add a reaction to a post."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        cookie: str,
        post: str,
        react: int = 1
    ):
        self.session = session
        self.cookie = cookie
        self.url = convert_url(post)
        self.react = react

    async def execute(self) -> Dict[str, Any]:
        """Execute the reaction asynchronously."""
        reaction_info = REACTIONS.get(self.react, REACTIONS[1])
        react_type = reaction_info['name']
        react_id = reaction_info['id']

        try:
            async with self.session.get(
                self.url,
                headers=get_headers_get(),
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ) as response:
                req_text = await response.text()

            _, data = await async_get_session_data(self.session, self.cookie)
            if not data:
                return {'status': 'failed', 'react_type': react_type, 'message': 'Session error'}

            session_id = safe_regex_search(r'"sessionID":"(.*?)"', req_text)
            feedback_id = safe_regex_search(
                r'"feedback":\{"associated_group":null,"id":"(.*?)"\},"is_story_civic":null',
                req_text
            ) or safe_regex_findall(r'"feedback_id":"(.*?)"', req_text, index=-1)

            if not feedback_id:
                return {'status': 'failed', 'react_type': react_type, 'message': 'Could not extract post ID'}

            encrypted_tracking = safe_regex_findall(r'"encrypted_tracking":"(.*?)"', req_text, index=0)

            variables = {
                "input": {
                    "attribution_id_v2": "CometSinglePostRoot.react,comet.post.single,via_cold_start,1697303736286,689359,,",
                    "feedback_id": feedback_id,
                    "feedback_reaction_id": react_id,
                    "feedback_source": "OBJECT",
                    "is_tracking_encrypted": True,
                    "tracking": [encrypted_tracking],
                    "session_id": session_id,
                    "actor_id": data['__user'],
                    "client_mutation_id": "1"
                },
                "useDefaultActor": False,
                "scale": 1.5
            }

            data.update({
                'fb_api_caller_class': 'RelayModern',
                'fb_api_req_friendly_name': 'CometUFIFeedbackReactMutation',
                'variables': json.dumps(variables),
                'server_timestamps': True,
                'doc_id': DOC_IDS['reaction']
            })

            async with self.session.post(
                ENDPOINTS['graphql'],
                data=data,
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ) as response:
                text = await response.text()

            if '"feedback_react":{"feedback":{"can_viewer_react":true' in text:
                return {'status': 'success', 'react_type': react_type, 'message': None}

            return {'status': 'failed', 'react_type': react_type, 'message': 'Reaction failed'}

        except Exception as e:
            return {'status': 'failed', 'react_type': react_type, 'message': str(e)}


class AsyncStart:
    """
    Async main entry point for FBTools.

    Use as an async context manager for automatic session handling.

    Example:
        >>> async with AsyncStart(cookie="your_cookie") as fb:
        ...     if fb.IsValid:
        ...         result = await fb.PostToFeed(text="Hello!")
        ...         print(result)

    Or manage the session manually:
        >>> fb = AsyncStart(cookie="your_cookie")
        >>> await fb.connect()
        >>> if fb.IsValid:
        ...     result = await fb.PostToFeed(text="Hello!")
        >>> await fb.close()
    """

    def __init__(self, cookie: str = None):
        self.cookie = cookie
        self.IsValid = False
        self._session: Optional[aiohttp.ClientSession] = None
        self._owns_session = True

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def connect(self) -> bool:
        """
        Initialize the async session and validate cookie.

        Returns:
            True if connection and validation succeeded.
        """
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._owns_session = True

        if self.cookie:
            try:
                async with self._session.get(
                    'https://www.facebook.com/profile.php',
                    headers=get_headers_get(USER_AGENT_WINDOWS),
                    cookies={'cookie': self.cookie},
                    allow_redirects=True
                ) as response:
                    text = await response.text()

                actor_id = safe_regex_search(r'"actorID":"(.*?)"', text)
                if actor_id:
                    self.IsValid = True
                    logger.info("Async cookie validation successful")
                else:
                    logger.warning("Async cookie validation failed")

            except Exception as e:
                logger.error(f"Async connection failed: {e}")

        return self.IsValid

    async def close(self):
        """Close the async session."""
        if self._session and self._owns_session:
            await self._session.close()
            self._session = None

    async def PostToFeed(
        self,
        text: str = None,
        url: List[str] = None,
        tag: List[str] = None,
        privacy: int = None
    ) -> Dict[str, Any]:
        """
        Asynchronously create a post on your feed.

        Args:
            text: Post text content.
            url: List of image URLs or file paths.
            tag: List of friend IDs to tag.
            privacy: Privacy level (1=EVERYONE, 2=FRIENDS, 3=SELF).

        Returns:
            Dict with 'status', 'id', 'message', and 'upload_errors' keys.
        """
        if not self._session:
            return {'status': 'failed', 'id': None, 'message': 'Not connected'}

        post = AsyncPostToFeed(
            self._session, self.cookie,
            text=text, url=url, tag=tag, privacy=privacy
        )
        return await post.execute()

    async def PostToGroup(
        self,
        group: str,
        text: str = None,
        url: List[str] = None,
        tag: List[str] = None
    ) -> Dict[str, Any]:
        """
        Asynchronously create a post in a group.

        Args:
            group: Group ID (required).
            text: Post text content.
            url: List of image URLs or file paths.
            tag: List of friend IDs to tag.

        Returns:
            Dict with 'status', 'id', 'message', and 'upload_errors' keys.
        """
        if not self._session:
            return {'status': 'failed', 'id': None, 'message': 'Not connected'}

        post = AsyncPostToGroup(
            self._session, self.cookie,
            group=group, text=text, url=url, tag=tag
        )
        return await post.execute()

    async def ReactToPost(self, post: str, react: int = 1) -> Dict[str, Any]:
        """
        Asynchronously add a reaction to a post.

        Args:
            post: Post URL or ID.
            react: Reaction type (1=Like, 2=Love, etc.).

        Returns:
            Dict with 'status', 'react_type', and 'message' keys.
        """
        if not self._session:
            return {'status': 'failed', 'react_type': None, 'message': 'Not connected'}

        reaction = AsyncReactToPost(
            self._session, self.cookie,
            post=post, react=react
        )
        return await reaction.execute()
