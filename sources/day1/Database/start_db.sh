#!/usr/bin/env bash
# MySQL 컨테이너 시작 + 스키마 초기화
set -e

CONTAINER="isolation-mysql"
PORT=3306
PASSWORD="demo"

# 이미 실행 중이면 중지 후 제거
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "[*] 기존 컨테이너 제거: ${CONTAINER}"
    docker rm -f "${CONTAINER}"
fi

echo "[*] MySQL 8.0 컨테이너 시작..."
docker run -d \
    --name "${CONTAINER}" \
    -e MYSQL_ROOT_PASSWORD="${PASSWORD}" \
    -e MYSQL_DATABASE=isolation_demo \
    -p "${PORT}:3306" \
    mysql:8.0 \
    --default-authentication-plugin=mysql_native_password

echo "[*] MySQL 초기화 대기 중..."
until docker exec "${CONTAINER}" mysqladmin ping -u root -p"${PASSWORD}" --silent 2>/dev/null; do
    printf '.'
    sleep 1
done
echo ""

echo "[*] 스키마 및 초기 데이터 적재..."
docker exec -i "${CONTAINER}" mysql -u root -p"${PASSWORD}" < setup.sql

echo ""
echo "[완료] 접속 정보:"
echo "  Host     : 127.0.0.1"
echo "  Port     : ${PORT}"
echo "  User     : root"
echo "  Password : ${PASSWORD}"
echo "  Database : isolation_demo"
echo ""
echo "  MySQL 클라이언트 접속:"
echo "  docker exec -it ${CONTAINER} mysql -u root -p${PASSWORD} isolation_demo"
echo ""
echo "  종료:"
echo "  docker rm -f ${CONTAINER}"
