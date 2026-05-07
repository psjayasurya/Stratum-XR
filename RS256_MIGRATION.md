# RS256 Migration Guide

## Overview
The authentication system has been migrated from **HS256** (symmetric) to **RS256** (asymmetric) using RSA 2048-bit encryption.

## What Changed

### 1. **Algorithm**
- **Before**: HS256 (HMAC with SHA-256)
- **After**: RS256 (RSA with SHA-256)

### 2. **Key Management**
- **Before**: Single `JWT_SECRET_KEY` (symmetric key)
- **After**: Two RSA keys:
  - `JWT_PRIVATE_KEY` - Used for signing tokens (MUST be kept secret)
  - `JWT_PUBLIC_KEY` - Used for verifying tokens (can be shared)

### 3. **Benefits of RS256**
✅ Asymmetric encryption (more secure for distributed systems)  
✅ Public key can be shared without compromising security  
✅ Better for microservices architectures  
✅ Industry standard for OAuth2 and OpenID Connect  

## Setup Instructions

### Development Environment

1. **Keys are already generated** (`private.pem` and `public.pem` in project root)

2. **Verify the keys exist**:
   ```bash
   ls -la private.pem public.pem
   ```

3. **Start the application** - it will automatically load the keys from files:
   ```bash
   python main.py
   ```

### Production Environment

**Important**: Never commit `private.pem` to version control!

1. **Set environment variables**:
   ```bash
   # Get the contents of private.pem and public.pem
   export JWT_PRIVATE_KEY="$(cat private.pem)"
   export JWT_PUBLIC_KEY="$(cat public.pem)"
   ```

2. **Or in `.env` file**:
   ```
   JWT_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----
   MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC...
   -----END PRIVATE KEY-----
   
   JWT_PUBLIC_KEY=-----BEGIN PUBLIC KEY-----
   MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
   -----END PUBLIC KEY-----
   ```

3. **Alternative: Docker/Kubernetes Secrets**:
   ```bash
   docker run -e JWT_PRIVATE_KEY="$(cat private.pem)" my-app
   ```

## File Changes

### Modified Files:

1. **`app/config.py`**
   - Added `load_rsa_keys()` function to load keys from environment or files
   - Changed `JWT_ALGORITHM = "RS256"`
   - Added `JWT_PRIVATE_KEY` and `JWT_PUBLIC_KEY`
   - Kept `JWT_SECRET_KEY` for backwards compatibility (deprecated)

2. **`app/routes/auth_routes.py`**
   - Updated `create_access_token()` to use `JWT_PRIVATE_KEY` for signing
   - Updated `verify_token()` to use `JWT_PUBLIC_KEY` for verification
   - Both now use RS256 algorithm

### New Files:

1. **`generate_rsa_keys.py`**
   - Script to generate RSA key pairs
   - Creates `private.pem` and `public.pem`

2. **`.env.example`**
   - Example environment configuration for RS256

## Backward Compatibility

- Existing HS256 tokens will **NOT** work with the new RS256 system
- All users need to log in again after the migration
- The old `JWT_SECRET_KEY` is kept in config but not used

## Security Best Practices

### ✅ DO:
- Keep `private.pem` file secure (file permissions: `600`)
- Store in environment variables for production
- Use different keys per environment
- Rotate keys periodically
- Back up keys securely

### ❌ DON'T:
- Commit `private.pem` to version control (already in `.gitignore`)
- Share the private key
- Use weak passphrases
- Store keys in code/comments
- Use the same keys across multiple applications

## Troubleshooting

### Issue: "RSA keys not found"
**Solution**: Run `python generate_rsa_keys.py` in the project root

### Issue: "Invalid token" after migration
**Solution**: Users need to log in again (HS256 tokens are incompatible)

### Issue: Decoding errors
**Solution**: Ensure public key is properly formatted (must include BEGIN/END markers)

### Issue: Token verification fails
**Solution**: Verify that the same keys are used for signing and verification

## Reverting to HS256 (Not Recommended)

If you need to revert:

1. Edit `app/config.py`: Change `JWT_ALGORITHM = "HS256"`
2. Update `create_access_token()` to use `JWT_SECRET_KEY`
3. Update `verify_token()` to use `JWT_SECRET_KEY`
4. All users must log in again

**Note**: RS256 is recommended for modern applications.

## Testing the Migration

```python
# Test script to verify RS256 is working
from app.config import config
from app.routes.auth_routes import create_access_token, verify_token

# Create a test token
test_token = create_access_token({"sub": "test@example.com"})
print(f"Created token: {test_token[:50]}...")

# Verify the token
email = verify_token(test_token)
print(f"Verified email: {email}")
assert email == "test@example.com", "Token verification failed!"
print("✓ RS256 migration successful!")
```

## References

- [RSA Algorithm](https://tools.ietf.org/html/rfc3447)
- [JWT (JSON Web Tokens)](https://tools.ietf.org/html/rfc7519)
- [RS256 vs HS256](https://auth0.com/blog/json-web-token-jwt/)
- [python-jose Documentation](https://python-jose.readthedocs.io/)
