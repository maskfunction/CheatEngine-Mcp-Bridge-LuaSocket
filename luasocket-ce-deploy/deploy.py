#!/usr/bin/env python3
"""
============================================================================
  LuaSocket CE Deployment Tool  v1.0
  Automated detection, verification, and installation of LuaSocket
  for Cheat Engine (all versions).
============================================================================

Usage:
  python deploy.py                          # Interactive mode
  python deploy.py --ce "C:\\Cheat Engine"   # Specify CE root
  python deploy.py --ce "C:\\Cheat Engine" --force  # Skip confirmations
  python deploy.py --check-only             # Only check, don't install
  python deploy.py --dry-run                # Preview without writing

Features:
  - Auto-detects CE installation from common paths
  - Identifies CE's Lua version (5.1/5.3/5.4) by scanning DLLs
  - Matches pre-built luasocket binaries to the detected Lua version
  - Falls back to compiling from source if no pre-built match
  - Deploys .lua modules + .dll files to correct CE paths
  - Verifies deployment integrity
  - Creates backups of existing luasocket installations
  - Works with both installer and portable CE editions

Requirements:
  - Python 3.6+
  - (Optional) Visual Studio Build Tools for compilation fallback
"""

import os, sys, struct, shutil, subprocess, argparse, re, json, platform
from pathlib import Path
from datetime import datetime

# ─── Configuration ───────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
PREBUILT_DIR = SCRIPT_DIR / "prebuilt"
LUA_MODULES_DIR = SCRIPT_DIR / "lua"
SRC_DIR = SCRIPT_DIR / "src"

# CE Lua version → DLL name mapping (64-bit)
# Pattern: "luaxx-64.dll" where xx = version without dots
LUA_VERSION_MAP = {
    "51": {"dll": "lua51-64.dll", "lib": "lua51-64.lib", "ver": "5.1", "ver_num": 501},
    "53": {"dll": "lua53-64.dll", "lib": "lua53-64.lib", "ver": "5.3", "ver_num": 503},
    "54": {"dll": "lua54-64.dll", "lib": "lua54-64.lib", "ver": "5.4", "ver_num": 504},
}

# Common CE installation paths to scan
COMMON_CE_PATHS = [
    r"C:\Program Files\Cheat Engine 7.5",
    r"C:\Program Files\Cheat Engine 7.4",
    r"C:\Program Files\Cheat Engine 7.3",
    r"C:\Program Files\Cheat Engine 7.2",
    r"C:\Program Files\Cheat Engine 7.1",
    r"C:\Program Files\Cheat Engine 7.0",
    r"C:\Program Files (x86)\Cheat Engine 7.5",
    r"C:\Program Files (x86)\Cheat Engine 7.4",
    r"C:\Program Files (x86)\Cheat Engine 7.3",
    r"C:\Program Files (x86)\Cheat Engine",
    r"C:\Program Files\Cheat Engine",
    r"D:\Cheat Engine",
    r"E:\Cheat Engine",
]

# Files that will be deployed
LUA_FILES = [
    "socket.lua", "mime.lua", "ltn12.lua",
    "socket/http.lua", "socket/ftp.lua", "socket/smtp.lua",
    "socket/tp.lua", "socket/url.lua", "socket/headers.lua",
]

DLL_FILES = [
    "socket/core.dll",
    "mime/core.dll",
]


# ─── Utility Functions ───────────────────────────────────────────────────────

def color(text, code):
    """Wrap text in ANSI color codes (Windows 10+ supports them)."""
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass
    return f"\033[{code}m{text}\033[0m"


def green(s):  return color(s, "32")
def yellow(s): return color(s, "33")
def red(s):    return color(s, "31")
def bold(s):   return color(s, "1")
def cyan(s):   return color(s, "36")


def print_header(title):
    print()
    print(bold("=" * 72))
    print(bold(f"  {title}"))
    print(bold("=" * 72))


