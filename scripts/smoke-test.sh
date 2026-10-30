#!/usr/bin/env bash
# End-to-end check of a running stack: replicas, product creation, media, catalog page.
# Usage: scripts/smoke-test.sh   (CHECK_FAILOVER=1 also stops one api replica)
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:${HTTP_PORT:-8085}}"
TOKEN="$(grep '^INTERNAL_API_TOKEN=' .env | cut -d= -f2-)"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }
json_field() { python3 -c "import json,sys; print(json.load(sys.stdin)[\"$1\"])"; }
http_code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

echo "Waiting for API..."
for _ in $(seq 60); do
  curl -fsS "$BASE_URL/api/health" >/dev/null 2>&1 && break
  sleep 2
done
curl -fsS "$BASE_URL/api/health" >/dev/null || fail "API is not healthy"

for service in api web; do
  count="$(docker compose ps -q "$service" | wc -l)"
  [ "$count" -ge 2 ] || fail "$service has $count replica(s), expected 2+"
done
echo "OK: api and web run in 2+ replicas"

python3 -c "import base64; open('$WORK_DIR/p.png','wb').write(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='))"
TITLE="Тестовый товар $RANDOM"
KEY="smoke-$(date +%s)-$RANDOM"

create() {
  curl -fsS -X POST "$BASE_URL/api/products" \
    -H "X-Internal-Token: $TOKEN" -H "Idempotency-Key: $KEY" \
    -F "title=$TITLE" -F "image=@$WORK_DIR/p.png;type=image/png"
}
first="$(create)"
second="$(create)"
[ "$(echo "$first" | json_field id)" = "$(echo "$second" | json_field id)" ] \
  || fail "same Idempotency-Key created two products"
echo "OK: product created once for a repeated request"

image_url="$(echo "$first" | json_field image_url)"
curl -fsS "$BASE_URL$image_url" -o "$WORK_DIR/got.png"
cmp -s "$WORK_DIR/p.png" "$WORK_DIR/got.png" || fail "image from /media differs from uploaded"
echo "OK: image is served from MinIO"

page="$(curl -fsS "$BASE_URL/")"
grep -q "Каталог" <<<"$page" || fail "catalog page has no title"
grep -q "$TITLE" <<<"$page" || fail "new product is not on the catalog page"
echo "OK: catalog page lists the new product"

[ "$(http_code -X POST "$BASE_URL/api/products" -F title=x -F "image=@$WORK_DIR/p.png")" = 401 ] \
  || fail "product creation without token is allowed"
[ "$(http_code "$BASE_URL/media/")" = 404 ] || fail "bucket listing is exposed"
echo "OK: write access and bucket listing are closed"

since="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
sleep 1
for _ in $(seq 20); do curl -fsS "$BASE_URL/api/products?limit=1" >/dev/null; done
for container in $(docker compose ps -q api); do
  served="$(docker logs --since "$since" "$container" 2>&1 | grep -c 'GET /api/products?limit=1' || true)"
  [ "$served" -ge 1 ] || fail "api replica ${container:0:12} received no requests from nginx"
  echo "OK: api replica ${container:0:12} served $served of 20 requests"
done

if [ "${CHECK_FAILOVER:-0}" = 1 ]; then
  docker stop "$(docker compose ps -q api | head -n1)" >/dev/null
  for _ in $(seq 10); do
    curl -fsS "$BASE_URL/api/products" >/dev/null || fail "catalog failed after stopping one api replica"
  done
  echo "OK: catalog keeps working with one api replica stopped"
fi

echo "All smoke checks passed"
