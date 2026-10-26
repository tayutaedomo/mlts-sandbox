#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
OUTPUT_DIR="$PROJECT_DIR/dist"

# 失敗時も既存の ZIP を維持し、一時領域は終了時に片付ける。
# 同じファイルシステム上で作り、最後の mv で生成済み ZIP を置き換える。
mkdir -p "$OUTPUT_DIR"
WORK_DIR=$(mktemp -d "$OUTPUT_DIR/.lambda-build.XXXXXX")
trap 'rm -rf "$WORK_DIR"' 0
trap 'exit 1' HUP INT TERM
PACKAGE_DIR="$WORK_DIR/package"

cd "$PROJECT_DIR"

# lock のバージョンとハッシュを使い、開発依存とプロジェクト自身を除外する。
uv export --locked --no-dev --no-emit-project \
  --output-file "$WORK_DIR/requirements.txt" > /dev/null

# Mac の .venv をコピーせず、Python 3.13・Linux arm64 用 wheel を取得する。
# manylinux2014 は glibc 2.17 以降向けで、Lambda の Python 3.13（AL2023）に対応する。
# 対応 wheel がない場合は失敗させ、Mac 上でのソースビルドへ切り替えない。
uv pip install \
  --requirements "$WORK_DIR/requirements.txt" \
  --target "$PACKAGE_DIR" \
  --python-version 3.13 \
  --python-platform aarch64-manylinux2014 \
  --only-binary :all: \
  --require-hashes --no-deps --link-mode copy

# アプリは .py ファイルだけを配置し、依存の CLI とキャッシュを除外する。
cp -R "$PROJECT_DIR/lambda_app" "$PACKAGE_DIR/"
find "$PACKAGE_DIR/lambda_app" -type f ! -name '*.py' -delete
rm -rf "$PACKAGE_DIR/bin"
find "$PACKAGE_DIR" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$PACKAGE_DIR" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

# ZIP 内の権限・日時・順序を揃え、同じビルド環境・内容なら同じハッシュにする。
# 0644 で Lambda がファイルを読めるようにし、日時は ZIP の最小日時に統一する。
find "$PACKAGE_DIR" -type f -exec chmod 644 {} +
TZ=UTC find "$PACKAGE_DIR" -type f -exec touch -t 198001010000 {} +

cd "$PACKAGE_DIR"
find . -type f > "$WORK_DIR/files.txt"
LC_ALL=C sort "$WORK_DIR/files.txt" > "$WORK_DIR/sorted-files.txt"
# -X は UID などの追加属性を省き、-@ はソートしたファイル一覧を読み込む。
TZ=UTC zip -q -X "$WORK_DIR/lambda.zip" -@ < "$WORK_DIR/sorted-files.txt"

mv -f "$WORK_DIR/lambda.zip" "$OUTPUT_DIR/lambda.zip"
printf 'Lambda 用 ZIP を %s に生成しました\n' "$OUTPUT_DIR/lambda.zip"
