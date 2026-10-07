# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 概要

`wintag` は GNOME（X11）向けの Bash 製ツール（補助の Python スクリプト 2 本付き）。Docker コンテナで動く GUI アプリのウィンドウタイトルの先頭に `[コンテナ名]` を付け、同じアプリが GNOME Dock の 1 つのアイコンにまとめられても見分けられるようにする。ランチャー（`.desktop`）はアプリごとに 1 つで、右クリックメニュー（Desktop Action）から起動元のコンテナを選んで起動できる。

Dock でコンテナごとにアイコンを分けることはしない（2.1.0 までは WM_CLASS のインスタンス名を付け替えて分けようとしたが、Ubuntu Dock では 1 つにまとまった）。まとまる前提で設計すること。

テスト、リンター設定はない。リポジトリは https://github.com/MaeharaTakumi/wintag で、`.deb` は GitHub Release に添付する（`*.deb`・`build/` は .gitignore 済み）。

## コマンド

```bash
./build.sh                                   # wintag_<VERSION>_all.deb を作成（組み立ては build/wintag/）
sudo apt install ./wintag_<VERSION>_all.deb  # 作成したパッケージをインストール
wintag on | off | status                     # ウィンドウ監視のオン・オフ（既定はオフ）
wintag watch | register [コマンド...] | list | remove <ID> | cleanup | launch <ID>
bash -n wintag && shellcheck wintag          # 構文・静的チェック（shellcheck は入っていれば）
gh release create v<VERSION> wintag_<VERSION>_all.deb --title "wintag <VERSION>" --notes "..."
```

`wintag` は補助スクリプトを `LIB_DIR=/usr/lib/wintag` から固定で参照するため、ソースフォルダで `./wintag` を実行しても**インストール済み**の `wintag-icon.py`・`wintag-source.py` が使われる。変更を試すには、パッケージを作り直して再インストールするか、`LIB_DIR` を書き換えた複製を使う。インストールせずに試すときは、`HOME` と `XDG_RUNTIME_DIR`（ロックファイルの場所）を作業用フォルダに向けた複製を使うと、本物のエントリや動いている監視とぶつからない。

動作確認には、X11 セッション、Docker、`xprop`/`xwininfo`（x11-utils）、`xhost` が必要。

## アーキテクチャ

**ファイルとインストール先**（`build.sh` で指定）：
- `wintag` → `/usr/bin/wintag`：プログラム本体。末尾の `case` でサブコマンドを振り分ける。
- `wintag-icon.py` → `/usr/lib/wintag/`：標準入力で `xprop -notype 32c _NET_WM_ICON` の出力を受け取り、最大サイズのアイコンを PNG で保存する（標準ライブラリだけで PNG を生成）。`xprop` は既定で 250,000 バイトで黙って切り詰めるため、呼び出し側で `-len "${ICON_MAX_BYTES}"` を付け、こちらでも画素が欠けたアイコンは捨てる。
- `wintag-source.py` → `/usr/lib/wintag/`：ウィンドウ ID を受け取り、`ctypes` で libXRes の `XResQueryClientIds` を呼んで X クライアントのホスト側 PID を得る。`/proc/<PID>/cgroup` の `docker[-/]<64 桁>` からコンテナを、`/proc/<PID>/status` の `NSpid` 末尾からコンテナ内 PID を求め、「起動元 PID」を出力する。
- `build.sh` は preinst/postinst/postrm に `dpkg-maintscript-helper rm_conffile` を書き、2.1.0 以前が置いた `/etc/xdg/autostart/wintag-watch.desktop` を更新時に削除する。

**監視のオン・オフ**：`wintag on` は `~/.config/autostart/wintag-watch.desktop` を作り、監視が動いていなければ `setsid -f wintag watch` で開始する。`off` はそのファイルを消し、ロックファイル（`${XDG_RUNTIME_DIR}/wintag-watch-<UID>.lock`、中身は watch の PID）から PID を読んで止める。動いているかは `flock -n` でロックを取れるかで判定する（`watch_pid`）。