def print_ok(msg):   print(f"  {green('[OK]')} {msg}")
def print_warn(msg): print(f"  {yellow('[!]')} {msg}")
def print_err(msg):  print(f"  {red('[X]')} {msg}")
def print_info(msg): print(f"  {cyan('[*]')} {msg}")


def is_admin():
    """Check if running with administrator privileges."""
    try:
        return os.getuid() == 0
    except AttributeError:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0


def get_pe_machine_type(dll_path):
    """Read PE header to determine 32-bit vs 64-bit architecture."""
    try:
        with open(dll_path, "rb") as f:
            dos_header = f.read(64)
            if dos_header[:2] != b"MZ":
                return None
            pe_offset = struct.unpack("<I", dos_header[60:64])[0]
            f.seek(pe_offset)
            pe_sig = f.read(4)
            if pe_sig != b"PE\x00\x00":
                return None
            coff_header = f.read(20)
            machine = struct.unpack("<H", coff_header[0:2])[0]
            # 0x8664 = x64, 0x14C = x86
            return "x64" if machine == 0x8664 else "x86" if machine == 0x14C else f"0x{machine:04X}"
    except Exception:
        return None


def get_pe_dependencies(dll_path):
    """Extract DLL dependencies from PE import table using a simple parser."""
    deps = []
    try:
        with open(dll_path, "rb") as f:
            dos_header = f.read(64)
            pe_offset = struct.unpack("<I", dos_header[60:64])[0]
            f.seek(pe_offset + 4)
            coff = f.read(20)
            # Optional header
            opt_header_size = struct.unpack("<H", coff[16:18])[0]
            opt_header = f.read(opt_header_size)
            # Data directories: offset 96 (for PE32+) or 80 (for PE32) into opt_header
            # Magic: 0x10B = PE32, 0x20B = PE32+
            magic = struct.unpack("<H", opt_header[0:2])[0]
            if magic == 0x20B:
                import_dir_rva = struct.unpack("<I", opt_header[96:100])[0]
                import_dir_size = struct.unpack("<I", opt_header[104:108])[0]
            else:
                import_dir_rva = struct.unpack("<I", opt_header[80:84])[0]
                import_dir_size = struct.unpack("<I", opt_header[88:92])[0]

            if import_dir_rva == 0:
                return deps

            # Read section headers to translate RVA → file offset
            num_sections = struct.unpack("<H", coff[2:4])[0]
            section_table_offset = pe_offset + 24 + opt_header_size
            sections = []
            f.seek(section_table_offset)
            for _ in range(num_sections):
                sec = f.read(40)
                sections.append({
                    "name": sec[:8].rstrip(b"\x00").decode("ascii", errors="replace"),
                    "virtual_address": struct.unpack("<I", sec[12:16])[0],
                    "virtual_size": struct.unpack("<I", sec[8:12])[0],
                    "raw_offset": struct.unpack("<I", sec[20:24])[0],
                })

            def rva_to_offset(rva):
                for sec in sections:
                    if sec["virtual_address"] <= rva < sec["virtual_address"] + sec["virtual_size"]:
                        return rva - sec["virtual_address"] + sec["raw_offset"]
                return None

            offset = rva_to_offset(import_dir_rva)
            if offset is None:
                return deps

            f.seek(offset)
            while True:
                entry = f.read(20)
                if all(b == 0 for b in entry):
                    break
                name_rva = struct.unpack("<I", entry[12:16])[0]
                name_offset = rva_to_offset(name_rva)
                if name_offset:
                    current_pos = f.tell()
                    f.seek(name_offset)
                    dll_name = b""
                    while True:
                        ch = f.read(1)
                        if ch == b"\x00":
                            break
                        dll_name += ch
                    deps.append(dll_name.decode("ascii", errors="replace"))
                    f.seek(current_pos)
            return deps
    except Exception as e:
        return [f"(parse error: {e})"]


