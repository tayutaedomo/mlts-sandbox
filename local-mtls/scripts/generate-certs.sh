#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
OUTPUT_DIR=${1:-"$PROJECT_DIR/certs/generated"}

# 鍵ファイルを所有者だけが読み書きできる権限で作成する。
umask 077
mkdir -p "$OUTPUT_DIR"

# 自己署名ルート CA と、その CA の秘密鍵を作る。
# CA:TRUE と keyCertSign は、この証明書が他の証明書を発行する CA であることを示す。
openssl req -x509 -newkey rsa:2048 -sha256 -days 365 -nodes \
  -keyout "$OUTPUT_DIR/ca.key" \
  -out "$OUTPUT_DIR/ca.crt" \
  -subj "/CN=Local mTLS POC CA" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -addext "subjectKeyIdentifier=hash" \
  -addext "authorityKeyIdentifier=keyid:always"

# サーバー用の秘密鍵と CSR（証明書署名要求）を作る。
# CSR の内容を CA で署名し、サーバー証明書にする。
openssl req -new -newkey rsa:2048 -nodes \
  -keyout "$OUTPUT_DIR/server.key" \
  -out "$OUTPUT_DIR/server.csr" \
  -subj "/CN=localhost"

# 証明書の用途や接続先名などの拡張設定は server-ext.cnf から読み込む。
openssl x509 -req -sha256 -days 365 \
  -in "$OUTPUT_DIR/server.csr" \
  -CA "$OUTPUT_DIR/ca.crt" \
  -CAkey "$OUTPUT_DIR/ca.key" \
  -CAcreateserial \
  -extfile "$SCRIPT_DIR/server-ext.cnf" \
  -out "$OUTPUT_DIR/server.crt"

# クライアント用の秘密鍵と CSR を作り、サーバー証明書と同じ CA で署名する。
# 用途は client-ext.cnf でクライアント認証用に限定する。
openssl req -new -newkey rsa:2048 -nodes \
  -keyout "$OUTPUT_DIR/client.key" \
  -out "$OUTPUT_DIR/client.csr" \
  -subj "/CN=local-client"

openssl x509 -req -sha256 -days 365 \
  -in "$OUTPUT_DIR/client.csr" \
  -CA "$OUTPUT_DIR/ca.crt" \
  -CAkey "$OUTPUT_DIR/ca.key" \
  -CAserial "$OUTPUT_DIR/ca.srl" \
  -extfile "$SCRIPT_DIR/client-ext.cnf" \
  -out "$OUTPUT_DIR/client.crt"

# 秘密鍵のアクセス権を明示的に所有者のみへ制限する。
chmod 600 "$OUTPUT_DIR/ca.key" "$OUTPUT_DIR/server.key" "$OUTPUT_DIR/client.key"
printf 'CA・サーバー・クライアント証明書を %s に生成しました\n' "$OUTPUT_DIR"
