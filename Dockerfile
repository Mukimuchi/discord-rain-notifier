FROM python:3.11-slim

WORKDIR /app

# 必要なパッケージ（tzdataなど）があればインストール（今回はデフォルトでOK）
# キャッシュを活かすためrequirements.txtを先にコピー
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# コード類をコピー
COPY . .

# 実行
CMD ["python", "-u", "main.py"]