# ─── Detection Logic ─────────────────────────────────────────────────────────

def find_ce_installation(user_path=None):
    """
    Find Cheat Engine installation directory.
    Returns (path, source) or (None, None).
    """
    if user_path:
        p = Path(user_path)
        if p.is_dir():
            # Check for CE executable
            exes = list(p.glob("cheatengine*.exe")) + list(p.glob("Cheat Engine.exe"))
            if exes:
                return str(p), "user_specified"
            # Also accept paths that just have the lua DLLs
            luas = list(p.glob("lua*-64.dll")) + list(p.glob("lua*-32.dll"))
            if luas:
                return str(p), "user_specified"
        print_err(f"Path does not appear to be a CE installation: {user_path}")
        return None, None

    # Auto-scan common paths
    print_info("Scanning for Cheat Engine installation...")
    for p in COMMON_CE_PATHS:
        if Path(p).is_dir():
            luas = list(Path(p).glob("lua*-64.dll"))
            if luas:
                print_ok(f"Found CE at: {p}")
                return p, "auto_detected"

    # Try registry
    try:
        import winreg
        for root in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            for subkey in [r"SOFTWARE\Cheat Engine", r"SOFTWARE\WOW6432Node\Cheat Engine"]:
                try:
                    key = winreg.OpenKey(root, subkey)
                    path, _ = winreg.QueryValueEx(key, "Path")
                    winreg.CloseKey(key)
                    if Path(path).is_dir():
                        print_ok(f"Found CE via registry: {path}")
                        return path, "registry"
                except OSError:
                    pass
    except ImportError:
        pass

    print_err("Could not auto-detect Cheat Engine installation.")
    print_info("Please specify manually with: python deploy.py --ce \"C:\\path\\to\\Cheat Engine\"")
    return None, None


def detect_lua_version(ce_path):
    """
    Detect CE's Lua version by examining DLLs in the CE directory.
    Returns version key ("51", "53", "54") or None.
    """
    ce = Path(ce_path)
    detected = {}

    # Scan for luaXX-64.dll pattern
    for dll in ce.glob("lua*-64.dll"):
        name = dll.name.lower()
        m = re.match(r"lua(\d)(\d)-64\.dll", name)
        if m:
            key = m.group(1) + m.group(2)
            if key in LUA_VERSION_MAP:
                detected[key] = str(dll)

    if len(detected) == 1:
        key = list(detected.keys())[0]
        info = LUA_VERSION_MAP[key]
        print_ok(f"Detected Lua {info['ver']} ({info['dll']})")
        return key
    elif len(detected) == 0:
        print_err("No Lua DLL found in CE directory.")
        print_info("Expected pattern: luaXX-64.dll (e.g. lua53-64.dll)")
        return None
    else:
        print_warn(f"Multiple Lua versions detected: {list(detected.keys())}")
        # Prefer 5.3 > 5.4 > 5.1
        for preferred in ["53", "54", "51"]:
            if preferred in detected:
                info = LUA_VERSION_MAP[preferred]
                print_info(f"Selecting Lua {info['ver']} as default")
                return preferred
        return list(detected.keys())[0]


def detect_ce_arch(ce_path):
    """Detect CE architecture (x86 or x64) from the main executable."""
    ce = Path(ce_path)
    exe_candidates = list(ce.glob("cheatengine-x86_64*.exe")) + \
                     list(ce.glob("cheatengine-i386*.exe")) + \
                     list(ce.glob("Cheat Engine.exe"))
    for exe in exe_candidates:
        arch = get_pe_machine_type(str(exe))
        if arch:
            print_ok(f"CE architecture: {arch}")
            return arch
    print_warn("Could not determine CE architecture, assuming x64")
    return "x64"


# ─── Environment Check ───────────────────────────────────────────────────────

