# wintag

Docker コンテナで動く GUI アプリのウィンドウタイトルの先頭に、起動元のコンテナ名を付けるツールです。

複数の Docker コンテナで同じアプリ（例：rviz）を動かすと、GNOME Dock 上では 1 つのアイコンにまとめられ、どのウィンドウがどのコンテナのものか分からなくなります。wintag はタイトルにコンテナ名を付けるので、Dock のアイコンをクリックしたときのウィンドウ一覧や Alt+Tab で見分けられます。

```
Dock: [rviz2]（1 つのアイコン）

  クリック → ウィンドウ一覧
    [whillLocalizer] localization2.rviz - RViz
    [20261002] example.rviz - RViz
```

## 動作環境

- GNOME（X11 セッション）
- bash 4.4 以上、python3、x11-utils、libxres1（パッケージの依存関係として自動で入ります）
- Docker：コンテナ名の取得に、ログインユーザーが `sudo` なしで `docker` コマンドを使えること（使えない場合はコンテナ ID の先頭 12 桁を表示します）

## インストール

[Releases](https://github.com/MaeharaTakumi/wintag/releases) から `.deb` をダウンロードするか、ソースからビルドします。

```bash
./build.sh
```

```bash
sudo apt install ./wintag_2.2.0_all.deb
```

## 使い方

ウィンドウ監視は、インストール直後はオフです。オンにすると、すぐに監視が始まり、次回以降もログイン時に自動で始まります。

```bash
wintag on
```

```bash
wintag off
```

監視がオンの間は、コンテナでアプリのウィンドウが開くと、タイトルの先頭に `[コンテナ名]` が付きます。アプリがタイトルを変えても付け直します。ホストのアプリのタイトルは変更しません。

オン・オフはユーザーごとの設定です（`~/.config/autostart/wintag-watch.desktop` の有無）。

## 仕組み

- X サーバー（XRes 拡張）にウィンドウを作ったプロセスを問い合わせ、そのプロセスの cgroup から起動元のコンテナを判定します。`--net=host` のコンテナが複数あっても区別できます。X に TCP で接続しているアプリは判定できません。
- タイトルは、ウィンドウごとに `_NET_WM_NAME` の変化を監視して付け直します。ウィンドウが閉じると監視も終わります。

## 注意

- 監視は 1 ユーザーにつき 1 つしか動きません。
- 監視をオフにしても、付けたタイトルはアプリが次にタイトルを変えるまで残ります。

## 2.1.0 以前からの更新

2.2.0 から機能をタイトル付けだけにし、監視は既定でオフになりました。更新すると全ユーザー向けの自動起動設定は削除されます。動いている古い監視を止めてから更新し、必要なら `wintag on` でオンにしてください。

```bash
pkill -f '/usr/bin/wintag watch'
```

以前の版が作ったデータ（登録エントリ・ランチャー）は使わなくなったので、削除してください。

```bash
rm -rf ~/.local/share/wintag ~/.local/share/applications/wintag-*.desktop
```

## アンインストール

先に監視をオフにしてから削除します。

```bash
wintag off
```

```bash
sudo apt remove wintag
```
