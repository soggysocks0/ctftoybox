"""
Central registry of vulnerability templates.

Each Vulnerability is a dataclass describing a single deployable challenge
template. They're grouped by Category. For now we ship ONE simple, well-known
vulnerability per category — enough to drive batch-file / Dockerfile generation
later.

Adding more templates later is just appending to the CATEGORY's `templates`
list — the GUI picks them up automatically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Category(str, Enum):
    """Top-level CTF challenge categories shown in the deploy dropdown."""

    REVERSE_ENGINEERING = "reverse_engineering"
    BINARY_EXPLOITATION = "binary_exploitation"
    WEB_EXPLOITATION    = "web_exploitation"
    FORENSICS           = "forensics"
    CUSTOM              = "custom"

    @property
    def display_name(self) -> str:
        return {
            Category.REVERSE_ENGINEERING: "Reverse Engineering",
            Category.BINARY_EXPLOITATION: "Binary Exploitation",
            Category.WEB_EXPLOITATION:    "Web Exploitation",
            Category.FORENSICS:           "Forensics",
            Category.CUSTOM:              "Custom",
        }[self]

    @property
    def short_code(self) -> str:
        """Short label used in slugs/filenames (e.g. 're', 'pwn')."""
        return {
            Category.REVERSE_ENGINEERING: "re",
            Category.BINARY_EXPLOITATION: "pwn",
            Category.WEB_EXPLOITATION:    "web",
            Category.FORENSICS:           "for",
            Category.CUSTOM:              "custom",
        }[self]

    @property
    def description(self) -> str:
        return {
            Category.REVERSE_ENGINEERING:
                "Analyze compiled binaries to recover hidden flags or logic.",
            Category.BINARY_EXPLOITATION:
                "Exploit memory-corruption bugs to hijack program execution.",
            Category.WEB_EXPLOITATION:
                "Attack web applications via injection, auth, or logic flaws.",
            Category.FORENSICS:
                "Recover hidden data from files, images, packets, or memory.",
            Category.CUSTOM:
                "Deploy your own image/Dockerfile with custom vulnerabilities.",
        }[self]


class Difficulty(str, Enum):
    EASY   = "easy"
    MEDIUM = "medium"
    HARD   = "hard"


# ---------------------------------------------------------------------------
# Vulnerability dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Vulnerability:
    """
    A single template vulnerability that can be used to spin up a challenge.
    """

    id:          str
    category:    Category
    name:        str
    short_desc:  str

    difficulty:    Difficulty
    learning_goal: str
    hint:          str

    image_base:     str
    exposed_ports:  tuple[int, ...] = ()
    build_args:     dict[str, str] = field(default_factory=dict)

    flag_template: str = "bluebox{{change_me}}"

    tags: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Templates — one easy challenge per category
# ---------------------------------------------------------------------------

_RE_STRCMP_PASSWORD = Vulnerability(
    id="re-strcmp-password",
    category=Category.REVERSE_ENGINEERING,
    name="Hardcoded Password Checker",
    short_desc="Classic strcmp() crackme — find the password baked into the binary.",
    difficulty=Difficulty.EASY,
    learning_goal=(
        "Use `strings`, `ltrace`, or a decompiler (Ghidra/IDA) to spot a "
        "hardcoded password compared against user input via strcmp()."
    ),
    hint="Try running `strings` on the binary first.",
    image_base="gcc:12-bookworm",
    exposed_ports=(),
    build_args={
        "lang": "c",
        "compile_flags": "-O0 -no-pie -fno-stack-protector",
    },
    flag_template="bluebox{{re_{challenge}_{rand}}}",
    tags=("crackme", "strings", "strcmp", "beginner"),
)

_PWN_RET2WIN = Vulnerability(
    id="pwn-ret2win-basic",
    category=Category.BINARY_EXPLOITATION,
    name="Stack Buffer Overflow → ret2win",
    short_desc="Overflow a stack buffer to redirect execution into a hidden win() function.",
    difficulty=Difficulty.EASY,
    learning_goal=(
        "Identify an unchecked gets()/strcpy() call, calculate the offset to "
        "the saved return address, and overwrite it with the address of an "
        "existing win() function that prints the flag."
    ),
    hint="There's a function in the binary that's never called from main…",
    image_base="ubuntu:22.04",
    exposed_ports=(31337,),
    build_args={
        "lang": "c",
        "compile_flags": "-no-pie -fno-stack-protector -z execstack",
        "service_wrapper": "socat",
    },
    flag_template="bluebox{{pwn_{challenge}_{rand}}}",
    tags=("pwn", "buffer-overflow", "ret2win", "stack", "beginner"),
)

_WEB_SQLI_LOGIN = Vulnerability(
    id="web-sqli-login-bypass",
    category=Category.WEB_EXPLOITATION,
    name="SQL Injection — Auth Bypass",
    short_desc="Bypass a naive login form using classic SQL injection.",
    difficulty=Difficulty.EASY,
    learning_goal=(
        "Recognize string-concatenated SQL queries in a login handler and "
        "craft a payload like `' OR '1'='1' -- ` to bypass authentication "
        "without knowing the password."
    ),
    hint="The login form trusts your input a little too much. What if your username *was* SQL?",
    image_base="python:3.12-slim",
    exposed_ports=(8080,),
    build_args={
        "framework": "flask",
        "db": "sqlite",
    },
    flag_template="bluebox{{web_{challenge}_{rand}}}",
    tags=("web", "sqli", "auth-bypass", "beginner"),
)

_FOR_IMAGE_METADATA = Vulnerability(
    id="for-image-metadata",
    category=Category.FORENSICS,
    name="Hidden Flag in Image Metadata",
    short_desc="Recover a flag hidden in EXIF metadata or appended after the image data.",
    difficulty=Difficulty.EASY,
    learning_goal=(
        "Use `strings`, `exiftool`, or a hex editor to find data hidden in "
        "places that a casual viewer would miss — EXIF tags, comment fields, "
        "or bytes appended after the image's logical end-of-file."
    ),
    hint="A picture is worth a thousand words. Sometimes literally — check the metadata.",
    image_base="alpine:3.19",
    exposed_ports=(),
    build_args={
        "artifact_format": "jpeg",
        "hide_method": "exif_comment",
    },
    flag_template="bluebox{{for_{challenge}_{rand}}}",
    tags=("forensics", "stego", "exif", "metadata", "beginner"),
)

_CUSTOM_PLACEHOLDER = Vulnerability(
    id="custom-user-defined",
    category=Category.CUSTOM,
    name="User-Defined Challenge",
    short_desc="Bring your own Dockerfile or image with custom vulnerabilities.",
    difficulty=Difficulty.MEDIUM,
    learning_goal="Whatever you want to teach.",
    hint="(provided by you)",
    image_base="",
    exposed_ports=(),
    build_args={},
    flag_template="bluebox{{custom_{challenge}_{rand}}}",
    tags=("custom", "user-defined"),
)


# ---------------------------------------------------------------------------
# Registry — keyed by Category, ordered as we want them shown in the UI
# ---------------------------------------------------------------------------

REGISTRY: dict[Category, list[Vulnerability]] = {
    Category.REVERSE_ENGINEERING: [_RE_STRCMP_PASSWORD],
    Category.BINARY_EXPLOITATION: [_PWN_RET2WIN],
    Category.WEB_EXPLOITATION:    [_WEB_SQLI_LOGIN],
    Category.FORENSICS:           [_FOR_IMAGE_METADATA],
    Category.CUSTOM:              [_CUSTOM_PLACEHOLDER],
}


# ---------------------------------------------------------------------------
# Helper accessors
# ---------------------------------------------------------------------------

def get_category(slug: str) -> Category | None:
    """Look up a Category by its string value (e.g. 'web_exploitation')."""
    try:
        return Category(slug)
    except ValueError:
        return None


def get_vulnerabilities(category: Category) -> list[Vulnerability]:
    """Return all template vulnerabilities for a given category."""
    return list(REGISTRY.get(category, []))


def get_vulnerability(vuln_id: str) -> Vulnerability | None:
    """Look up a single vulnerability by its slug id, across all categories."""
    for vulns in REGISTRY.values():
        for v in vulns:
            if v.id == vuln_id:
                return v
    return None