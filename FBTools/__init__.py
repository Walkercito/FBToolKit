"""
FBTools - Facebook Automation Toolkit.

A Python library for automating Facebook interactions using
reverse-engineered GraphQL APIs.

Example (sync):
    >>> from FBTools import Start
    >>> fb = Start(cookie="your_facebook_cookie")
    >>> if fb.IsValid:
    ...     result = fb.PostToFeed(text="Hello World!")
    ...     print(result)

Example (async):
    >>> import asyncio
    >>> from FBTools import AsyncStart
    >>>
    >>> async def main():
    ...     async with AsyncStart(cookie="your_cookie") as fb:
    ...         if fb.IsValid:
    ...             result = await fb.PostToFeed(text="Hello async!")
    ...             print(result)
    >>>
    >>> asyncio.run(main())

Features:
    - Post to feeds and groups
    - Comment on posts
    - React to posts (Like, Love, Haha, etc.)
    - Share posts to feeds and groups
    - Get profile, page, and group information
    - Manage 2FA authentication
    - Privacy controls
    - Full async/await support

Note:
    This library uses Facebook's internal GraphQL API and may break
    if Facebook changes their API structure.
"""

__version__ = "0.1.1"
__author__ = "Dapunta Khurayra X"
__maintainer__ = "Walkercito"

import logging
import requests
from typing import Optional, List, Dict, Any

from .Login import LoginCookie, LoginEmail, LoginPhone
from .GetToken import TokenEAAG, TokenEAAB, TokenEAAD, TokenEAAC, TokenEAAF, TokenEABB
from .GetInfo import GetInfoProfile, GetInfoPage, GetInfoGroup
from .Automation1 import PostToFeed, PostToGroup, CommentToPost, ReactToPost, ShareToFeed, ShareToGroup
from .Privacy import PostPrivacy, PhotoPrivacy, AlbumPrivacy
from .Friend import AddFriend, UnFriend, Follow, UnFollow, Block, UnBlock
from .Setting import A2F, UnA2F, GetAPP, ProfileGuard
from .constants import USER_AGENT_WINDOWS, USER_AGENT_ANDROID
from .exceptions import (
    FBToolsError,
    AuthenticationError,
    PostError,
    GroupPostError,
    ImageUploadError,
    CommentError,
    ReactionError,
    ShareError,
    ValidationError,
    SessionError,
)
from .async_client import (
    AsyncStart,
    AsyncPostToFeed,
    AsyncPostToGroup,
    AsyncReactToPost,
)

# Configure default logging
logging.getLogger('FBTools').addHandler(logging.NullHandler())

logger = logging.getLogger('FBTools')


