FROM python:3.9.6-alpine

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY requirements.txt /usr/src/app/

RUN pip3 install --no-cache-dir -r requirements.txt

RUN apk add ffmpeg

COPY . /usr/src/app

RUN mkdir -p /usr/files

ENTRYPOINT ["python3"]

CMD ["-m", "yt_downloader_telegram_bot"]