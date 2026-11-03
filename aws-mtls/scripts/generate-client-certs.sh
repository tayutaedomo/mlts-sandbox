#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
OUTPUT_DIR=${1:-"$PROJECT_DIR/certs/generated"}

# 秘密鍵を所有者だけが読める権限で生成する。既存の証明書は上書きしない。
umask 077
mkdir -p "$(dirname -- "$OUTPUT_DIR")"
if ! mkdir "$OUTPUT_DIR"; then
  printf '生成先を作成できません。既存のディレクトリを避けて指定してください: %s\n' "$OUTPUT_DIR" >&2
  exit 1
fi
OUTPUT_DIR=$(CDPATH= cd -- "$OUTPUT_DIR" && pwd)
mkdir "$OUTPUT_DIR/untrusted" "$OUTPUT_DIR/expired"

# openssl ca の発行記録は一時領域に作り、終了時に片付ける。
WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' 0
trap 'exit 1' HUP INT TERM
mkdir "$WORK_DIR/newcerts"
touch "$WORK_DIR/index.txt"
printf '1000\n' > "$WORK_DIR/serial"

create_ca() {
  # 自己署名ルート CA。Truststore に配置するのは ca.crt だけ。
  openssl req -x509 -newkey rsa:2048 -sha256 -days 365 -nodes \
    -keyout "$1/ca.key" -out "$1/ca.crt" -subj "/CN=$2" \
    -addext "basicConstraints=critical,CA:TRUE" \
    -addext "keyUsage=critical,keyCertSign,cRLSign" \
    -addext "subjectKeyIdentifier=hash" \
    -addext "authorityKeyIdentifier=keyid:always"
}

issue_client() {
  CLIENT_DIR=$1
  ISSUER_DIR=$2
  CLIENT_NAME=$3
  shift 3
  openssl req -new -newkey rsa:2048 -nodes \
    -keyout "$CLIENT_DIR/client.key" -out "$CLIENT_DIR/client.csr" -subj "/CN=$CLIENT_NAME"
  # ca コマンドで用途を設定し、有効期間の指定があればその期間で発行する。
  CA_WORK_DIR="$WORK_DIR" openssl ca -batch -notext -config "$SCRIPT_DIR/client-ca.cnf" \
    -cert "$ISSUER_DIR/ca.crt" -keyfile "$ISSUER_DIR/ca.key" \
    -in "$CLIENT_DIR/client.csr" -out "$CLIENT_DIR/client.crt" "$@"
}

create_ca "$OUTPUT_DIR" "AWS mTLS POC CA"
create_ca "$OUTPUT_DIR/untrusted" "AWS mTLS POC Untrusted CA"
issue_client "$OUTPUT_DIR" "$OUTPUT_DIR" "poc-client"
issue_client "$OUTPUT_DIR/untrusted" "$OUTPUT_DIR/untrusted" "poc-untrusted-client"
# 正常系と同じ CA で署名し、有効期限だけが拒否理由になる証明書を作る。
issue_client "$OUTPUT_DIR/expired" "$OUTPUT_DIR" "poc-expired-client" \
  -startdate 20200101000000Z -enddate 20200102000000Z

printf '検証用 CA と正常・非信頼 CA・期限切れのクライアント証明書を %s に生成しました\n' "$OUTPUT_DIR"
