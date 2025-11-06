# Colorado CareAssist Portal

Central hub/launchpad providing access to all tools and platforms used by Colorado CareAssist.

## Features

- **Google OAuth Authentication** - Secure login with Google Workspace accounts
- **Domain Restriction** - Only `coloradocareassist.com` users allowed
- **Tool Grid** - Beautiful grid of clickable tool tiles
- **Admin Interface** - Manage tools (add/edit/delete) with modal-based interface
- **Responsive Design** - Works on desktop, tablet, and mobile
- **Exact Dashboard Styling** - Matches the sales dashboard design exactly

## Setup

### Local Development

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables**
   - Create `.env` file:
   ```env
   GOOGLE_CLIENT_ID=your_google_client_id
   GOOGLE_CLIENT_SECRET=your_google_client_secret
   GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback
   APP_SECRET_KEY=your_secret_key
   ALLOWED_DOMAINS=coloradocareassist.com
   DATABASE_URL=sqlite:///./portal.db
   ```

3. **Initialize Database**
   ```bash
   python portal_setup.py
   ```

4. **Run the Application**
   ```bash
   uvicorn portal_app:app --reload --port 8000
   ```

5. **Access the Portal**
   - Open `http://localhost:8000`

## Deployment

### Heroku

The app is configured for Heroku deployment:

1. **Set Environment Variables**
   ```bash
   heroku config:set GOOGLE_CLIENT_ID=your_client_id
   heroku config:set GOOGLE_CLIENT_SECRET=your_client_secret
   heroku config:set GOOGLE_REDIRECT_URI=https://portal-coloradocareassist.herokuapp.com/auth/callback
   heroku config:set APP_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
   heroku config:set ALLOWED_DOMAINS=coloradocareassist.com
   ```

2. **Add PostgreSQL**
   ```bash
   heroku addons:create heroku-postgresql:mini
   ```

3. **Deploy**
   ```bash
   git push heroku main
   ```

4. **Initialize Database**
   ```bash
   heroku run python portal_setup.py
   ```

## Project Structure

```
├── portal_app.py          # Main FastAPI application
├── portal_auth.py          # Google OAuth authentication
├── portal_database.py     # Database setup and connection
├── portal_models.py       # Database models (PortalTool)
├── portal_setup.py        # Setup script for default tools
├── templates/
│   └── portal.html        # Portal UI template
├── Procfile               # Heroku process file
├── requirements.txt       # Python dependencies
└── runtime.txt            # Python version
```

## API Endpoints

### Authentication
- `GET /auth/login` - Redirect to Google OAuth
- `GET /auth/callback` - OAuth callback handler
- `POST /auth/logout` - Logout user
- `GET /auth/me` - Get current user info

### Tools
- `GET /api/tools` - Get all active tools
- `POST /api/tools` - Create new tool (admin only)
- `PUT /api/tools/{id}` - Update tool (admin only)
- `DELETE /api/tools/{id}` - Delete tool (admin only)

## Adding Tools

### Via Admin Interface

1. Login to the portal
2. Click "Manage Tools" button
3. Click "+ Add Tool"
4. Fill in the form:
   - **Name**: Tool name (e.g., "Sales Dashboard")
   - **URL**: Full URL to the tool
   - **Icon**: Emoji icon (e.g., "📊")
   - **Description**: Brief description (optional)
   - **Category**: Category name (optional)
   - **Display Order**: Order in grid (lower numbers first)

## Security

- **Google OAuth 2.0** - Secure authentication
- **Domain Restriction** - Only company domain allowed
- **HTTP-only Cookies** - Secure session management
- **24-hour Sessions** - Automatic logout after 24 hours
- **HTTPS Required** - Secure in production

## Design

The portal uses the **exact same styling** as the sales dashboard:
- Dark theme with `#0f172a` background
- Cards with `#1e293b` background and `#334155` borders
- Same typography, spacing, and colors
- Same navigation sidebar
- Same responsive breakpoints

