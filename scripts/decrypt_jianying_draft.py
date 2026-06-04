import ctypes
import pathlib
import sys


DEC_SYMBOL = "?decrypt@EncryptUtils@lvve@@QEAA?AV?$basic_string@DU?$char_traits@D@std@@V?$allocator@D@2@@std@@AEBV34@0AEA_N@Z"


class _StringData(ctypes.Union):
    _fields_ = [("small", ctypes.c_char * 16), ("ptr", ctypes.c_void_p)]


class MsvcString(ctypes.Structure):
    _fields_ = [
        ("data", _StringData),
        ("size", ctypes.c_ulonglong),
        ("capacity", ctypes.c_ulonglong),
    ]


def make_msvc_string(payload: bytes):
    storage = ctypes.create_string_buffer(payload + b"\0")
    s = MsvcString()
    s.size = len(payload)
    if len(payload) < 16:
        s.capacity = 15
        ctypes.memset(ctypes.addressof(s.data), 0, 16)
        ctypes.memmove(ctypes.addressof(s.data), payload, len(payload))
    else:
        s.capacity = len(payload)
        s.data.ptr = ctypes.cast(storage, ctypes.c_void_p).value
    return s, storage


def take_msvc_string(s: MsvcString) -> bytes:
    if s.size > (1 << 34):
        raise RuntimeError(f"refusing suspicious output size: {s.size}")
    if s.capacity < 16:
        return bytes(s.data.small[: s.size])
    if not s.data.ptr:
        return b""
    return ctypes.string_at(s.data.ptr, s.size)


def decrypt_file(install_dir: pathlib.Path, src: pathlib.Path, out: pathlib.Path) -> None:
    dll_path = install_dir / "videoeditor.dll"
    if not dll_path.exists():
        raise FileNotFoundError(f"videoeditor.dll not found: {dll_path}")

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.SetErrorMode(0x0001 | 0x8000)
    kernel32.SetDefaultDllDirectories.argtypes = [ctypes.c_uint32]
    kernel32.SetDefaultDllDirectories.restype = ctypes.c_bool
    kernel32.AddDllDirectory.argtypes = [ctypes.c_wchar_p]
    kernel32.AddDllDirectory.restype = ctypes.c_void_p
    kernel32.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]
    kernel32.LoadLibraryExW.restype = ctypes.c_void_p

    load_dll_dir = 0x00000100
    load_app_dir = 0x00000200
    load_user_dirs = 0x00000400
    load_system32 = 0x00000800

    kernel32.SetDefaultDllDirectories(load_app_dir | load_system32 | load_user_dirs)
    kernel32.AddDllDirectory(str(install_dir))
    handle = kernel32.LoadLibraryExW(
        str(dll_path),
        None,
        load_dll_dir | load_app_dir | load_user_dirs | load_system32,
    )
    if not handle:
        raise OSError(f"LoadLibraryExW failed gle={ctypes.get_last_error()} path={dll_path}")

    dll = ctypes.WinDLL(str(dll_path), handle=handle)
    decrypt = getattr(dll, DEC_SYMBOL)
    decrypt.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(MsvcString),
        ctypes.POINTER(MsvcString),
        ctypes.POINTER(MsvcString),
        ctypes.POINTER(ctypes.c_bool),
    ]
    decrypt.restype = ctypes.POINTER(MsvcString)

    encrypted = src.read_bytes()
    in_s, in_storage = make_msvc_string(encrypted)
    param_s, param_storage = make_msvc_string(b"{}")
    ret_s = MsvcString()
    ok = ctypes.c_bool(False)

    decrypt(None, ctypes.byref(ret_s), ctypes.byref(in_s), ctypes.byref(param_s), ctypes.byref(ok))
    plain = take_msvc_string(ret_s)
    if not ok.value or not plain:
        raise RuntimeError(f"decrypt failed for {src}")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(plain)


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: python decrypt_jianying_draft.py <JY_INSTALL_DIR> <encrypted_json> <output_json>", file=sys.stderr)
        return 64
    decrypt_file(pathlib.Path(sys.argv[1]).resolve(), pathlib.Path(sys.argv[2]).resolve(), pathlib.Path(sys.argv[3]).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
