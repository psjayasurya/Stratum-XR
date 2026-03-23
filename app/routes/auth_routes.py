"""
Authentication Routes
Handles user registration, login, verification, and session management.
"""
from fastapi import APIRouter, Request, Form, Cookie, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from jose import JWTError, jwt
from typing import Optional
from datetime import datetime, timedelta
import random

from app.config import config, DEFAULT_SETTINGS, COLOR_PALETTES, TEMPLATES_FOLDER
from app.database import get_db
from app.utils.email import send_email


# Create router
router = APIRouter(tags=["Authentication"])

# Import limiter from shared module
from app.limiter import limiter

# Templates
templates = Jinja2Templates(directory=TEMPLATES_FOLDER)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============ JWT UTILITIES ============

def create_access_token(data: dict, expires_delta: timedelta = None):
    """
    Create JWT access token
    
    Args:
        data: Dictionary to encode in token
        expires_delta: Optional expiration time delta
        
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or config.JWT_ACCESS_TOKEN_EXPIRES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def verify_token(token: str):
    """
    Verify and decode JWT token
    
    Args:
        token: JWT token string
        
    Returns:
        Email from token payload or None if invalid
    """
    try:
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def get_current_user(access_token: Optional[str] = Cookie(None)):
    """
    Get current user email from access token cookie
    
    Args:
        access_token: JWT token from cookie
        
    Returns:
        User email or None if not authenticated
    """
    if not access_token:
        return None
    email = verify_token(access_token)
    return email


# ============ AUTHENTICATION ROUTES ============

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, error: Optional[str] = None):
    """Display registration page"""
    return templates.TemplateResponse("register.html", {"request": request, "error": error})


@router.post("/register")
@limiter.limit("5/minute")
async def register(request: Request, email: str = Form(...), password: str = Form(...)):
    """
    Register new user and send OTP
    
    Args:
        email: User email
        password: User password
        
    Returns:
        Redirect to verification page or error page
    """
    hashed_password = pwd_context.hash(password)
    otp = str(random.randint(100000, 999999))
    hashed_otp = pwd_context.hash(otp)
    
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "INSERT INTO users (email, password, otp) VALUES (%s,%s,%s)",
            (email, hashed_password, hashed_otp)
        )
        db.commit()
        db.close()
        
        send_email(email, "Your OTP", f"Your OTP is {otp}")
        
        return RedirectResponse(url="/verify", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/register?error={str(e)}", status_code=303)


@router.get("/verify", response_class=HTMLResponse)
async def verify_page(request: Request, error: Optional[str] = None):
    """Display OTP verification page"""
    return templates.TemplateResponse("otp.html", {"request": request, "error": error})


@router.post("/verify")
async def verify_email(email: str = Form(...), otp: str = Form(...)):
    """
    Verify user email with OTP
    
    Args:
        email: User email
        otp: One-time password
        
    Returns:
        Redirect to login page or error page
    """
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT otp FROM users WHERE email=%s", (email,))
    user = cur.fetchone()
    
    if user and user[0] and pwd_context.verify(otp, user[0]):
        cur.execute("UPDATE users SET verified=TRUE, otp=NULL WHERE email=%s", (email,))
        db.commit()
        db.close()
        return RedirectResponse(url="/login", status_code=303)
    
    db.close()
    return RedirectResponse(url="/verify?error=Invalid OTP", status_code=303)

@router.get("/", response_class=HTMLResponse)
async def website_page(request: Request, error: Optional[str] = None):
    """Display web page"""
    return templates.TemplateResponse("website.html", {"request": request, "error": error})


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None):
    """Display login page"""
    return templates.TemplateResponse("login.html", {"request": request, "error": error})


@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    """
    Authenticate user and create session
    
    Args:
        email: User email
        password: User password
        
    Returns:
        Redirect to dashboard with access token cookie or error page
    """
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT password FROM users WHERE email=%s AND verified=TRUE", (email,))
    user = cur.fetchone()
    db.close()
    
    if user and pwd_context.verify(password, user[0]):
        access_token = create_access_token({"sub": email})
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(key="access_token", value=access_token, httponly=True, samesite="lax")
        # Also set user_email cookie for collaboration features (not httponly so JS can read it)
        response.set_cookie(key="user_email", value=email, httponly=False, samesite="lax")
        return response
    
    return RedirectResponse(url="/?error=Invalid credentials", status_code=303)


@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request, error: Optional[str] = None, message: Optional[str] = None):
    """Display forgot password request page"""
    return templates.TemplateResponse("forgot_password.html", {"request": request, "error": error, "message": message})


@router.post("/forgot-password")
async def forgot_password_request(email: str = Form(...)):
    """Send reset OTP to user email"""
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM users WHERE email=%s", (email,))
    user = cur.fetchone()
    
    if not user:
        db.close()
        return RedirectResponse(url="/forgot-password?error=Email not found", status_code=303)
        
    otp = str(random.randint(100000, 999999))
    hashed_otp = pwd_context.hash(otp)
    cur.execute("UPDATE users SET otp=%s WHERE email=%s", (hashed_otp, email))
    db.commit()
    db.close()
    
    send_email(email, "Password Reset OTP", f"Your password reset OTP is {otp}")
    
    return RedirectResponse(url=f"/verify-reset-otp?email={email}", status_code=303)


@router.get("/verify-reset-otp", response_class=HTMLResponse)
async def verify_reset_otp_page(request: Request, email: str, error: Optional[str] = None):
    """Display OTP verification page for password reset"""
    return templates.TemplateResponse("verify_reset_otp.html", {"request": request, "email": email, "error": error})


@router.post("/verify-reset-otp")
async def verify_reset_otp(email: str = Form(...), otp: str = Form(...)):
    """Verify reset OTP and redirect to new password page"""
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT otp FROM users WHERE email=%s", (email,))
    user = cur.fetchone()
    db.close()
    
    if user and user[0] and pwd_context.verify(otp, user[0]):
        return RedirectResponse(url=f"/reset-password?email={email}&otp={otp}", status_code=303)
    
    return RedirectResponse(url=f"/verify-reset-otp?email={email}&error=Invalid OTP", status_code=303)


@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, email: str, otp: str, error: Optional[str] = None):
    """Display new password entry page"""
    return templates.TemplateResponse("reset_password.html", {"request": request, "email": email, "otp": otp, "error": error})


@router.post("/reset-password")
async def reset_password(email: str = Form(...), otp: str = Form(...), password: str = Form(...)):
    """Update user password after OTP verification"""
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT otp FROM users WHERE email=%s", (email,))
    user = cur.fetchone()
    
    if user and user[0] and pwd_context.verify(otp, user[0]):
        hashed_password = pwd_context.hash(password)
        # Clear OTP after successful reset and update password
        cur.execute("UPDATE users SET password=%s, otp=NULL WHERE email=%s", (hashed_password, email))
        db.commit()
        db.close()
        return RedirectResponse(url="/?message=Password updated successfully", status_code=303)
    
    db.close()
    return RedirectResponse(url="/?error=Invalid session or OTP", status_code=303)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, access_token: Optional[str] = Cookie(None)):
    """
    Display user dashboard (requires authentication)
    
    Args:
        request: FastAPI request
        access_token: JWT token from cookie
        
    Returns:
        Dashboard page or redirect to login
    """
    user = get_current_user(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": user,
        "default_settings": DEFAULT_SETTINGS,
        "color_palettes": COLOR_PALETTES
    })


@router.post("/logout")
async def logout():
    """
    Logout user by clearing access token cookie
    
    Returns:
        Redirect to login page with cleared cookies
    """
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("access_token")
    response.delete_cookie("user_email")
    return response


# ============ PROFILE ROUTES ============

@router.get("/api/profile")
async def get_profile(access_token: Optional[str] = Cookie(None)):
    """Get current user's profile data"""
    user_email = get_current_user(access_token)
    if not user_email:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "SELECT display_name, company_name, photo_url FROM user_profiles WHERE user_email=%s",
            (user_email,)
        )
        row = cur.fetchone()
        db.close()
        
        if row:
            return {
                "email": user_email,
                "display_name": row[0] or "",
                "company_name": row[1] or "",
                "photo_url": row[2] or ""
            }
        else:
            return {
                "email": user_email,
                "display_name": "",
                "company_name": "",
                "photo_url": ""
            }
    except Exception as e:
        return {"email": user_email, "display_name": "", "company_name": "", "photo_url": "", "error": str(e)}


