# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 概要

`wintag` は GNOME（X11）向けの Bash 製ツール（補助の Python スクリプト 1 本付き）。Docker コンテナで動く GUI アプリのウィンドウタイトルの先頭に `[コンテナ名]` を付け、同じアプリが GNOME Dock の 1 つのアイコンにまとめられても見分けられるようにする。機能はこれと、ウィンドウ監視のオン・オフ（既定はオフ）だけ。

方針：
- アプリの起動はユーザーがコマンドで行う。起動・登録・ランチャー（`.desktop`）・アイコン作成などの機能は付けない（2.1.0 までにあったが削除した）。頼まれていない機能を足さないこと。
- Dock でコンテナごとにアイコンを分けることはしない（WM_CLASS のインスタンス名を付け替えても、Ubuntu Dock では 1 つにまとまった）。

テスト、リンター設定はない。リポジトリは https://github.com/MaeharaTakumi/wintag で、`.deb` は GitHub Release に添付する（`*.deb`・`build/` は .gitignore 済み）。

## コマンド

```bash
./build.sh                                   # wintag_<VERSION>_all.deb を作成（組み立ては build/wintag/）
sudo apt install ./wintag_<VERSION>_all.deb  # 作成したパッケージをインストール
wintag on | off | watch
bash -n wintag && shellcheck wintag          # 構文・静的チェック（shellcheck は入っていれば）
gh release create v<VERSION> wintag_<VERSION>_all.deb --title "wintag <VERSION>" --notes "..."
```

`wintag` は `SOURCE_SCRIPT=/usr/lib/wintag/wintag-source.py` を固定で参照するため、ソースフォルダで `./wintag` を実行しても**インストール済み**の判定スクリプトが使われる。インストールせずに試すときは、`SOURCE_SCRIPT` を書き換えた複製を、`HOME` と `XDG_RUNTIME_DIR`（ロックファイルの場所）を作業用フォルダに向けて実行すると、本物の自動起動設定や動いている監視とぶつからない。なお、テストでも本物のウィンドウのタイトルは変わる。

動作確認には、X11 セッション、Docker、`xprop`（x11-utils）が必要。

## アーキテクチャ

**ファイルとインストール先**（`build.sh` で指定）：
- `wintag` → `/usr/bin/wintag`：プログラム本体。末尾の `case` でサブコマンドを振り分ける。
- `wintag-source.py` → `/usr/lib/wintag/`：ウィンドウ ID を受け取り、`ctypes` で libXRes の `XResQueryClientIds` を呼んで X クライアントのホスト側 PID を得て、`/proc/<PID>/cgroup` の `docker[-/]<64 桁>` からコンテナのフル ID を出力する（ホストのアプリ・判定できないときは何も出力しない）。`_NET_WM_PID` は PID 名前空間ごとの番号で、`--net=host` の複数コンテナやホストと衝突するため、起動元の判定に使わないこと。
- `build.sh` は preinst/postinst/postrm に `dpkg-maintscript-helper rm_conffile` を書き、2.1.0 以前が置いた `/etc/xdg/autostart/wintag-watch.desktop` を更新時に削除する。

**オン・オフ**：`wintag on` は `~/.config/autostart/wintag-watch.desktop` を作り、監視が動いていなければ `setsid -f wintag watch` で開始する。`off` はそのファイルを消し、ロックファイル（`${XDG_RUNTIME_DIR}/wintag-watch-<UID>.lock`、中身は watch の PID）から PID を読んで止める。動いているかは `flock -n` でロックを取れるかで判定する。

**`watch_windows`**：
1. ロックを `flock` して 1 ユーザー 1 つに限り、PID を書く。子プロセスにロックの fd 9 を渡さないよう `9>&-` で閉じる。終了時（`off` の SIGTERM を含む）は EXIT トラップで子の `xprop` をすべて止める。
2. `xprop -root -spy _NET_CLIENT_LIST` を監視し、新しく現れたウィンドウごとに `title_prefix` を呼ぶ。コンテナのウィンドウなら `docker inspect` でコンテナ名を得て接頭辞（`TITLE_FORMAT`）を返す。
3. 接頭辞があれば、ウィンドウごとに `xprop -id <W> -notype -spy _NET_WM_NAME` を起動し、出力を `keep_title` に流す。`keep_title` は接頭辞がなければ `xprop -f _NET_WM_NAME 8u -set` で付け直す（`xprop` の出力は `"` と `\` がエスケープされているので戻す）。ウィンドウが閉じると `xprop -spy` は自分で終了するが、一覧から消えたウィンドウの分も `SPIES` から止める。

## 規約

- コメントとユーザー向けメッセージは日本語。すべての関数に `# 機能： / # 入力： / # 出力：` のヘッダーを付ける（Python は docstring に同じ形式）。この形式を守ること。
- 調整用の値は各ファイル先頭の `# ===== パラメータ =====` ブロックに 1 行ずつ、行末コメント付きで置く。
- 使い方の説明は `wintag` の 2〜6 行目で、`HELP_LINES="2,6p"` で表示する。先頭コメントの行数が変わったら更新すること。パッケージには `README.md` を同梱する。
- リリース時は `build.sh` の `VERSION` を上げる。`.deb` のファイル名はこれから決まる。
