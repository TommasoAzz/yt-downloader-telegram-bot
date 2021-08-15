# yt-downloader-telegram-bot
Telegram bot that downloads videos from YouTube via messages and stores them in the device serving the bot.
It accepts:

- messages containing YouTube links in the two available formats (https://youtu.be/{videoId} and https://youtube.com/watch?v={videoId});
- `.txt` files containing links (max. 1 per row);
- `.zip` files containing a `_chat.txt` files (i.e. WhatsApp log .zip files).

When a text message or a row in the `.txt` file cannot be parsed an error message is sent to the user in the chat.

Not everyone can use the bot!
All users allowed to make use of the bot must be explictly listed on the `accepted_usernames.txt` file.

## Requirements
Just Docker (tested with **Docker version 20.10.8, build 3967b7d** on Raspberry Pi 4).

Otherwise one could run it on its local machine but would require both **Python 3+** and **Redis** installed.

## Setup and run
1. Create an environment file called `.env` and store the following variables:
    - BOT_TOKEN=`your-token`
    - REDIS_HOST=yt_downloader_redis
    - REDIS_PORT=6379
    - REDIS_DB=0
    
    Instead of `your-token` insert a valid Telegram bot token generated via the [BotFather](https://core.telegram.org/bots#6-botfather).
    For what concerns REDIS_HOST, REDIS_PORT, REDIS_DB, one could leave them as is if using Docker and okay with the default values.
2. Add all the Telegram users allowed to use the bot inside the file `accepted_usernames.txt`.
3. Run the bot via `docker-compose up`.
4. To stop the service, use `CTRL+C` or `docker-compose down` in another terminal window.
