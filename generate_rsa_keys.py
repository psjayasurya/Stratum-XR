"""
Generate RSA key pair for RS256 JWT authentication

Run this script once to generate private.pem and public.pem in the project root.
These keys will be used for signing and verifying JWTs.
"""
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import os


def generate_rsa_keys(private_key_path: str = 'private.pem', public_key_path: str = 'public.pem'):
    """
    Generate RSA 2048-bit key pair and save to files
    
    Args:
        private_key_path: Path to save private key
        public_key_path: Path to save public key
    """
    print("Generating RSA 2048-bit key pair...")
    
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    # Extract public key
    public_key = private_key.public_key()
    
    # Serialize private key (PKCS8 format)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    # Serialize public key
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    # Write to files
    with open(private_key_path, 'wb') as f:
        f.write(private_pem)
    print(f"✓ Private key saved to: {private_key_path}")
    
    with open(public_key_path, 'wb') as f:
        f.write(public_pem)
    print(f"✓ Public key saved to: {public_key_path}")
    
    print("\n⚠️ IMPORTANT:")
    print(f"  - Keep '{private_key_path}' SECURE and PRIVATE")
    print(f"  - Add both files to .gitignore if using version control")
    print(f"  - The public key can be shared safely")
    print(f"  - Store keys in environment variables for production")


if __name__ == "__main__":
    # Get paths from current directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    private_key_path = os.path.join(script_dir, 'private.pem')
    public_key_path = os.path.join(script_dir, 'public.pem')
    
    # Check if keys already exist
    if os.path.exists(private_key_path) or os.path.exists(public_key_path):
        print("⚠️ Warning: Key files already exist!")
        response = input("Overwrite existing keys? (yes/no): ").strip().lower()
        if response != 'yes':
            print("Cancelled.")
            exit(1)
    
    generate_rsa_keys(private_key_path, public_key_path)
    print("\n✓ RSA key generation complete!")
