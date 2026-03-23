
import os
import uvicorn
from gen_cert import generate_self_signed_cert




if __name__ == "__main__":
    # Generate certs if they don't exist
    if not os.path.exists("cert.pem") or not os.path.exists("key.pem"):
        generate_self_signed_cert()
    
    print("\n" + "="*60)
    print("STARTING SECURE SERVER FOR VR DEVELOPMENT")
    print("="*60)
    print(f"Local Access: https://127.0.0.1:5007")
    
    # Get local IP
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print(f"Network Access: https://{local_ip}:5007")
    print("="*60 + "\n")
    print("NOTE: You will see a security warning in your browser.")
    print("      This is normal for self-signed certificates.")
    print("      Click 'Advanced' -> 'Proceed to...' (Chrome) or 'Accept Risk' (Firefox)")
    print("\n")

    # Run uvicorn with SSL
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=5007,
        ssl_keyfile="key.pem",
        ssl_certfile="cert.pem",
        reload=True
    )
