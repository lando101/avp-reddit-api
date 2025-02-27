from fastapi import FastAPI, Depends, HTTPException, Query, Header
from fastapi.security import OAuth2AuthorizationCodeBearer
from dotenv import load_dotenv 
import requests


# Initialize FastAPI app
app = FastAPI(
    title="Reddit Vision Pro API",
    description="An API to interact with Reddit via OAuth for a Vision Pro app.",
    version="1.0.0"
)


# Reddit API credentials (Replace with actual credentials)
CLIENT_ID = "mYYBez2n7Gnctjn1XEWIzQ"
CLIENT_SECRET = "u8iYFs_hxecmC6aAWZA5elOsvbCLJw"
REDIRECT_URI = "http://127.0.0.1:8000/auth/callback"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
API_BASE_URL = "https://oauth.reddit.com"

# ✅ Proper OAuth2 configuration for Swagger UI
oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"https://www.reddit.com/api/v1/authorize?client_id={CLIENT_ID}&response_type=code&state=randomstring&redirect_uri={REDIRECT_URI}&duration=permanent&scope=read,vote,identity",
    tokenUrl=TOKEN_URL
)

# Store tokens (Temporary - replace with a database in production)
user_tokens = {}

def get_auth_headers(token: str):
    """Helper function to return authorization headers."""
    return {
        "Authorization": f"Bearer {token}",
        "User-Agent": "VisionProRedditClient/0.1"
    }

# --- AUTHENTICATION ---

@app.post("/auth/login", summary="Authenticate with Reddit", tags=["Authentication"])
def login(auth_code: str = Query(..., description="Authorization code from Reddit")):
    """
    **Exchanges an authorization code for an access token.**
    - **auth_code**: The authorization code received from Reddit.
    - **Returns**: `access_token`, `refresh_token`, `expires_in`
    """
    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
    }
    auth = (CLIENT_ID, CLIENT_SECRET)
    
    headers = {"User-Agent": "VisionProRedditClient/0.1"}
    response = requests.post(TOKEN_URL, data=data, auth=auth, headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Failed to obtain token: {response.text}")

    token_data = response.json()

    # ✅ Store refresh_token if available
    if "refresh_token" in token_data:
        user_tokens[token_data["access_token"]] = token_data["refresh_token"]

    return token_data

@app.get("/auth/refresh", summary="Refresh Access Token", tags=["Authentication"])
def refresh_token(token: str = Query(..., description="Expired access token")):
    """
    **Refreshes an expired Reddit access token.**
    - **token**: The expired access token.
    - **Returns**: New `access_token`
    """
    if token not in user_tokens:
        raise HTTPException(status_code=400, detail="Invalid token")

    data = {
        "grant_type": "refresh_token",
        "refresh_token": user_tokens[token],
    }
    auth = (CLIENT_ID, CLIENT_SECRET)

    response = requests.post(TOKEN_URL, data=data, auth=auth)
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to refresh token")

    new_token_data = response.json()
    user_tokens[new_token_data["access_token"]] = user_tokens[token]  # Keep the same refresh token
    del user_tokens[token]
    return new_token_data

@app.get("/auth/callback", summary="OAuth Callback", tags=["Authentication"])
def auth_callback(code: str = Query(None), state: str = Query(None)):
    """
    Handles Reddit OAuth callback.
    - **Extracts `code` from Reddit response.**
    - **Displays the authorization code (for testing).**
    """
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code missing")

    return {"message": "Authorization successful!", "code": code}

# --- REDDIT DATA FETCHING ---

@app.get("/subreddit/{subreddit}", summary="Get Subreddit Posts", tags=["Reddit Data"])
def get_subreddit_posts(subreddit: str, token: str = Header(None)):
    """
    **Fetches the hot posts from a subreddit.**
    - **subreddit**: Name of the subreddit (e.g., `technology`).
    - **token**: Reddit OAuth token (provided in the `Authorization` header).
    - **Returns**: List of subreddit posts in JSON format.
    """
    if not token:
        raise HTTPException(status_code=401, detail="Missing Authorization Token")

    headers = get_auth_headers(token)
    response = requests.get(f"{API_BASE_URL}/r/{subreddit}/hot.json?limit=10", headers=headers)
    
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch subreddit posts")

    return response.json()

@app.get("/post/{post_id}", summary="Get Post Details", tags=["Reddit Data"])
def get_post(post_id: str, token: str = Header(None)):
    """
    **Fetches a specific Reddit post and its comments.**
    - **post_id**: ID of the post.
    - **token**: Reddit OAuth token (provided in `Authorization` header).
    - **Returns**: Post details including comments.
    """
    if not token:
        raise HTTPException(status_code=401, detail="Missing Authorization Token")

    headers = get_auth_headers(token)
    response = requests.get(f"{API_BASE_URL}/comments/{post_id}.json", headers=headers)
    
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch post")

    return response.json()

# --- VOTING AND COMMENTING ---

@app.post("/vote", summary="Vote on a Post", tags=["Reddit Actions"])
def vote(post_id: str, vote: int, token: str = Header(None)):
    """
    **Upvotes or downvotes a Reddit post.**
    - **post_id**: ID of the post.
    - **vote**: `1` = Upvote, `-1` = Downvote, `0` = Remove vote.
    - **token**: Reddit OAuth token.
    """
    if not token:
        raise HTTPException(status_code=401, detail="Missing Authorization Token")

    headers = get_auth_headers(token)
    data = {"id": f"t3_{post_id}", "dir": vote}

    response = requests.post(f"{API_BASE_URL}/api/vote", headers=headers, data=data)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to vote")

    return {"status": "success"}

# --- RUN SERVER LOCALLY ---
if __name__ == "__main__":
    import uvicorn
    import os
    
    port = int(os.getenv("PORT", 8000))  # Default to 8000 if PORT is not set
    uvicorn.run(app, host="0.0.0.0", port=port)
