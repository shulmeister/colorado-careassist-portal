from services.auth_service import (
    GoogleOAuthManager,
    get_current_user,
    get_current_user_optional,
    require_domain,
    security
)

# Instantiate with specific redirect URI for Portal
oauth_manager = GoogleOAuthManager(redirect_uri_env_var="PORTAL_GOOGLE_REDIRECT_URI")