@router.post("/api/profile")
async def save_profile(request: Request, access_token: Optional[str] = Cookie(None)):
    """Save/update user profile data (supports multipart form with photo upload)"""
    user_email = get_current_user(access_token)
    if not user_email:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    form = await request.form()
    display_name = form.get("display_name", "")
    company_name = form.get("company_name", "")
    
    # Handle photo upload
    photo_url = ""
    photo_file = form.get("photo")
    if photo_file and hasattr(photo_file, 'filename') and photo_file.filename:
        import os
        from app.config import STATIC_FOLDER
        
        uploads_dir = os.path.join(STATIC_FOLDER, "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        
        # Sanitize filename
        safe_email = user_email.replace("@", "_at_").replace(".", "_")
        ext = os.path.splitext(photo_file.filename)[1] or ".jpg"
        photo_filename = f"profile_{safe_email}{ext}"
        photo_path = os.path.join(uploads_dir, photo_filename)
        
        contents = await photo_file.read()
        with open(photo_path, "wb") as f:
            f.write(contents)
        
        photo_url = f"/static/uploads/{photo_filename}"
    
    try:
        db = get_db()
        cur = db.cursor()
        
        # Check if profile exists
        cur.execute("SELECT id, photo_url FROM user_profiles WHERE user_email=%s", (user_email,))
        existing = cur.fetchone()
        
        if existing:
            # Keep existing photo if no new one uploaded
            if not photo_url:
                photo_url = existing[1] or ""
            cur.execute(
                "UPDATE user_profiles SET display_name=%s, company_name=%s, photo_url=%s, updated_at=CURRENT_TIMESTAMP WHERE user_email=%s",
                (display_name, company_name, photo_url, user_email)
            )
        else:
            cur.execute(
                "INSERT INTO user_profiles (user_email, display_name, company_name, photo_url) VALUES (%s, %s, %s, %s)",
                (user_email, display_name, company_name, photo_url)
            )
        
        db.commit()
        db.close()
        
        return {"success": True, "display_name": display_name, "company_name": company_name, "photo_url": photo_url}
    except Exception as e:
        return {"success": False, "error": str(e)}


__all__ = ['router', 'get_current_user', 'pwd_context']
