"""
Facebook automation module for posting, commenting, reacting, and sharing.

This module provides classes for automating various Facebook interactions
including posting to feeds and groups, commenting, reacting, and sharing.
"""

import re
import json
import logging
import mimetypes
import urllib.request
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

from .Tools import convert_url, get_session_data, safe_regex_search, safe_regex_findall, extract_photo_id, extract_session_id
from .constants import (
    get_headers_get,
    get_headers_post,
    ENDPOINTS,
    DOC_IDS,
    REACTIONS,
    PRIVACY_LEVELS,
    IMAGE_DOWNLOAD_TIMEOUT,
)
from .exceptions import (
    ValidationError,
    PostError,
    GroupPostError,
    ImageUploadError,
    CommentError,
    ReactionError,
    ShareError,
    RateLimitError,
    SessionError,
)

logger = logging.getLogger('FBTools')


def load_image(source: str, timeout: int = IMAGE_DOWNLOAD_TIMEOUT) -> tuple:
    """
    Load an image from a URL or local file path.

    Supports loading images from:
    - HTTP/HTTPS URLs (including Imgur, direct image links, etc.)
    - Local file paths

    Args:
        source: URL or file path to the image.
        timeout: Timeout in seconds for URL downloads (default: 30).

    Returns:
        Tuple of (image_bytes, filename, content_type).

    Raises:
        ImageUploadError: If the image cannot be loaded.

    Example:
        >>> data, name, ctype = load_image('https://i.imgur.com/example.jpg')
        >>> data, name, ctype = load_image('/path/to/image.png')
    """
    source = str(source).strip()

    # Check if it's a URL
    if source.startswith(('http://', 'https://')):
        try:
            logger.debug(f"Downloading image from URL: {source}")
            request = urllib.request.Request(
                source,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                image_data = response.read()
                content_type = response.headers.get('Content-Type', 'image/jpeg')

                # Determine filename from URL or content type
                url_path = source.split('?')[0]
                filename = url_path.split('/')[-1]

                # If filename has no extension, add one based on content type
                if '.' not in filename:
                    ext = mimetypes.guess_extension(content_type.split(';')[0]) or '.jpg'
                    filename = f'image{ext}'

                logger.debug(f"Downloaded image: {filename} ({len(image_data)} bytes)")
                return image_data, filename, content_type

        except urllib.error.URLError as e:
            raise ImageUploadError(f"Failed to download image from URL: {e}")
        except TimeoutError:
            raise ImageUploadError(f"Timeout downloading image from: {source}")
        except Exception as e:
            raise ImageUploadError(f"Error loading image from URL: {e}")

    # Check if it's a local file
    else:
        file_path = Path(source)
        if not file_path.exists():
            raise ImageUploadError(f"File not found: {source}")

        if not file_path.is_file():
            raise ImageUploadError(f"Path is not a file: {source}")

        try:
            logger.debug(f"Loading image from file: {source}")
            image_data = file_path.read_bytes()
            filename = file_path.name
            content_type = mimetypes.guess_type(source)[0] or 'image/jpeg'

            logger.debug(f"Loaded image: {filename} ({len(image_data)} bytes)")
            return image_data, filename, content_type

        except PermissionError:
            raise ImageUploadError(f"Permission denied reading file: {source}")
        except Exception as e:
            raise ImageUploadError(f"Error reading file: {e}")


class PostToFeed:
    """
    Create a post on the user's personal feed/timeline.

    Supports text posts with optional images and friend tags.

    Args:
        r: Requests session object.
        cookie: Facebook authentication cookie.
        group: Unused parameter (kept for API compatibility).
        text: Post text content (optional).
        url: List of image URLs or file paths to attach (optional).
        tag: List of friend IDs to tag (optional).
        privacy: Privacy level - 1=EVERYONE, 2=FRIENDS, 3=SELF (optional).

    Example:
        >>> post = PostToFeed(r=session, cookie=cookie, text="Hello World!")
        >>> result = post.Execute()
        >>> print(result['status'])  # 'success' or 'failed'
    """

    def __init__(
        self,
        r=None,
        cookie: str = None,
        group=None,
        text: str = None,
        url: List[str] = None,
        tag: List[str] = None,
        privacy: int = None
    ):
        self.r = r
        self.cookie = cookie
        self.text = text or ''
        self.tag = tag or []
        self.attachments = []
        self.upload_errors = []

        # Set privacy level
        self.privacy = PRIVACY_LEVELS.get(privacy, 'EVERYONE')

        # Get session data
        try:
            self.req = self.r.get(
                ENDPOINTS['base'] + '/',
                headers=get_headers_get(),
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ).text
        except Exception as e:
            logger.error(f"Failed to fetch session: {e}")
            self.req = None

        self.Data = get_session_data(self.req) if self.req else {}

        # Upload images if provided
        if url:
            for image_source in url:
                self._upload_photo(image_source)

    def _upload_photo(self, source: str) -> bool:
        """
        Upload a photo for attachment.

        Args:
            source: Image URL or local file path.

        Returns:
            True if upload succeeded, False otherwise.
        """
        try:
            image_data, filename, content_type = load_image(source)
            file = {'file': (filename, image_data, content_type)}

            data = self.Data.copy()
            data.update({
                'source': '8',
                'profile_id': data.get('__user', ''),
                'waterfallxapp': 'comet',
                'upload_id': 'jsc_c_1g'
            })

            response = self.r.post(
                ENDPOINTS['upload_photo'],
                data=data,
                files=file,
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ).text

            photo_id = extract_photo_id(response)
            if photo_id:
                self.attachments.append({"photo": {"id": photo_id}})
                logger.info(f"Uploaded photo: {filename} (ID: {photo_id})")
                return True
            else:
                # Log response for debugging (truncated)
                logger.debug(f"Photo upload response (truncated): {response[:500]}")
                error_msg = f"Failed to get photo ID after upload: {filename}"
                logger.warning(error_msg)
                self.upload_errors.append(error_msg)
                return False

        except ImageUploadError as e:
            error_msg = str(e)
            logger.error(f"Image upload failed: {error_msg}")
            self.upload_errors.append(error_msg)
            return False
        except Exception as e:
            error_msg = f"Unexpected error uploading {source}: {e}"
            logger.error(error_msg)
            self.upload_errors.append(error_msg)
            return False

    def Execute(self) -> Dict[str, Any]:
        """
        Execute the post creation.

        Returns:
            Dictionary with keys:
            - status: 'success' or 'failed'
            - id: Post ID if successful, None otherwise
            - message: Error message if failed, None otherwise
            - upload_errors: List of image upload errors (if any)
        """
        if not self.r or not self.cookie:
            return {
                'status': 'failed',
                'id': None,
                'message': 'Invalid session: cookie is required',
                'upload_errors': self.upload_errors
            }

        if not self.Data:
            return {
                'status': 'failed',
                'id': None,
                'message': 'Failed to extract session data',
                'upload_errors': self.upload_errors
            }

        try:
            session_id = extract_session_id(self.req)
            # session_id is always valid (extract_session_id generates fallback if needed)

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
                    "navigation_data": {
                        "attribution_id_v2": "ProfileCometTimelineListViewRoot.react,comet.profile.timeline.list,via_cold_start,1703620101353,887511,190055527696468,,"
                    },
                    "tracking": [None],
                    "event_share_metadata": {"surface": "newsfeed"},
                    "actor_id": self.Data['__user'],
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

            self.Data.update({
                'fb_api_caller_class': 'RelayModern',
                'fb_api_req_friendly_name': 'ComposerStoryCreateMutation',
                'variables': json.dumps(variables),
                'server_timestamps': True,
                'doc_id': DOC_IDS['composer_create']
            })

            response = self.r.post(
                ENDPOINTS['graphql'],
                data=self.Data,
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ).text

            # Check for duplicate post error (language-agnostic patterns)
            duplicate_patterns = [
                '"error_summary"',
                'duplicate',
                'duplikat',  # Indonesian
                'duplicado',  # Spanish
                'dupliziert',  # German
                'identique',  # French
            ]
            if any(p in response.lower() for p in duplicate_patterns) and not safe_regex_search(r'"post_id":"(.*?)"', response):
                return {
                    'status': 'failed',
                    'id': None,
                    'message': 'Duplicate post detected - cannot create identical post',
                    'upload_errors': self.upload_errors
                }

            # Extract post ID
            post_id = safe_regex_search(r'"post_id":"(.*?)"', response)
            if post_id:
                logger.info(f"Post created successfully: {post_id}")
                return {
                    'status': 'success',
                    'id': post_id,
                    'message': None,
                    'upload_errors': self.upload_errors if self.upload_errors else None
                }

            return {
                'status': 'failed',
                'id': None,
                'message': 'Failed to create post - no post ID in response',
                'upload_errors': self.upload_errors
            }

        except SessionError as e:
            return {
                'status': 'failed',
                'id': None,
                'message': str(e),
                'upload_errors': self.upload_errors
            }
        except Exception as e:
            logger.error(f"Post creation failed: {e}")
            return {
                'status': 'failed',
                'id': None,
                'message': f'An error occurred: {e}',
                'upload_errors': self.upload_errors
            }


class PostToGroup:
    """
    Create a post in a Facebook group.

    Supports text posts with optional images and friend tags.

    Args:
        r: Requests session object.
        cookie: Facebook authentication cookie.
        group: Group ID (required).
        text: Post text content (optional).
        url: List of image URLs or file paths to attach (optional).
        tag: List of friend IDs to tag (optional).
        privacy: Unused for groups (group privacy applies).

    Raises:
        ValidationError: If group ID is not provided.

    Example:
        >>> post = PostToGroup(r=session, cookie=cookie, group="123456", text="Hello Group!")
        >>> result = post.Execute()
    """

    def __init__(
        self,
        r=None,
        cookie: str = None,
        group: str = None,
        text: str = None,
        url: List[str] = None,
        tag: List[str] = None,
        privacy: int = None
    ):
        if not group:
            raise ValidationError("Parameter 'group' is required for PostToGroup")

        self.r = r
        self.cookie = cookie
        self.group = str(group)
        self.text = text or ''
        self.tag = tag or []
        self.attachments = []
        self.upload_errors = []

        # Get session data
        try:
            self.req = self.r.get(
                ENDPOINTS['base'] + '/',
                headers=get_headers_get(),
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ).text
        except Exception as e:
            logger.error(f"Failed to fetch session: {e}")
            self.req = None

        self.Data = get_session_data(self.req) if self.req else {}

        # Upload images if provided
        if url:
            for image_source in url:
                self._upload_photo(image_source)

    def _upload_photo(self, source: str) -> bool:
        """Upload a photo for attachment."""
        try:
            image_data, filename, content_type = load_image(source)
            file = {'file': (filename, image_data, content_type)}

            data = self.Data.copy()
            data.update({
                'source': '8',
                'profile_id': data.get('__user', ''),
                'waterfallxapp': 'comet',
                'upload_id': 'jsc_c_1g'
            })

            response = self.r.post(
                ENDPOINTS['upload_photo'],
                data=data,
                files=file,
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ).text

            photo_id = extract_photo_id(response)
            if photo_id:
                self.attachments.append({"photo": {"id": photo_id}})
                logger.info(f"Uploaded photo: {filename} (ID: {photo_id})")
                return True
            else:
                # Log response for debugging (truncated)
                logger.debug(f"Photo upload response (truncated): {response[:500]}")
                error_msg = f"Failed to get photo ID after upload: {filename}"
                logger.warning(error_msg)
                self.upload_errors.append(error_msg)
                return False

        except ImageUploadError as e:
            error_msg = str(e)
            logger.error(f"Image upload failed: {error_msg}")
            self.upload_errors.append(error_msg)
            return False
        except Exception as e:
            error_msg = f"Unexpected error uploading {source}: {e}"
            logger.error(error_msg)
            self.upload_errors.append(error_msg)
            return False

    def Execute(self) -> Dict[str, Any]:
        """
        Execute the group post creation.

        Returns:
            Dictionary with keys:
            - status: 'success', 'pending', or 'failed'
            - id: Post ID if successful, None otherwise
            - message: Status message or error description
            - upload_errors: List of image upload errors (if any)
        """
        if not self.r or not self.cookie:
            return {
                'status': 'failed',
                'id': None,
                'message': 'Invalid session: cookie is required',
                'upload_errors': self.upload_errors
            }

        if not self.Data:
            return {
                'status': 'failed',
                'id': None,
                'message': 'Failed to extract session data',
                'upload_errors': self.upload_errors
            }

        try:
            session_id = extract_session_id(self.req)
            # session_id is always valid (extract_session_id generates fallback if needed)

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
                    "navigation_data": {
                        "attribution_id_v2": "CometGroupDiscussionRoot.react,comet.group,unexpected,1703627156789,472005,2361831622,,;GroupsCometPeopleRoot.react,comet.group.admin.people,unexpected,1703627121338,335432,,,;CometGroupDiscussionRoot.react,comet.group,via_cold_start,1703627109831,115805,2361831622,,"
                    },
                    "tracking": [None],
                    "event_share_metadata": {"surface": "newsfeed"},
                    "audience": {"to_id": self.group},
                    "actor_id": self.Data['__user'],
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

            self.Data.update({
                'fb_api_caller_class': 'RelayModern',
                'fb_api_req_friendly_name': 'ComposerStoryCreateMutation',
                'variables': json.dumps(variables),
                'server_timestamps': True,
                'doc_id': DOC_IDS['composer_create']
            })

            response = self.r.post(
                ENDPOINTS['graphql'],
                data=self.Data,
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ).text.replace('\\', '')

            # Check for account restriction (language-agnostic patterns)
            restriction_patterns = [
                'restricted',
                'dibatasi',  # Indonesian
                'restringido',  # Spanish
                'eingeschränkt',  # German
                'restreint',  # French
                'limitado',  # Portuguese
                '"is_restricted":true',
                '"can_post":false',
            ]
            if any(p in response.lower() for p in restriction_patterns) and not safe_regex_search(r'"post_id":"(.*?)"', response):
                logger.warning("Account is restricted from posting to groups")
                return {
                    'status': 'failed',
                    'id': None,
                    'message': 'Your account is currently restricted from posting to groups',
                    'upload_errors': self.upload_errors
                }

            # Extract post ID
            post_id = safe_regex_search(r'"post_id":"(.*?)"', response)
            if post_id:
                # Check if post is pending approval
                if f'pending_posts/{post_id}' in response:
                    logger.info(f"Post pending approval: {post_id}")
                    return {
                        'status': 'pending',
                        'id': post_id,
                        'message': 'Post is pending admin approval',
                        'upload_errors': self.upload_errors if self.upload_errors else None
                    }

                logger.info(f"Group post created successfully: {post_id}")
                return {
                    'status': 'success',
                    'id': post_id,
                    'message': None,
                    'upload_errors': self.upload_errors if self.upload_errors else None
                }

            return {
                'status': 'failed',
                'id': None,
                'message': 'Failed to create post - no post ID in response',
                'upload_errors': self.upload_errors
            }

        except SessionError as e:
            return {
                'status': 'failed',
                'id': None,
                'message': str(e),
                'upload_errors': self.upload_errors
            }
        except Exception as e:
            logger.error(f"Group post creation failed: {e}")
            return {
                'status': 'failed',
                'id': None,
                'message': f'An error occurred: {e}',
                'upload_errors': self.upload_errors
            }


class CommentToPost:
    """
    Add a comment to a Facebook post.

    Supports text comments with optional photo and user tags.

    Args:
        r: Requests session object.
        cookie: Facebook authentication cookie.
        post: Post URL or ID to comment on.
        text: Comment text content (optional).
        photo: Photo URL or file path to attach (optional).
        tag: List of user IDs to tag (optional).

    Example:
        >>> comment = CommentToPost(r=session, cookie=cookie, post="123456", text="Nice post!")
        >>> result = comment.Execute()
    """

    def __init__(
        self,
        r=None,
        cookie: str = None,
        post: str = None,
        text: str = None,
        photo: str = None,
        tag: List[str] = None
    ):
        self.r = r
        self.cookie = cookie
        self.url = convert_url(post)
        self.text = text or ''
        self.photo = []
        self.upload_error = None

        # Format tags
        if tag:
            self.tag = [{"entity": {"id": i}, "length": 100, "offset": 100} for i in tag]
        else:
            self.tag = []

        # Get session data
        try:
            self.req = self.r.get(
                self.url,
                headers=get_headers_get(),
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ).text
        except Exception as e:
            logger.error(f"Failed to fetch post: {e}")
            self.req = None

        self.Data = get_session_data(self.req) if self.req else {}

        # Upload photo if provided
        if photo:
            self._upload_photo(photo)

    def _upload_photo(self, source: str) -> bool:
        """Upload a photo for the comment."""
        try:
            image_data, filename, content_type = load_image(source)
            file = {'file': (filename, image_data, content_type)}

            data = self.Data.copy()
            data.update({
                'source': '8',
                'profile_id': data.get('__user', ''),
                'waterfallxapp': 'comet',
                'upload_id': 'jsc_c_1g'
            })

            response = self.r.post(
                ENDPOINTS['upload_comment_photo'],
                data=data,
                files=file,
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ).text

            photo_id = safe_regex_search(r'"fbid":(.*?),', response)
            if photo_id:
                self.photo = [{"media": {"id": photo_id}}]
                logger.info(f"Uploaded comment photo (ID: {photo_id})")
                return True
            else:
                self.upload_error = f"Failed to get photo ID: {filename}"
                logger.warning(self.upload_error)
                return False

        except ImageUploadError as e:
            self.upload_error = str(e)
            logger.error(f"Comment photo upload failed: {self.upload_error}")
            return False
        except Exception as e:
            self.upload_error = f"Unexpected error: {e}"
            logger.error(self.upload_error)
            return False

    def Execute(self) -> Dict[str, Any]:
        """
        Execute the comment creation.

        Returns:
            Dictionary with keys:
            - status: 'success' or 'failed'
            - id: Comment ID if successful, None otherwise
            - message: Error message if failed, None otherwise
        """
        if not self.r or not self.cookie:
            return {'status': 'failed', 'id': None, 'message': 'Invalid session: cookie is required'}

        if not self.Data:
            return {'status': 'failed', 'id': None, 'message': 'Failed to extract session data'}

        try:
            session_id = extract_session_id(self.req)
            client_id = safe_regex_search(r'"clientID":"(.*?)"', self.req)

            if not session_id or not client_id:
                raise SessionError("Could not extract session/client ID")

            # Extract feedback ID (post identifier)
            feedback_id = safe_regex_search(
                r'"feedback":\{"associated_group":null,"id":"(.*?)"\},"is_story_civic":null',
                self.req
            )
            if not feedback_id:
                feedback_id = safe_regex_findall(r'"feedback_id":"(.*?)"', self.req, index=-1)

            if not feedback_id:
                raise CommentError("Could not extract feedback ID from post")

            # Extract tracking data
            tracking = safe_regex_findall(
                r'\{"action_link":null,"badge":null,"follow_button":null\},"encrypted_tracking":"(.*?)"\},"__module_operation_CometFeedStoryTitleSection_story"',
                self.req, index=-1
            )
            if not tracking:
                tracking = safe_regex_findall(r'"encrypted_tracking":"(.*?)"', self.req, index=0)

            vir = {
                "assistant_caller": "comet_above_composer",
                "conversation_guide_session_id": session_id,
                "conversation_guide_shown": None
            }

            variables = {
                "feedLocation": "PERMALINK",
                "feedbackSource": 2,
                "groupID": None,
                "input": {
                    "client_mutation_id": "1",
                    "actor_id": self.Data['__user'],
                    "attachments": self.photo,
                    "feedback_id": feedback_id,
                    "formatting_style": None,
                    "message": {"ranges": self.tag, "text": self.text},
                    "attribution_id_v2": "CometSinglePostRoot.react,comet.post.single,via_cold_start,1703691784875,275571,,,",
                    "vod_video_timestamp": None,
                    "is_tracking_encrypted": True,
                    "tracking": [tracking, json.dumps(vir)],
                    "feedback_source": "OBJECT",
                    "idempotence_token": f"client:{client_id}",
                    "session_id": session_id
                },
                "inviteShortLinkKey": None,
                "renderLocation": None,
                "scale": 1.5,
                "useDefaultActor": False,
                "focusCommentID": None
            }

            self.Data.update({
                'fb_api_caller_class': 'RelayModern',
                'fb_api_req_friendly_name': 'useCometUFICreateCommentMutation',
                'variables': json.dumps(variables),
                'server_timestamps': True,
                'doc_id': DOC_IDS['comment_create']
            })

            response = self.r.post(
                ENDPOINTS['graphql'],
                data=self.Data,
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ).text

            if '"data":{"comment_create":{"feedback"' in response:
                comment_id = safe_regex_search(r'comment_id=(.*?)"', response)
                logger.info(f"Comment created successfully: {comment_id}")
                return {'status': 'success', 'id': comment_id, 'message': None}
            else:
                return {
                    'status': 'failed',
                    'id': None,
                    'message': 'Comment may be flagged as spam or post has restrictions'
                }

        except (SessionError, CommentError) as e:
            return {'status': 'failed', 'id': None, 'message': str(e)}
        except Exception as e:
            logger.error(f"Comment creation failed: {e}")
            return {'status': 'failed', 'id': None, 'message': f'An error occurred: {e}'}


class ReactToPost:
    """
    Add a reaction to a Facebook post.

    Supported reactions: Like, Love, Haha, Wow, Care, Sad, Angry.

    Args:
        r: Requests session object.
        cookie: Facebook authentication cookie.
        post: Post URL or ID to react to.
        react: Reaction type (1=Like, 2=Love, 3=Haha, 4=Wow, 5=Care, 6=Sad, 7=Angry).

    Example:
        >>> reaction = ReactToPost(r=session, cookie=cookie, post="123456", react=2)
        >>> result = reaction.Execute()  # Adds 'Love' reaction
    """

    def __init__(
        self,
        r=None,
        cookie: str = None,
        post: str = None,
        react: int = None
    ):
        self.r = r
        self.cookie = cookie
        self.url = convert_url(post)
        self.react = react or 1  # Default to Like

        # Get session data
        try:
            self.req = self.r.get(
                self.url,
                headers=get_headers_get(),
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ).text
        except Exception as e:
            logger.error(f"Failed to fetch post: {e}")
            self.req = None

        self.Data = get_session_data(self.req) if self.req else {}

    def Execute(self) -> Dict[str, Any]:
        """
        Execute the reaction.

        Returns:
            Dictionary with keys:
            - status: 'success' or 'failed'
            - react_type: Name of reaction (Like, Love, etc.)
            - message: Error message if failed, None otherwise
        """
        reaction_info = REACTIONS.get(self.react, REACTIONS[1])
        react_type = reaction_info['name']
        react_id = reaction_info['id']

        if not self.r or not self.cookie:
            return {'status': 'failed', 'react_type': react_type, 'message': 'Invalid session: cookie is required'}

        if not self.Data:
            return {'status': 'failed', 'react_type': react_type, 'message': 'Failed to extract session data'}

        try:
            session_id = extract_session_id(self.req)
            # session_id is always valid (extract_session_id generates fallback if needed)

            # Extract feedback ID
            feedback_id = safe_regex_search(
                r'"feedback":\{"associated_group":null,"id":"(.*?)"\},"is_story_civic":null',
                self.req
            )
            if not feedback_id:
                feedback_id = safe_regex_findall(r'"feedback_id":"(.*?)"', self.req, index=-1)

            if not feedback_id:
                raise ReactionError("Could not extract feedback ID from post")

            # Extract tracking data
            encrypted_tracking = safe_regex_findall(
                r'\{"action_link":null,"badge":null,"follow_button":null\},"encrypted_tracking":"(.*?)"\},"__module_operation_CometFeedStoryTitleSection_story"',
                self.req, index=-1
            )
            if not encrypted_tracking:
                encrypted_tracking = safe_regex_findall(r'"encrypted_tracking":"(.*?)"', self.req, index=0)

            variables = {
                "input": {
                    "attribution_id_v2": "CometSinglePostRoot.react,comet.post.single,via_cold_start,1697303736286,689359,,",
                    "feedback_id": feedback_id,
                    "feedback_reaction_id": react_id,
                    "feedback_source": "OBJECT",
                    "is_tracking_encrypted": True,
                    "tracking": [encrypted_tracking],
                    "session_id": session_id,
                    "actor_id": self.Data['__user'],
                    "client_mutation_id": "1"
                },
                "useDefaultActor": False,
                "scale": 1.5
            }

            self.Data.update({
                'fb_api_caller_class': 'RelayModern',
                'fb_api_req_friendly_name': 'CometUFIFeedbackReactMutation',
                'variables': json.dumps(variables),
                'server_timestamps': True,
                'doc_id': DOC_IDS['reaction']
            })

            response = self.r.post(
                ENDPOINTS['graphql'],
                data=self.Data,
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ).text

            if '"feedback_react":{"feedback":{"can_viewer_react":true' in response:
                logger.info(f"Reaction '{react_type}' added successfully")
                return {'status': 'success', 'react_type': react_type, 'message': None}
            else:
                return {
                    'status': 'failed',
                    'react_type': react_type,
                    'message': 'Failed to add reaction - may be spam or post has restrictions'
                }

        except (SessionError, ReactionError) as e:
            return {'status': 'failed', 'react_type': react_type, 'message': str(e)}
        except Exception as e:
            logger.error(f"Reaction failed: {e}")
            return {'status': 'failed', 'react_type': react_type, 'message': f'An error occurred: {e}'}


class ShareToFeed:
    """
    Share a post to the user's personal feed.

    Args:
        r: Requests session object.
        cookie: Facebook authentication cookie.
        post: Post URL or ID to share.
        group: Unused parameter (kept for API compatibility).
        text: Additional text to add to share (optional).
        tag: List of friend IDs to tag (optional).
        privacy: Privacy level - 1=EVERYONE, 2=FRIENDS, 3=SELF (optional).

    Example:
        >>> share = ShareToFeed(r=session, cookie=cookie, post="123456", text="Check this out!")
        >>> result = share.Execute()
    """

    def __init__(
        self,
        r=None,
        cookie: str = None,
        post: str = None,
        group=None,
        text: str = None,
        tag: List[str] = None,
        privacy: int = None
    ):
        self.r = r
        self.cookie = cookie
        self.url = convert_url(post)
        self.text = text or ''
        self.tag = tag or []
        self.privacy = PRIVACY_LEVELS.get(privacy, 'EVERYONE')

        # Get session data
        try:
            self.req = self.r.get(
                self.url,
                headers=get_headers_get(),
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ).text
        except Exception as e:
            logger.error(f"Failed to fetch post: {e}")
            self.req = None

        self.Data = get_session_data(self.req) if self.req else {}

    def Execute(self) -> Dict[str, Any]:
        """
        Execute the share to feed.

        Returns:
            Dictionary with keys:
            - status: 'success' or 'failed'
            - id: Share post ID if successful, None otherwise
            - message: Error message if failed, None otherwise
        """
        if not self.r or not self.cookie:
            return {'status': 'failed', 'id': None, 'message': 'Invalid session: cookie is required'}

        if not self.Data:
            return {'status': 'failed', 'id': None, 'message': 'Failed to extract session data'}

        try:
            session_id = extract_session_id(self.req)
            share_fbid = safe_regex_search(r'"share_fbid":"(.*?)"', self.req)

            if not session_id or not share_fbid:
                raise SessionError("Could not extract session ID or share ID")

            # Extract tracking data
            tracking = safe_regex_findall(
                r'\{"action_link":null,"badge":null,"follow_button":null\},"encrypted_tracking":"(.*?)"\},"__module_operation_CometFeedStoryTitleSection_story"',
                self.req, index=-1
            )
            if not tracking:
                tracking = safe_regex_findall(r'"encrypted_tracking":"(.*?)"', self.req, index=0)

            variables = {
                "input": {
                    "composer_entry_point": "share_modal",
                    "composer_source_surface": "feed_story",
                    "composer_type": "share",
                    "idempotence_token": f"{session_id}_FEED",
                    "source": "WWW",
                    "is_tracking_encrypted": True,
                    "tracking": [tracking, None],
                    "audience": {
                        "privacy": {
                            "allow": [],
                            "base_state": self.privacy,
                            "deny": [],
                            "tag_expansion_state": "UNSPECIFIED"
                        }
                    },
                    "message": {"ranges": [], "text": self.text},
                    "inline_activities": [],
                    "text_format_preset_id": "0",
                    "attachments": [{
                        "link": {
                            "share_scrape_data": json.dumps({
                                "share_type": 22,
                                "share_params": [int(share_fbid)]
                            })
                        }
                    }],
                    "with_tags_ids": self.tag,
                    "logging": {"composer_session_id": session_id},
                    "navigation_data": {
                        "attribution_id_v2": "CometSinglePostRoot.react,comet.post.single,via_cold_start,1703851502946,850033,,,"
                    },
                    "event_share_metadata": {"surface": "newsfeed"},
                    "actor_id": self.Data['__user'],
                    "client_mutation_id": "1"
                },
                "displayCommentsFeedbackContext": None,
                "displayCommentsContextEnableComment": None,
                "displayCommentsContextIsAdPreview": None,
                "displayCommentsContextIsAggregatedShare": None,
                "displayCommentsContextIsStorySet": None,
                "feedLocation": "NEWSFEED",
                "feedbackSource": 1,
                "focusCommentID": None,
                "gridMediaWidth": None,
                "groupID": None,
                "scale": 2,
                "privacySelectorRenderLocation": "COMET_STREAM",
                "checkPhotosToReelsUpsellEligibility": True,
                "renderLocation": "homepage_stream",
                "useDefaultActor": False,
                "inviteShortLinkKey": None,
                "isFeed": True,
                "isFundraiser": False,
                "isFunFactPost": False,
                "isGroup": False,
                "isEvent": False,
                "isTimeline": False,
                "isSocialLearning": False,
                "isPageNewsFeed": False,
                "isProfileReviews": False,
                "isWorkSharedDraft": False,
                "UFI2CommentsProvider_commentsKey": "CometModernHomeFeedQuery",
                "hashtag": None,
                "canUserManageOffers": False,
                "__relay_internal__pv__CometUFIIsRTAEnabledrelayprovider": False,
                "__relay_internal__pv__CometUFIReactionsEnableShortNamerelayprovider": False,
                "__relay_internal__pv__IsWorkUserrelayprovider": False,
                "__relay_internal__pv__IsMergQAPollsrelayprovider": False,
                "__relay_internal__pv__StoriesArmadilloReplyEnabledrelayprovider": False,
                "__relay_internal__pv__StoriesRingrelayprovider": False
            }

            self.Data.update({
                'fb_api_caller_class': 'RelayModern',
                'fb_api_req_friendly_name': 'ComposerStoryCreateMutation',
                'variables': json.dumps(variables),
                'server_timestamps': True,
                'doc_id': DOC_IDS['composer_create']
            })

            response = self.r.post(
                ENDPOINTS['graphql'],
                data=self.Data,
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ).text.replace('\\', '')

            # Check for errors (language-agnostic patterns)
            duplicate_patterns = ['duplicate', 'duplikat', 'duplicado', 'dupliziert', 'identique']
            share_error_patterns = ['unable to share', 'tidak dapat', 'no se puede compartir', 'kann nicht teilen', 'impossible de partager']

            if any(p in response.lower() for p in duplicate_patterns) and not safe_regex_search(r'"post_id":"(.*?)"', response):
                return {'status': 'failed', 'id': None, 'message': 'Duplicate share detected'}

            if any(p in response.lower() for p in share_error_patterns) and not safe_regex_search(r'"post_id":"(.*?)"', response):
                return {'status': 'failed', 'id': None, 'message': 'Unable to share - post may be deleted or private'}

            # Extract post ID
            post_id = safe_regex_search(r'"post_id":"(.*?)"', response)
            if post_id:
                logger.info(f"Shared to feed successfully: {post_id}")
                return {'status': 'success', 'id': post_id, 'message': None}

            return {'status': 'failed', 'id': None, 'message': 'Failed to share - no post ID in response'}

        except SessionError as e:
            return {'status': 'failed', 'id': None, 'message': str(e)}
        except Exception as e:
            logger.error(f"Share to feed failed: {e}")
            return {'status': 'failed', 'id': None, 'message': f'An error occurred: {e}'}


class ShareToGroup:
    """
    Share a post to a Facebook group.

    Args:
        r: Requests session object.
        cookie: Facebook authentication cookie.
        post: Post URL or ID to share.
        group: Group ID to share to (required).
        text: Additional text to add to share (optional).
        tag: List of friend IDs to tag (optional).
        privacy: Unused for groups (group privacy applies).

    Raises:
        ValidationError: If group ID is not provided.

    Example:
        >>> share = ShareToGroup(r=session, cookie=cookie, post="123456", group="789", text="Great content!")
        >>> result = share.Execute()
    """

    def __init__(
        self,
        r=None,
        cookie: str = None,
        post: str = None,
        group: str = None,
        text: str = None,
        tag: List[str] = None,
        privacy: int = None
    ):
        if not group:
            raise ValidationError("Parameter 'group' is required for ShareToGroup")

        self.r = r
        self.cookie = cookie
        self.url = convert_url(post)
        self.group = str(group)
        self.text = text or ''
        self.tag = tag or []

        # Get session data
        try:
            self.req = self.r.get(
                self.url,
                headers=get_headers_get(),
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ).text
        except Exception as e:
            logger.error(f"Failed to fetch post: {e}")
            self.req = None

        self.Data = get_session_data(self.req) if self.req else {}

    def Execute(self) -> Dict[str, Any]:
        """
        Execute the share to group.

        Returns:
            Dictionary with keys:
            - status: 'success', 'pending', or 'failed'
            - id: Share post ID if successful, None otherwise
            - message: Status message or error description
        """
        if not self.r or not self.cookie:
            return {'status': 'failed', 'id': None, 'message': 'Invalid session: cookie is required'}

        if not self.Data:
            return {'status': 'failed', 'id': None, 'message': 'Failed to extract session data'}

        try:
            session_id = extract_session_id(self.req)
            share_fbid = safe_regex_search(r'"share_fbid":"(.*?)"', self.req)

            if not session_id or not share_fbid:
                raise SessionError("Could not extract session ID or share ID")

            # Extract tracking data
            tracking = safe_regex_findall(
                r'\{"action_link":null,"badge":null,"follow_button":null\},"encrypted_tracking":"(.*?)"\},"__module_operation_CometFeedStoryTitleSection_story"',
                self.req, index=-1
            )
            if not tracking:
                tracking = safe_regex_findall(r'"encrypted_tracking":"(.*?)"', self.req, index=0)

            variables = {
                "input": {
                    "composer_entry_point": "inline_composer",
                    "composer_source_surface": "group",
                    "composer_type": "group",
                    "logging": {"composer_session_id": session_id},
                    "source": "WWW",
                    "is_tracking_encrypted": True,
                    "tracking": [tracking, None],
                    "attachments": [{
                        "link": {
                            "share_scrape_data": json.dumps({
                                "share_type": 22,
                                "share_params": [int(share_fbid)]
                            })
                        }
                    }],
                    "message": {"ranges": [], "text": self.text},
                    "with_tags_ids": self.tag,
                    "inline_activities": [],
                    "explicit_place_id": "0",
                    "text_format_preset_id": "0",
                    "navigation_data": {
                        "attribution_id_v2": "CometSinglePostRoot.react,comet.post.single,via_cold_start,1703874125062,522238,,,"
                    },
                    "event_share_metadata": {"surface": "newsfeed"},
                    "audience": {"to_id": self.group},
                    "actor_id": self.Data['__user'],
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
                "scale": 2,
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
                "UFI2CommentsProvider_commentsKey": None,
                "hashtag": None,
                "canUserManageOffers": False,
                "__relay_internal__pv__CometUFIIsRTAEnabledrelayprovider": False,
                "__relay_internal__pv__CometUFIReactionsEnableShortNamerelayprovider": False,
                "__relay_internal__pv__IsWorkUserrelayprovider": False,
                "__relay_internal__pv__IsMergQAPollsrelayprovider": False,
                "__relay_internal__pv__StoriesArmadilloReplyEnabledrelayprovider": False,
                "__relay_internal__pv__StoriesRingrelayprovider": False
            }

            self.Data.update({
                'fb_api_caller_class': 'RelayModern',
                'fb_api_req_friendly_name': 'ComposerStoryCreateMutation',
                'variables': json.dumps(variables),
                'server_timestamps': True,
                'doc_id': DOC_IDS['composer_create']
            })

            response = self.r.post(
                ENDPOINTS['graphql'],
                data=self.Data,
                cookies={'cookie': self.cookie},
                allow_redirects=True
            ).text.replace('\\', '')

            # Check for account restriction (language-agnostic patterns)
            restriction_patterns = [
                'restricted', 'dibatasi', 'restringido', 'eingeschränkt', 'restreint', 'limitado',
                '"is_restricted":true', '"can_post":false'
            ]
            share_error_patterns = ['unable to share', 'tidak dapat', 'no se puede compartir', 'kann nicht teilen', 'impossible de partager']

            if any(p in response.lower() for p in restriction_patterns) and not safe_regex_search(r'"post_id":"(.*?)"', response):
                logger.warning("Account is restricted from sharing to groups")
                return {
                    'status': 'failed',
                    'id': None,
                    'message': 'Your account is currently restricted from sharing to groups'
                }

            # Check for share error (language-agnostic)
            if any(p in response.lower() for p in share_error_patterns) and not safe_regex_search(r'"post_id":"(.*?)"', response):
                return {'status': 'failed', 'id': None, 'message': 'Unable to share - post may be deleted or private'}

            # Extract post ID
            post_id = safe_regex_search(r'"post_id":"(.*?)"', response)
            if post_id:
                # Check if pending approval
                if f'pending_posts/{post_id}' in response:
                    logger.info(f"Share pending approval: {post_id}")
                    return {'status': 'pending', 'id': post_id, 'message': 'Share is pending admin approval'}

                logger.info(f"Shared to group successfully: {post_id}")
                return {'status': 'success', 'id': post_id, 'message': None}

            return {'status': 'failed', 'id': None, 'message': 'Failed to share - no post ID in response'}

        except SessionError as e:
            return {'status': 'failed', 'id': None, 'message': str(e)}
        except Exception as e:
            logger.error(f"Share to group failed: {e}")
            return {'status': 'failed', 'id': None, 'message': f'An error occurred: {e}'}
