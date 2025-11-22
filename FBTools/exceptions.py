"""
Custom exceptions for FBTools.

This module defines a hierarchy of exceptions for better error handling
and more informative error messages throughout the library.
"""


class FBToolsError(Exception):
    """
    Base exception for all FBTools errors.

    All custom exceptions in FBTools inherit from this class,
    making it easy to catch any FBTools-related error.
    """
    pass


class AuthenticationError(FBToolsError):
    """
    Raised when authentication fails.

    This can occur when:
    - Cookie is invalid or expired
    - Email/password combination is incorrect
    - Account requires additional verification
    """
    pass


class SessionError(FBToolsError):
    """
    Raised when session data cannot be extracted.

    This typically occurs when Facebook's response format
    has changed or the session has expired.
    """
    pass


class PostError(FBToolsError):
    """
    Raised when a post operation fails.

    This can occur when:
    - Account is restricted from posting
    - Post content is flagged as spam
    - Duplicate post detected
    """
    pass


class GroupPostError(PostError):
    """
    Raised when posting to a group fails.

    Additional causes:
    - User is not a member of the group
    - Post is pending approval
    - Group has posting restrictions
    """
    pass


class ImageUploadError(FBToolsError):
    """
    Raised when image upload fails.

    This can occur when:
    - Image URL is inaccessible
    - Local file does not exist
    - File format is not supported
    - Upload request fails
    """
    pass


class CommentError(FBToolsError):
    """
    Raised when commenting on a post fails.

    This can occur when:
    - Post does not exist or is deleted
    - Comments are disabled
    - Account is restricted from commenting
    """
    pass


class ReactionError(FBToolsError):
    """
    Raised when adding a reaction fails.

    This can occur when:
    - Post does not exist
    - Invalid reaction type specified
    """
    pass


class ShareError(FBToolsError):
    """
    Raised when sharing a post fails.

    This can occur when:
    - Original post is deleted
    - Post is not shareable (private)
    - Account is restricted from sharing
    """
    pass


class PrivacyError(FBToolsError):
    """
    Raised when changing privacy settings fails.

    This can occur when:
    - Post/photo/album does not exist
    - User does not own the content
    - Invalid privacy level specified
    """
    pass


class TokenError(FBToolsError):
    """
    Raised when token extraction fails.

    This can occur when:
    - Required page is inaccessible
    - Token format has changed
    - Insufficient permissions
    """
    pass


class RateLimitError(FBToolsError):
    """
    Raised when account is temporarily restricted.

    This occurs when too many actions are performed
    in a short period of time.
    """
    pass


class ValidationError(FBToolsError):
    """
    Raised when input validation fails.

    This occurs when:
    - Required parameters are missing
    - Parameter format is invalid
    - Parameter value is out of range
    """
    pass


class ScrapingError(FBToolsError):
    """
    Raised when data extraction from Facebook fails.

    This typically indicates that Facebook's response
    format has changed and regex patterns need updating.
    """
    pass
