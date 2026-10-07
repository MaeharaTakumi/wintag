#!/bin/bash
# 機能：wintag の .deb パッケージを作成する
# 入力：同じフォルダにある wintag / wintag-source.py / README.md
# 出力：${NAME}_${VERSION}_all.deb
set -e

# ===== パラメータ =====
NAME="wintag"                                        # パッケージ名
VERSION="2.2.0"                                      # バージョン
MAINTAINER="wintag <noreply@localhost>"              # 作成者（配布する場合は自分の名前・連絡先に変更）
DEPENDS="bash (>= 4.4), python3, x11-utils, libx11-6, libxres1"  # 必須の依存パッケージ
RECOMMENDS="docker.io | docker-ce-cli"               # 推奨（コンテナ名の取得に使用。ない場合はコンテナ ID を表示）
OLD_AUTOSTART="/etc/xdg/autostart/${NAME}-watch.desktop"  # 2.1.0 以前が全ユーザー向けに置いた自動起動設定（更新時に削除）
OLD_AUTOSTART_UNTIL="2.2.0~"                         # この版より前から更新するときに OLD_AUTOSTART を削除
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"             # 元ファイルの場所
BUILD_DIR="${SRC_DIR}/build/${NAME}"                 # パッケージの組み立て場所

# 組み立て場所を初期化し、インストール先のフォルダ構成を作る
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}/DEBIAN" \
         "${BUILD_DIR}/usr/bin" \
         "${BUILD_DIR}/usr/lib/${NAME}" \
         "${BUILD_DIR}/usr/share/doc/${NAME}"

# 各ファイルを配置（実行ファイルは 755、それ以外は 644）
install -m 755 "${SRC_DIR}/wintag"               "${BUILD_DIR}/usr/bin/${NAME}"
install -m 755 "${SRC_DIR}/wintag-source.py"     "${BUILD_DIR}/usr/lib/${NAME}/wintag-source.py"

# 使い方をドキュメントとして同梱
install -m 644 "${SRC_DIR}/README.md"            "${BUILD_DIR}/usr/share/doc/${NAME}/README.md"

# 監視は既定でオフ（wintag on でユーザーごとに有効化）。旧版の全ユーザー向け自動起動設定を、更新時に削除する
for script in preinst postinst postrm; do
  cat > "${BUILD_DIR}/DEBIAN/${script}" <<EOF
#!/bin/sh
set -e
dpkg-maintscript-helper rm_conffile ${OLD_AUTOSTART} ${OLD_AUTOSTART_UNTIL} ${NAME} -- "\$@"
EOF
  chmod 755 "${BUILD_DIR}/DEBIAN/${script}"
done

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
Description: Tell GUI app windows apart by their source Docker container
 When enabled with "wintag on", watches new X11 windows and prefixes the
 title of each window from a Docker container with the container name, so
 windows of the same app grouped under one GNOME Dock icon can be told apart.
EOF

# .deb を作成
dpkg-deb --root-owner-group --build "${BUILD_DIR}" "${SRC_DIR}/${NAME}_${VERSION}_all.deb"
