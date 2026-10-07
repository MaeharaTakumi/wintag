# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 概要

`wintag` は GNOME（X11）向けの Bash 製ツール（補助の Python スクリプト 1 本付き）。GUI アプリのウィンドウを起動元（ホスト、または個々の Docker コンテナ）ごとに見分けられるようにする。コンテナごとに専用の `.desktop`・表示名・アイコンを用意し、異なるコンテナの同じアプリが GNOME Dock 上でまとめられないようにする。git リポジトリ、テスト、リンター設定はない。

## コマンド

```bash
./build.sh                                   # wintag_<VERSION>_all.deb を作成（組み立ては build/wintag/）
sudo apt install ./wintag_2.0.0_all.deb      # 作成したパッケージをインストール
wintag watch | register [コマンド...] | list | remove <ID> | cleanup | launch <ID>
bash -n wintag && shellcheck wintag          # 構文・静的チェック（shellcheck は入っていれば）
```

`wintag` は補助スクリプトを `LIB_DIR=/usr/lib/wintag` から固定で参照するため、ソースフォルダで `./wintag` を実行しても**インストール済み**の `wintag-icon.py`・`wintag-source.py` が使われる。変更を試すには、パッケージを作り直して再インストールするか、`LIB_DIR` を書き換えた複製を使う。

動作確認には、X11 セッション、Docker、`xprop`/`xwininfo`（x11-utils）、`xhost`、`xdotool` が必要。

## アーキテクチャ

**ファイルとインストール先**（`build.sh` で指定）：
- `wintag` → `/usr/bin/wintag`：プログラム本体。末尾の `case` でサブコマンドを振り分ける。
- `wintag-icon.py` → `/usr/lib/wintag/`：標準入力で `xprop -notype 32c _NET_WM_ICON` の出力を受け取り、最大サイズのアイコンを PNG で保存する（標準ライブラリだけで PNG を生成）。`xprop` は既定で 250,000 バイトで黙って切り詰めるため、呼び出し側で `-len "${ICON_MAX_BYTES}"` を付け、こちらでも画素が欠けたアイコンは捨てる。
- `wintag-source.py` → `/usr/lib/wintag/`：ウィンドウ ID を受け取り、`ctypes` で libXRes の `XResQueryClientIds` を呼んで X クライアントのホスト側 PID を得る。`/proc/<PID>/cgroup` の `docker[-/]<64 桁>` からコンテナを、`/proc/<PID>/status` の `NSpid` 末尾からコンテナ内 PID を求め、「起動元 PID」を出力する。
- `wintag-watch.desktop` → `/etc/xdg/autostart/`：ログイン時に `wintag watch` を起動する。conffile として登録。

**処理の流れ：**
1. `watch_windows` は最初に `cleanup` を 1 回実行し、その後 `xprop -root -spy _NET_CLIENT_LIST` を監視して、新しく現れたウィンドウ ID ごとに `auto_tag` を呼ぶ。
2. `window_source` が「起動元 PID」（PID は起動元の名前空間での番号）を返す。まず `wintag-source.py`（XRes）で判定し、失敗したとき（TCP 接続など）だけ、`WM_CLIENT_MACHINE` がホストと異なり、ホスト名が一致するコンテナが 1 つのときに限り `_NET_WM_PID` を使う。`_NET_WM_PID` は名前空間ごとの番号で、`--net=host` の複数コンテナやホストと衝突するため、PID だけで起動元を推測しないこと。
3. `auto_tag` はコンテナのウィンドウだけを対象にする。エントリがなければ `capture` で作成し、`set_tag` が `xdotool set_window --classname` でウィンドウの WM_CLASS の**インスタンス名**をエントリ ID に付け替える。生成する `.desktop` は `StartupWMClass=<エントリ ID>` なので、GNOME がそのウィンドウをコンテナ専用のランチャーに結びつける。
4. ホストのアプリは自動では付け替えない。`register` で手動登録したときだけエントリができ、その `.desktop` は元の WM_CLASS を `StartupWMClass` に使う。

**エントリごとのデータ**：エントリ ID は `host-<クラス名>` または `<コンテナ ID 先頭 12 桁>-<クラス名>`（英数字以外は `_` に置換）。
- `~/.local/share/wintag/<ID>/`：`cmdline`・`environ`（どちらも NUL 区切り。値に改行を含む `BASH_FUNC_*` があるため改行区切りにしない）、`cwd`、`icon.png`。コンテナのエントリには `container`（フル ID）と `user`（`uid:gid`）も入る。`environ` は `名前=値` の形の項目だけを残し（Electron 系は環境変数の領域を上書きするため）、ホストは `HOST_SKIP_VARS`、コンテナは `CONTAINER_SKIP_VARS` を除く。2.0.0 で作られたエントリは改行区切りの `env` を持ち、`launch` はこれも読める。
- `capture` は `.<ID>.<PID>` の一時フォルダに集めてから置き換えるので、途中で失敗しても既存のエントリは残る。
- `~/.local/share/applications/wintag-<ID>.desktop`（`Exec=<wintag のパス> launch <ID>`）。
- `auto_tag` は既存のエントリを上書き**しない**。そのため、`register` で手動設定した起動コマンドは後の自動検出でも保持される。

**`launch`**：コンテナの場合は `xhost +local:` と `docker start` を実行してから、保存した環境変数・作業ディレクトリ・ユーザーと現在の `DISPLAY` で `docker exec` する（付け替えは常駐中の watch に任せる）。ホストの場合は、現在の環境に保存した環境変数を重ねて `exec` する（セッション固有の変数は保存していないので、現在の値が使われる）。失敗は `fail` で標準エラーと `notify-send` に出す（Dock からの起動では標準エラーが見えないため）。

**`watch`** は `${XDG_RUNTIME_DIR}/wintag-watch-<UID>.lock` を `flock` して 1 ユーザー 1 つに限る。子プロセスにロックの fd 9 を渡さないよう `9>&-` で閉じている。

**`cleanup`** は存在しなくなったコンテナのエントリを削除する。Docker に接続できない場合は何も削除せずに終了する。

## 規約

- コメントとユーザー向けメッセージは日本語。すべての関数に `# 機能： / # 入力： / # 出力：` のヘッダーを付ける（Python は docstring に同じ形式）。この形式を守ること。
- 調整用の値は各ファイル先頭の `# ===== パラメータ =====` ブロックに 1 行ずつ、行末コメント付きで置く。
- 使い方の説明は `wintag` の 2〜9 行目で、`HELP_LINES="2,9p"` で表示する。先頭コメントの行数が変わったら更新すること。パッケージには `README.md` を同梱する。
- エントリ ID はパスに使うため、外から受け取る ID は `valid_id` で確認する。
- リリース時は `build.sh` の `VERSION` を上げる。`.deb` のファイル名はこれから決まる。
