#!/usr/bin/env python3
# 機能：ウィンドウを作った X クライアントのプロセスから、起動元（ホスト・Docker コンテナ）と PID を調べる
#       X サーバー（XRes 拡張）から見たホスト側の PID を使うため、--net=host のコンテナや
#       PID が重なる場合でも起動元が一意に決まる
# 入力：argv[1]   ウィンドウ ID（例 0x3a00004）
# 出力：「起動元 PID」を標準出力へ（起動元はコンテナのフル ID または host、PID は起動元から見た番号）
#       判定できなければ（TCP 経由の X 接続など）何も出力しない
import ctypes
import ctypes.util
import re
import sys

# ===== パラメータ =====
HOST = "host"                                      # ホストで動くアプリを表す起動元名
XRES_CLIENT_ID_PID_MASK = 1 << 1                   # XResQueryClientIds で PID を問い合わせるマスク
X_SUCCESS = 0                                      # Xlib の成功ステータス
CONTAINER_RE = re.compile(r"docker[-/]([0-9a-f]{64})")  # cgroup のパスに含まれるコンテナ ID


class ClientIdSpec(ctypes.Structure):
    """XResClientIdSpec 構造体"""
    _fields_ = [("client", ctypes.c_ulong), ("mask", ctypes.c_uint)]


class ClientIdValue(ctypes.Structure):
    """XResClientIdValue 構造体"""
    _fields_ = [("spec", ClientIdSpec), ("length", ctypes.c_long), ("value", ctypes.c_void_p)]


# X のエラー（ウィンドウが既に閉じた場合など）でプロセスが終了しないよう、何もしないハンドラを使う
ERROR_HANDLER = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)(lambda dpy, ev: 0)


def client_pid(win):
    """機能：ウィンドウを作った X クライアントのホスト側 PID を X サーバーに問い合わせる
    入力：win  ウィンドウ ID（整数）
    出力：PID（整数）、取得できなければ None"""
    try:
        x11 = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
        xres = ctypes.CDLL(ctypes.util.find_library("XRes") or "libXRes.so.1")
    except OSError:
        return None
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    x11.XSetErrorHandler.argtypes = [ctypes.c_void_p]
    xres.XResQueryClientIds.argtypes = [
        ctypes.c_void_p, ctypes.c_long, ctypes.POINTER(ClientIdSpec),
        ctypes.POINTER(ctypes.c_long), ctypes.POINTER(ctypes.POINTER(ClientIdValue))]
    xres.XResGetClientPid.argtypes = [ctypes.POINTER(ClientIdValue)]
    xres.XResClientIdsDestroy.argtypes = [ctypes.c_long, ctypes.POINTER(ClientIdValue)]

    dpy = x11.XOpenDisplay(None)
    if not dpy:
        return None
    x11.XSetErrorHandler(ctypes.cast(ERROR_HANDLER, ctypes.c_void_p))
    pid = None
    spec = ClientIdSpec(win, XRES_CLIENT_ID_PID_MASK)
    count = ctypes.c_long()
    ids = ctypes.POINTER(ClientIdValue)()
    if xres.XResQueryClientIds(dpy, 1, ctypes.byref(spec), ctypes.byref(count), ctypes.byref(ids)) == X_SUCCESS:
        for i in range(count.value):
            p = xres.XResGetClientPid(ctypes.byref(ids[i]))
            if p > 0:
                pid = p
        xres.XResClientIdsDestroy(count, ids)
    x11.XCloseDisplay(dpy)
    return pid


def source_of(pid):
    """機能：ホスト側 PID のプロセスがどのコンテナに属するかを cgroup から調べる
    入力：pid  ホスト側 PID
    出力：(起動元, 起動元から見た PID)、プロセスがなければ None"""
    try:
        with open(f"/proc/{pid}/cgroup") as f:
            match = CONTAINER_RE.search(f.read())
        with open(f"/proc/{pid}/status") as f:
            # NSpid の最後の値が、プロセス自身の PID 名前空間での番号
            nspid = next(line.split()[-1] for line in f if line.startswith("NSpid:"))
    except (OSError, StopIteration):
        return None
    return (match.group(1), nspid) if match else (HOST, str(pid))


pid = client_pid(int(sys.argv[1], 16))
src = source_of(pid) if pid else None
if src:
    print(*src)