def check_environment(ce_path, lua_key):
    """Run pre-deployment checks and return (can_proceed, report)."""
    report = []
    all_ok = True

    info = LUA_VERSION_MAP.get(lua_key)
    if not info:
        return False, [f"Unknown Lua version key: {lua_key}"]

    ce = Path(ce_path)

    # 1. Check CE directory exists and is writable
    if not ce.is_dir():
        report.append(red(f"CE directory not found: {ce_path}"))
        return False, report
    if not os.access(str(ce), os.W_OK):
        report.append(yellow(f"CE directory may not be writable (run as admin if needed)"))
        # Not fatal - user might be doing dry-run

    # 2. Check CE Lua DLL exists
    expected_dll = ce / info["dll"]
    if expected_dll.exists():
        report.append(green(f"CE Lua DLL found: {info['dll']}"))
    else:
        report.append(red(f"CE Lua DLL not found: {info['dll']}"))
        all_ok = False

    # 3. Check pre-built binaries
    prebuilt_path = PREBUILT_DIR / ("lua" + lua_key)
    if prebuilt_path.is_dir():
        socket_dll = prebuilt_path / "socket" / "core.dll"
        mime_dll = prebuilt_path / "mime" / "core.dll"
        if socket_dll.exists() and mime_dll.exists():
            report.append(green(f"Pre-built binaries found for Lua {info['ver']}"))
            # Verify architecture
            arch = get_pe_machine_type(str(socket_dll))
            if arch:
                report.append(green(f"Pre-built binaries are {arch}"))
        else:
            report.append(yellow(f"Pre-built binaries incomplete for Lua {info['ver']}"))
            all_ok = False
    else:
        report.append(yellow(f"No pre-built binaries for Lua {info['ver']}"))
        all_ok = False

    # 4. Check VC++ runtime
    vcredit_ok = False
    for path in [
        r"C:\Windows\System32\vcruntime140.dll",
        r"C:\Windows\System32\vcruntime140_1.dll",
    ]:
        if Path(path).exists():
            vcredit_ok = True
            break
    if vcredit_ok:
        report.append(green("VC++ Runtime found"))
    else:
        report.append(yellow("VC++ Runtime not detected (may still work if CE bundles it)"))

    # 5. Check if VS tools available (for compilation fallback)
    vs_paths = []
    for base in [
        r"C:\Program Files\Microsoft Visual Studio",
        r"C:\Program Files (x86)\Microsoft Visual Studio",
    ]:
        if Path(base).is_dir():
            for vdir in Path(base).iterdir():
                if vdir.is_dir():
                    vs_paths.append(str(vdir / "Community"))
                    vs_paths.append(str(vdir / "Professional"))
                    vs_paths.append(str(vdir / "Enterprise"))

    has_vs = False
    for p in vs_paths:
        cl = Path(p) / "VC" / "Tools" / "MSVC"
        if cl.is_dir():
            has_vs = True
            report.append(green(f"Visual Studio found: {p}"))
            break
    if not has_vs:
        report.append(yellow("Visual Studio not found (compilation fallback unavailable)"))

    return all_ok, report


# ─── Deployment Logic ────────────────────────────────────────────────────────