**処理の流れ（`watch_windows`）：**
1. ロックを `flock` して 1 ユーザー 1 つに限り、PID を書く。子プロセスにロックの fd 9 を渡さないよう `9>&-` で閉じる。終了時（`off` の SIGTERM を含む）は EXIT トラップで子の `xprop` をすべて止める。
2. 最初に `cleanup` を 1 回実行し、その後 `xprop -root -spy _NET_CLIENT_LIST` を監視して、新しく現れたウィンドウ ID ごとに `auto_tag` を呼ぶ。
3. `window_source` が「起動元 PID」（PID は起動元の名前空間での番号）を返す。まず `wintag-source.py`（XRes）で判定し、失敗したとき（TCP 接続など）だけ、`WM_CLIENT_MACHINE` がホストと異なり、ホスト名が一致するコンテナが 1 つのときに限り `_NET_WM_PID` を使う。`_NET_WM_PID` は名前空間ごとの番号で、`--net=host` の複数コンテナやホストと衝突するため、PID だけで起動元を推測しないこと。
4. `auto_tag` はコンテナのウィンドウだけを対象にし、未登録なら `capture` で登録して、タイトルの接頭辞（`TITLE_FORMAT`）を返す。
5. 接頭辞があれば、ウィンドウごとに `xprop -id <W> -notype -spy _NET_WM_NAME` を起動し、出力を `keep_title` に流す。`keep_title` は接頭辞がなければ `xprop -f _NET_WM_NAME 8u -set` で付け直す（`xprop` の出力は `"` と `\` がエスケープされているので戻す）。ウィンドウが閉じると `xprop -spy` は自分で終了するが、一覧から消えたウィンドウの分も `SPIES` から止める。

**エントリと `.desktop`**：エントリは「アプリ（WM_CLASS のクラス名）× 起動元」ごと、`.desktop` はアプリごと。
- エントリ ID は `host-<クラス名>` または `<コンテナ ID 先頭 12 桁>-<クラス名>`（英数字以外は `_` に置換）。
- `~/.local/share/wintag/<ID>/`：`class`（クラス名）、`name`（起動元の表示名。コンテナ名または `HOST_LABEL`）、`cmdline`・`environ`（どちらも NUL 区切り。値に改行を含む `BASH_FUNC_*` があるため改行区切りにしない）、`cwd`、`icon.png`。コンテナのエントリには `container`（フル ID）と `user`（`uid:gid`）も入る。`environ` は `名前=値` の形の項目だけを残し（Electron 系は環境変数の領域を上書きするため）、ホストは `HOST_SKIP_VARS`、コンテナは `CONTAINER_SKIP_VARS` を除く。
- `~/.local/share/applications/wintag-<クラス名>.desktop` は `write_desktop` が同じクラスの全エントリから作る。`StartupWMClass=<クラス名>`、`Exec` はフォルダの更新時刻が最新のエントリ（`launch` が `touch` する＝最後に使った起動元）、`Actions` は表示名順の `src1;src2;…`。内容が変わったときだけ置き換える。
- `refresh_desktops` は全クラスの `.desktop` を作り直し、対応するエントリのない `wintag-*.desktop` を消す。`cleanup`・`remove` の後に呼ぶ。
- 旧形式のエントリ（`class`・`name` がない 2.1.0 以前のもの）は `migrate_entry` が旧 `wintag-<ID>.desktop` の `Name`（「クラス名 (コンテナ名)」）や `StartupWMClass` から補う。2.0.0 の改行区切りの `env` も `launch` は読める。
- `capture` は `.<ID>.<PID>` の一時フォルダに集めてから置き換えるので、途中で失敗しても既存のエントリは残る。
- `auto_tag` は既存のエントリを上書き**しない**。そのため、`register` で手動設定した起動コマンドは後の自動検出でも保持される。

**`launch`**：コンテナの場合は `xhost +local:` と `docker start` を実行してから、保存した環境変数・作業ディレクトリ・ユーザーと現在の `DISPLAY` で `docker exec` する（タイトルは watch が付ける）。ホストの場合は、現在の環境に保存した環境変数を重ねて `exec` する（セッション固有の変数は保存していないので、現在の値が使われる）。失敗は `fail` で標準エラーと `notify-send` に出す（Dock からの起動では標準エラーが見えないため）。

**`cleanup`** は存在しなくなったコンテナのエントリを削除する。Docker に接続できない場合は何も削除せずに終了する。

## 規約

- コメントとユーザー向けメッセージは日本語。すべての関数に `# 機能： / # 入力： / # 出力：` のヘッダーを付ける（Python は docstring に同じ形式）。この形式を守ること。
- 調整用の値は各ファイル先頭の `# ===== パラメータ =====` ブロックに 1 行ずつ、行末コメント付きで置く。
- 使い方の説明は `wintag` の 2〜12 行目で、`HELP_LINES="2,12p"` で表示する。先頭コメントの行数が変わったら更新すること。パッケージには `README.md` を同梱する。
- エントリ ID はパスに使うため、外から受け取る ID は `valid_id` で確認する。
- リリース時は `build.sh` の `VERSION` を上げる。`.deb` のファイル名はこれから決まる。