class Start:
    """
    Main entry point for the FBTools library.

    Handles authentication and provides access to all Facebook
    automation features.

    Args:
        cookie: Facebook authentication cookie string.
        email: Facebook email (requires password).
        phone: Facebook phone number (requires password).
        password: Account password (required for email/phone login).
        wait_for_approval: Wait for security approval if required (default: True).
        approval_timeout: Seconds to wait for approval (default: 60).

    Attributes:
        IsValid: True if authentication was successful.
        cookie: The validated cookie string.

    Example:
        >>> # Login with cookie
        >>> fb = Start(cookie="sb=xxx; c_user=yyy; xs=zzz; ...")
        >>> if fb.IsValid:
        ...     print("Logged in successfully!")

        >>> # Login with email/password (waits for approval if needed)
        >>> fb = Start(email="user@example.com", password="password123")

        >>> # Login with phone (custom approval timeout)
        >>> fb = Start(phone="+1234567890", password="pass", approval_timeout=120)
    """

    def __init__(
        self,
        cookie: str = None,
        email: str = None,
        phone: str = None,
        password: str = None,
        wait_for_approval: bool = True,
        approval_timeout: int = 60
    ):
        self.user_agent_windows = USER_AGENT_WINDOWS
        self.user_agent_android = USER_AGENT_ANDROID
        self.r = requests.Session()
        self.cookie = None
        self.IsValid = False

        if cookie:
            validated_cookie = LoginCookie(self.r, self.user_agent_windows, cookie)
            if validated_cookie:
                self.cookie = validated_cookie
                self.IsValid = True
            else:
                logger.warning("Cookie validation failed")

        elif email and password:
            validated_cookie = LoginEmail(
                self.r, self.user_agent_android, email, password,
                wait_for_approval=wait_for_approval,
                approval_timeout=approval_timeout
            )
            if validated_cookie:
                self.cookie = validated_cookie
                self.IsValid = True
            else:
                logger.warning("Email login failed")

        elif phone and password:
            validated_cookie = LoginPhone(
                self.r, self.user_agent_android, phone, password,
                wait_for_approval=wait_for_approval,
                approval_timeout=approval_timeout
            )
            if validated_cookie:
                self.cookie = validated_cookie
                self.IsValid = True
            else:
                logger.warning("Phone login failed")

        else:
            logger.warning("No valid authentication method provided")

    # --- Token Methods ---

    def TokenEAAG(self) -> str:
        """Extract EAAG access token."""
        return TokenEAAG(self.r, self.cookie)

    def TokenEAAB(self) -> str:
        """Extract EAAB access token."""
        return TokenEAAB(self.r, self.cookie)

    def TokenEAAD(self) -> str:
        """Extract EAAD access token."""
        return TokenEAAD(self.r, self.cookie)

    def TokenEAAC(self) -> str:
        """Extract EAAC access token."""
        return TokenEAAC(self.r, self.cookie)

    def TokenEAAF(self) -> str:
        """Extract EAAF access token."""
        return TokenEAAF(self.r, self.cookie)

    def TokenEABB(self) -> str:
        """Extract EABB access token."""
        return TokenEABB(self.r, self.cookie)

    # --- Information Methods ---

    def GetInfoProfile(self, profile: str) -> Dict[str, Any]:
        """
        Get information about a Facebook profile.

        Args:
            profile: Profile URL, username, or ID.

        Returns:
            GetInfoProfile object with profile attributes.
        """
        if not profile:
            return {'status': 'failed', 'message': 'GetInfoProfile() must have "profile" parameter'}
        return GetInfoProfile(r=self.r, cookie=self.cookie, profile=profile)

    def GetInfoPage(self, page: str) -> Dict[str, Any]:
        """
        Get information about a Facebook page.

        Args:
            page: Page URL, username, or ID.

        Returns:
            GetInfoPage object with page attributes.
        """
        if not page:
            return {'status': 'failed', 'message': 'GetInfoPage() must have "page" parameter'}
        return GetInfoPage(r=self.r, cookie=self.cookie, page=page)

    def GetInfoGroup(self, group: str) -> Dict[str, Any]:
        """
        Get information about a Facebook group.

        Args:
            group: Group URL, ID, or address.

        Returns:
            GetInfoGroup object with group attributes.
        """
        if not group:
            return {'status': 'failed', 'message': 'GetInfoGroup() must have "group" parameter'}
        return GetInfoGroup(r=self.r, cookie=self.cookie, group=group)

    # --- Post Methods ---

    def PostToFeed(
        self,
        group: str = None,
        text: str = None,
        url: List[str] = None,
        tag: List[str] = None,
        privacy: int = None
    ) -> Dict[str, Any]:
        """
        Create a post on your personal feed/timeline.

        Args:
            group: Unused (kept for API compatibility).
            text: Post text content.
            url: List of image URLs or file paths to attach.
            tag: List of friend IDs to tag.
            privacy: Privacy level (1=EVERYONE, 2=FRIENDS, 3=SELF).

        Returns:
            Dict with 'status', 'id', 'message', and 'upload_errors' keys.
        """
        ptf = PostToFeed(
            r=self.r, cookie=self.cookie, group=group,
            text=text, url=url, tag=tag, privacy=privacy
        )
        return ptf.Execute()

    def PostToGroup(
        self,
        group: str = None,
        text: str = None,
        url: List[str] = None,
        tag: List[str] = None,
        privacy: int = None
    ) -> Dict[str, Any]:
        """
        Create a post in a Facebook group.

        Args:
            group: Group ID (required).
            text: Post text content.
            url: List of image URLs or file paths to attach.
            tag: List of friend IDs to tag.
            privacy: Unused for groups.

        Returns:
            Dict with 'status', 'id', 'message', and 'upload_errors' keys.

        Raises:
            ValidationError: If group ID is not provided.
        """
        ptg = PostToGroup(
            r=self.r, cookie=self.cookie, group=group,
            text=text, url=url, tag=tag, privacy=privacy
        )
        return ptg.Execute()

    # --- Comment Methods ---

    def CommentToPost(
        self,
        post: str = None,
        text: str = None,
        photo: str = None,
        tag: List[str] = None
    ) -> Dict[str, Any]:
        """
        Add a comment to a post.

        Args:
            post: Post URL or ID.
            text: Comment text.
            photo: Photo URL or file path to attach.
            tag: List of user IDs to tag.

        Returns:
            Dict with 'status', 'id', and 'message' keys.
        """
        ctp = CommentToPost(
            r=self.r, cookie=self.cookie,
            post=post, text=text, photo=photo, tag=tag
        )
        return ctp.Execute()

    # --- React Methods ---

    def ReactToPost(self, post: str = None, react: int = None) -> Dict[str, Any]:
        """
        Add a reaction to a post.

        Args:
            post: Post URL or ID.
            react: Reaction type (1=Like, 2=Love, 3=Haha, 4=Wow, 5=Care, 6=Sad, 7=Angry).

        Returns:
            Dict with 'status', 'react_type', and 'message' keys.
        """
        rtp = ReactToPost(r=self.r, cookie=self.cookie, post=post, react=react)
        return rtp.Execute()

    # --- Share Methods ---

    def ShareToFeed(
        self,
        post: str = None,
        group: str = None,
        text: str = None,
        tag: List[str] = None,
        privacy: int = None
    ) -> Dict[str, Any]:
        """
        Share a post to your feed.

        Args:
            post: Post URL or ID to share.
            group: Unused (kept for API compatibility).
            text: Additional text to add.
            tag: List of friend IDs to tag.
            privacy: Privacy level (1=EVERYONE, 2=FRIENDS, 3=SELF).

        Returns:
            Dict with 'status', 'id', and 'message' keys.
        """
        stf = ShareToFeed(
            r=self.r, cookie=self.cookie,
            post=post, group=group, text=text, tag=tag, privacy=privacy
        )
        return stf.Execute()

    def ShareToGroup(
        self,
        post: str = None,
        group: str = None,
        text: str = None,
        tag: List[str] = None,
        privacy: int = None
    ) -> Dict[str, Any]:
        """
        Share a post to a group.

        Args:
            post: Post URL or ID to share.
            group: Group ID to share to (required).
            text: Additional text to add.
            tag: List of friend IDs to tag.
            privacy: Unused for groups.

        Returns:
            Dict with 'status', 'id', and 'message' keys.

        Raises:
            ValidationError: If group ID is not provided.
        """
        stg = ShareToGroup(
            r=self.r, cookie=self.cookie,
            post=post, group=group, text=text, tag=tag, privacy=privacy
        )
        return stg.Execute()

    # --- Privacy Methods ---

    def PostPrivacy(self, post: str = None, privacy: int = 3) -> Dict[str, Any]:
        """
        Change the privacy of a post.

        Args:
            post: Post URL or ID.
            privacy: Privacy level (1=EVERYONE, 2=FRIENDS, 3=SELF).

        Returns:
            Dict with 'status' and 'message' keys.
        """
        pp = PostPrivacy(r=self.r, cookie=self.cookie, post=post, privacy=privacy)
        return pp.Execute()

    def PhotoPrivacy(self, photo: str = None, privacy: int = 3) -> Dict[str, Any]:
        """
        Change the privacy of a photo.

        Args:
            photo: Photo URL or ID.
            privacy: Privacy level (1=EVERYONE, 2=FRIENDS, 3=SELF).

        Returns:
            Dict with 'status' and 'message' keys.
        """
        pp = PhotoPrivacy(r=self.r, cookie=self.cookie, photo=photo, privacy=privacy)
        return pp.Execute()

    def AlbumPrivacy(self, album: str = None, privacy: int = 3) -> Dict[str, Any]:
        """
        Change the privacy of an album.

        Args:
            album: Album URL or ID.
            privacy: Privacy level (1=EVERYONE, 2=FRIENDS, 3=SELF).

        Returns:
            Dict with 'status' and 'message' keys.
        """
        ap = AlbumPrivacy(r=self.r, cookie=self.cookie, album=album, privacy=privacy)
        return ap.Execute()

    # --- Friend Methods ---

    def AddFriend(self, id: str) -> Dict[str, Any]:
        """Send a friend request."""
        return AddFriend(r=self.r, cookie=self.cookie, id=id)

    def UnFriend(self, id: str) -> Dict[str, Any]:
        """Remove a friend."""
        return UnFriend(r=self.r, cookie=self.cookie, id=id)

    def Follow(self, id: str) -> Dict[str, Any]:
        """Follow a user."""
        return Follow(r=self.r, cookie=self.cookie, id=id)

    def UnFollow(self, id: str) -> Dict[str, Any]:
        """Unfollow a user."""
        return UnFollow(r=self.r, cookie=self.cookie, id=id)

    def Block(self, id: str) -> Dict[str, Any]:
        """Block a user."""
        return Block(r=self.r, cookie=self.cookie, id=id)

    def UnBlock(self, id: str) -> Dict[str, Any]:
        """Unblock a user."""
        return UnBlock(r=self.r, cookie=self.cookie, id=id)

    # --- Settings Methods ---

    def Authentication(
        self,
        active: bool = None,
        password: str = None
    ) -> Dict[str, Any]:
        """
        Enable or disable two-factor authentication.

        Args:
            active: True to enable 2FA, False to disable.
            password: Account password (required).

        Returns:
            Dict with 'status', 'key', 'recovery', and 'message' keys.
        """
        if active is None or password is None:
            return {
                'status': 'failed',
                'key': None,
                'message': 'Wrong Parameter, Give "active" and "password" Parameter'
            }
        if active:
            exe = A2F(r=self.r, cookie=self.cookie, stat=active, password=password)
            return exe.Auten()
        else:
            exe = UnA2F(r=self.r, cookie=self.cookie, stat=active, password=password)
            return exe.UnAuten()

    def CheckApp(self) -> Dict[str, Any]:
        """
        Get list of connected apps.

        Returns:
            Dict with 'active' and 'expired' lists of apps.
        """
        gap = GetAPP(r=self.r, cookie=self.cookie)
        return gap.Execute()

    def ProfileGuard(self, stat: bool) -> Dict[str, Any]:
        """
        Enable or disable profile guard.

        Args:
            stat: True to enable, False to disable.

        Returns:
            Dict with 'status' and 'message' keys.
        """
        pg = ProfileGuard(r=self.r, cookie=self.cookie, stat=stat)
        return pg.Execute()
