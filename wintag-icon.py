#!/usr/bin/env python3
# 機能：xprop の _NET_WM_ICON 出力（標準入力）から最大サイズのアイコンを PNG で保存する
# 入力：標準入力  xprop -notype 32c _NET_WM_ICON の出力
#       argv[1]   保存先のパス
# 出力：PNG ファイル（ウィンドウにアイコンがなければ何も作らない）
import re
import struct
import sys
import zlib

# ===== パラメータ =====
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"  # PNG ファイルの先頭シグネチャ
BIT_DEPTH = 8                         # 1 チャンネルあたりのビット数
COLOR_TYPE_RGBA = 6                   # PNG のカラータイプ（RGBA）
FILTER_NONE = b"\x00"                 # 各行の先頭に付けるフィルタ種別（なし）


def chunk(tag, data):
    """機能：PNG チャンクを作る
    入力：tag  チャンク種別（bytes）, data  中身（bytes）
    出力：長さ・種別・中身・CRC を連結したチャンク（bytes）"""
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))


def largest_icon(values):
    """機能：[幅, 高さ, 画素...] が繰り返される並びから最大のアイコンを取り出す
    入力：values  整数リスト
    出力：(幅, 高さ, ARGB 画素リスト)、アイコンがなければ None"""
    best, i = None, 0
    while i + 2 <= len(values):
        w, h = values[i], values[i + 1]
        pixels = values[i + 2 : i + 2 + w * h]
        # 画素が揃っている（途中で切れていない）もののうち、面積が最大のものを残す
        if w > 0 and h > 0 and len(pixels) == w * h and (best is None or w * h > best[0] * best[1]):
            best = (w, h, pixels)
        i += 2 + w * h
    return best


def to_png(w, h, argb):
    """機能：ARGB 画素を PNG のバイト列に変換する
    入力：w  幅, h  高さ, argb  ARGB 画素リスト（32bit 整数）
    出力：PNG データ（bytes）"""
    # ARGB → RGBA に並べ替え、各行の先頭にフィルタ種別を付ける
    rows = b"".join(
        FILTER_NONE + b"".join(
            struct.pack("BBBB", (p >> 16) & 0xFF, (p >> 8) & 0xFF, p & 0xFF, (p >> 24) & 0xFF)
            for p in argb[y * w : (y + 1) * w]
        )
        for y in range(h)
    )
    ihdr = struct.pack(">IIBBBBB", w, h, BIT_DEPTH, COLOR_TYPE_RGBA, 0, 0, 0)
    return PNG_SIGNATURE + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


# 「_NET_WM_ICON = 16, 16, ...」の = より後ろの数値をすべて取り出す
values = [int(v) for v in re.findall(r"\d+", sys.stdin.read().split("=", 1)[-1])]
icon = largest_icon(values)
if icon:
    with open(sys.argv[1], "wb") as f:
        f.write(to_png(*icon))
