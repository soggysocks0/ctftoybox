"""Customize this challenge:
 - Change which marker the flag hides in (COM, APP1/EXIF, after EOI)
 - Embed in a different file format (PNG tEXt chunk, ZIP comment, etc.)
 - Wrap the artifact in another container (zip, tar, pdf)
The flag comes from the CHALL_FLAG env var, set by CTF Manager.
"""
import os, struct

FLAG = os.environ.get("CHALL_FLAG", "bluebox{missing}").encode()

JPEG_BASE = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000"
    "ffdb0043000806060706050807070709090808"
    "0a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e27"
    "20222c231c1c2837292c30313434341f27393d38323c2e333432"
    "ffc0000b08000100010101110000"
    "ffc4001f0000010501010101010100000000000000000102030405060708090a0b"
    "ffda0008010100003f00"
    "37"
    "ffd9"
)


def jpeg_with_comment(base: bytes, comment: bytes) -> bytes:
    com = b"\xff\xfe" + struct.pack(">H", 2 + len(comment)) + comment
    return base[:2] + com + base[2:]


def main():
    out = jpeg_with_comment(JPEG_BASE, b"Hidden in plain sight: " + FLAG)
    out += b"\n--appendix--\n" + FLAG + b"\n"
    with open("/out/challenge.jpg", "wb") as f:
        f.write(out)
    print(f"Wrote /out/challenge.jpg ({len(out)} bytes)")


if __name__ == "__main__":
    main()
