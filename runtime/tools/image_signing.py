"""
Image signing check (PoC).
Checks for a signature file under ./security/image_signatures/<image_name>.sig
This is a stub for integration with real image signing/verifier.
"""
import os

def verify_image_signed(image: str) -> bool:
    # normalize image name to file-safe token
    safe_name = image.replace("/", "_").replace(":", "_")
    sig_path = os.path.join("security", "image_signatures", f"{safe_name}.sig")
    return os.path.exists(sig_path)


