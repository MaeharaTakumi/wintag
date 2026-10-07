#!/bin/bash
# 機能：wintag の .deb パッケージを作成する
# 入力：同じフォルダにある wintag / wintag-icon.py / wintag-source.py / wintag-watch.desktop / README.md
# 出力：${NAME}_${VERSION}_all.deb
set -e

# ===== パラメータ =====
NAME="wintag"                                        # パッケージ名
VERSION="2.1.0"                                      # バージョン
MAINTAINER="wintag <noreply@localhost>"              # 作成者（配布する場合は自分の名前・連絡先に変更）
DEPENDS="bash (>= 4.4), python3, x11-utils, x11-xserver-utils, xdotool, libx11-6, libxres1"  # 必須の依存パッケージ
RECOMMENDS="docker.io | docker-ce-cli, libnotify-bin" # 推奨（Docker 内のアプリの識別、起動失敗の通知に使用）
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"             # 元ファイルの場所
BUILD_DIR="${SRC_DIR}/build/${NAME}"                 # パッケージの組み立て場所

# 組み立て場所を初期化し、インストール先のフォルダ構成を作る
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}/DEBIAN" \
         "${BUILD_DIR}/usr/bin" \
         "${BUILD_DIR}/usr/lib/${NAME}" \
         "${BUILD_DIR}/etc/xdg/autostart" \
         "${BUILD_DIR}/usr/share/doc/${NAME}"

# 各ファイルを配置（実行ファイルは 755、それ以外は 644）
install -m 755 "${SRC_DIR}/wintag"               "${BUILD_DIR}/usr/bin/${NAME}"
install -m 755 "${SRC_DIR}/wintag-icon.py"       "${BUILD_DIR}/usr/lib/${NAME}/wintag-icon.py"
install -m 755 "${SRC_DIR}/wintag-source.py"     "${BUILD_DIR}/usr/lib/${NAME}/wintag-source.py"
install -m 644 "${SRC_DIR}/wintag-watch.desktop" "${BUILD_DIR}/etc/xdg/autostart/${NAME}-watch.desktop"

# 使い方をドキュメントとして同梱
install -m 644 "${SRC_DIR}/README.md"            "${BUILD_DIR}/usr/share/doc/${NAME}/README.md"

# /etc 以下は設定ファイル扱い（ユーザーが編集しても更新時に上書きしない）
echo "/etc/xdg/autostart/${NAME}-watch.desktop" > "${BUILD_DIR}/DEBIAN/conffiles"

# パッケージ情報
cat > "${BUILD_DIR}/DEBIAN/control" <<EOF
Package: ${NAME}
Version: ${VERSION}
Architecture: all
Maintainer: ${MAINTAINER}
Depends: ${DEPENDS}
Recommends: ${RECOMMENDS}
Section: utils
Priority: optional
Description: Tell GUI app windows apart by their source (host or Docker container)
 Watches new X11 windows and, for apps running in Docker containers, gives
 each container's windows its own name and icon on the GNOME Dock, so the
 same app from different containers is no longer grouped together.
 Apps can also be registered manually by clicking their window.
EOF

# .deb を作成
dpkg-deb --root-owner-group --build "${BUILD_DIR}" "${SRC_DIR}/${NAME}_${VERSION}_all.deb"