def deploy(ce_path, lua_key, dry_run=False, force=False):
    """
    Deploy luasocket to CE installation.
    Returns (success, message_list).
    """
    info = LUA_VERSION_MAP.get(lua_key)
    if not info:
        return False, [f"Unknown Lua version: {lua_key}"]

    ce = Path(ce_path)
    prebuilt = PREBUILT_DIR / ("lua" + lua_key)
    messages = []
    deployed = []
    backed_up = []

    # Verify pre-built binaries exist
    src_socket_dll = prebuilt / "socket" / "core.dll"
    src_mime_dll = prebuilt / "mime" / "core.dll"
    if not src_socket_dll.exists():
        return False, [f"Pre-built socket/core.dll not found for Lua {info['ver']} at {src_socket_dll}"]
    if not src_mime_dll.exists():
        return False, [f"Pre-built mime/core.dll not found for Lua {info['ver']} at {src_mime_dll}"]

    # Verify pre-built arch matches CE
    prebuilt_arch = get_pe_machine_type(str(src_socket_dll))
    messages.append(f"Pre-built DLL architecture: {prebuilt_arch}")

    if not force and not dry_run:
        print()
        print_info("Ready to deploy:")
        print(f"    CE Path:     {ce_path}")
        print(f"    Lua Version: {info['ver']}")
        print(f"    Arch:        {prebuilt_arch}")
        print()
        response = input("  Proceed with deployment? [Y/n]: ").strip().lower()
        if response and response != "y" and response != "yes":
            messages.append("Deployment cancelled by user.")
            return False, messages

    def do_copy(src, dst):
        """Copy file with backup, respecting dry-run."""
        dst = Path(dst)
        if dry_run:
            messages.append(f"[DRY-RUN] Would copy: {Path(src).name} → {dst}")
            deployed.append(str(dst))
            return True
        try:
            # Backup existing file
            if dst.exists():
                backup = dst.with_suffix(dst.suffix + ".bak")
                shutil.copy2(str(dst), str(backup))
                backed_up.append(str(backup))
                messages.append(f"Backed up existing: {dst.name} → {backup.name}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))
            deployed.append(str(dst))
            return True
        except PermissionError:
            messages.append(red(f"Permission denied: {dst}. Try running as Administrator."))
            return False
        except Exception as e:
            messages.append(red(f"Failed to copy {src} → {dst}: {e}"))
            return False

    # ── Step 1: Deploy Lua modules (.lua files) ──
    print_header("Step 1/3: Deploying Lua modules")
    lua_modules_src = LUA_MODULES_DIR
    for f in LUA_FILES:
        src = lua_modules_src / f
        dst = ce / "lua" / f
        if not src.exists():
            messages.append(yellow(f"Missing source: {f}"))
            continue
        if do_copy(src, dst):
            print_ok(f"lua/{f}")

    # ── Step 2: Deploy DLLs ──
    print_header("Step 2/3: Deploying native DLLs")
    dll_mapping = {
        src_socket_dll: ce / "socket" / "core.dll",
        src_mime_dll: ce / "mime" / "core.dll",
    }
    for src, dst in dll_mapping.items():
        if do_copy(src, dst):
            print_ok(f"{dst.relative_to(ce)}")

    # ── Step 3: Verify ──
    print_header("Step 3/3: Verification")
    if not dry_run:
        # Check DLL dependencies
        for dst in [ce / "socket" / "core.dll", ce / "mime" / "core.dll"]:
            if dst.exists():
                deps = get_pe_dependencies(str(dst))
                expected_dep = info["dll"]
                if expected_dep.lower() in [d.lower() for d in deps]:
                    print_ok(f"{dst.name} → {expected_dep} ✓")
                else:
                    print_err(f"{dst.name} does NOT depend on {expected_dep}!")
                    print_info(f"  Found dependencies: {deps}")
                    messages.append(red(f"Dependency mismatch in {dst.name}"))
    else:
        print_info("Dry-run: skipping verification")

    # Summary
    print_header("Deployment Summary")
    print(f"  Lua version:  {info['ver']}")
    print(f"  CE path:      {ce_path}")
    print(f"  Files copied: {len(deployed)}")
    if backed_up:
        print(f"  Backups:      {len(backed_up)} files (*.bak)")
    if dry_run:
        print(yellow("  MODE:         DRY-RUN (no files were modified)"))

    messages.append(f"Deployment complete. {len(deployed)} files deployed.")
    return True, messages


# ─── Main Entry Point ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="LuaSocket CE Deployment Tool - Auto-detect, verify, and install luasocket for Cheat Engine.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python deploy.py                             # Interactive mode
  python deploy.py --ce "D:\\Cheat Engine 7.5"  # Specify CE root
  python deploy.py --dry-run                    # Preview only
  python deploy.py --force                      # Skip all prompts
  python deploy.py --check-only                 # Only check, don't install
        """,
    )
    parser.add_argument(
        "--ce", type=str, default=None, metavar="PATH",
        help="Path to Cheat Engine installation directory"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Skip confirmation prompts"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview deployment without writing any files"
    )
    parser.add_argument(
        "--check-only", action="store_true",
        help="Only check environment, do not deploy"
    )
    parser.add_argument(
        "--list-prebuilt", action="store_true",
        help="List available pre-built binaries and exit"
    )

    args = parser.parse_args()

    print()
    print(bold("=" * 72))
    print(bold("  LuaSocket CE Deployment Tool  v1.0"))
    print(bold("  github.com/maskfunction/"))
    print(bold("=" * 72))

    # List prebuilt
    if args.list_prebuilt:
        print_header("Available Pre-built Binaries")
        for key in sorted(LUA_VERSION_MAP.keys()):
            info = LUA_VERSION_MAP[key]
            pb = PREBUILT_DIR / ("lua" + key)
            socket_dll = pb / "socket" / "core.dll"
            mime_dll = pb / "mime" / "core.dll"
            status = green("AVAILABLE") if (socket_dll.exists() and mime_dll.exists()) else red("MISSING")
            arch = get_pe_machine_type(str(socket_dll)) if socket_dll.exists() else "?"
            print(f"  Lua {info['ver']}  →  {status}  ({arch})")
            if socket_dll.exists():
                deps = get_pe_dependencies(str(socket_dll))
                lua_dep = [d for d in deps if "lua" in d.lower()]
                print(f"         socket/core.dll depends: {lua_dep}")
        return

    # Step 1: Find CE
    print_header("Step 1: Locating Cheat Engine")
    ce_path, source = find_ce_installation(args.ce)
    if not ce_path:
        print()
        print_info("Usage: python deploy.py --ce \"C:\\path\\to\\Cheat Engine\"")
        sys.exit(1)

    # Step 2: Detect Lua version
    print_header("Step 2: Detecting Lua Version")
    lua_key = detect_lua_version(ce_path)
    if not lua_key:
        print()
        print_info("Supported Lua versions: 5.1, 5.3, 5.4")
        print_info("If your CE uses a different version, pre-built binaries may not be available.")
        sys.exit(1)

    info = LUA_VERSION_MAP[lua_key]

    # Step 3: Detect architecture
    print_header("Step 3: Checking Architecture")
    ce_arch = detect_ce_arch(ce_path)

    # Step 4: Environment check
    print_header("Step 4: Environment Check")
    env_ok, report = check_environment(ce_path, lua_key)
    for line in report:
        print(f"  {line}")

    if args.check_only:
        print()
        if env_ok:
            print_ok("Environment check passed. Ready to deploy.")
            print_info("Run without --check-only to deploy.")
        else:
            print_warn("Some checks failed. Review the report above.")
        return

    if not env_ok:
        print()
        print_warn("Some pre-deployment checks failed.")
        if not args.force:
            response = input("  Continue anyway? [y/N]: ").strip().lower()
            if response != "y" and response != "yes":
                print_info("Aborted.")
                return

    # Step 5: Deploy
    success, msgs = deploy(ce_path, lua_key, dry_run=args.dry_run, force=args.force)
    if not success:
        print()
        for m in msgs:
            print(f"  {m}")
        sys.exit(1)

    # Final notes
    if not args.dry_run:
        print()
        print(bold("─" * 72))
        print(green("  Deployment complete!"))
        print()
        print("  To verify in Cheat Engine, open Lua Engine and run:")
        print(cyan('    print(require("socket")._VERSION)'))
        print(cyan('    print(require("mime")._VERSION)'))
        print()
        print("  Expected output:")
        print("    LuaSocket 3.1.0")
        print("    MIME 1.0.3")
        print(bold("─" * 72))


if __name__ == "__main__":
    main()
