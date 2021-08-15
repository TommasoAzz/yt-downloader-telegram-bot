#!/usr/bin/env python

"""
Telegram bot for downloading YouTube videos and converting them to mp3 locally.

Usage:
Please read the README file.
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""

import logging
from typing import Tuple

from datetime import datetime
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from os import environ, path, remove as remove_file, rename as rename_file
from redis import Redis
from youtube_dl import YoutubeDL
from zipfile import ZipFile

"""
Logging stuff
"""
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)


"""
Configuration
"""
redis_host = environ.get("REDIS_HOST", default="localhost")
redis_pwd = int(environ.get("REDIS_PORT", default=6379))
redis_db = int(environ.get("REDIS_DB", default=0))


currently_downloading = {}


def log_download_finished(data: dict) -> None:
    """Logs information to the console when the file has (or not) finished downloading to let know the video is downloading/converting to mp3."""

    if data['status'] == 'downloading':
        if data['filename'] not in currently_downloading.keys() or not currently_downloading[data['filename']]:
            logger.info(
                f"Started downloading {data['filename'].replace('/usr/files/', '', 1)}."
            )
            currently_downloading[data['filename']] = True

    if data['status'] == 'finished':
        logger.info(
            f"Done downloading {data['filename'].replace('/usr/files/', '', 1)}, now converting to mp3."
        )
        currently_downloading[data['filename']] = False


ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '320',
    }],
    'outtmpl': '/usr/files/%(title)s.%(ext)s',
    'nooverwrites': True,
    'logger': logger,
    'keepvideo': False,
    'prefer_ffmpeg': True,
    'fixup': 'detect_or_warn',
    'noplaylist': True,
    'progress_hooks': [log_download_finished],
}

"""
Command handlers
"""


def alive_command(update: Update, context: CallbackContext) -> None:
    """Checks whether the bot is alive with command /alive. Replies if online."""

    user = update.effective_user
    update.message.reply_markdown_v2(
        fr'Hi {user.mention_markdown_v2()}, I\'m online\!'
    )


def help_command(update: Update, context: CallbackContext) -> None:
    """Sends a help message when the command /help is issued."""

    update.message.reply_text('Help!')


"""
Text message handlers
"""


def text_handler(update: Update, context: CallbackContext) -> None:
    """Handles a text message, searching for YouTube links."""

    logger.info(f"Parsing: {update.message.text}")
    if handle_message_text(update.message.text):
        update.message.reply_text(
            'The video will be submitted for downloading promptly.'
        )
    else:
        update.message.reply_text(
            f'\"{update.message.text}\" is not a YouTube link.'
        )


def txt_file_handler(update: Update, context: CallbackContext) -> None:
    """Handles a text file, searching for YouTube links in each row."""

    logger.info(f"Opening file: {update.message.document.file_name}")
    out_file_path = context.bot.get_file(update.message.document).download()
    num_possible_files, not_downloaded = handle_text_file(out_file_path)
    for nd in not_downloaded:
        update.message.reply_text(
            f'\"{nd}\" does not contain a YouTube url. It can\'t be processed.'
        )
    update.message.reply_text(
        f"{'All' if len(not_downloaded) == 0 else f'{num_possible_files-len(not_downloaded)}/{len(not_downloaded)}'} urls in the file can be processed and those will be downloaded soon."
    )
    remove_file(out_file_path)


def zip_file_handler(update: Update, context: CallbackContext) -> None:
    """Handles a zip file, searching for a file named _chat.txt inside of it and then continuing with text_file_handler."""

    logger.info(f"Opening file: {update.message.document.file_name}")
    out_file_path = context.bot.get_file(update.message.document).download()
    unique_timestamp = str(datetime.utcnow().timestamp())
    text_file_name = f"{unique_timestamp}.txt"
    with ZipFile(out_file_path, 'r') as zip_file:
        zip_file.extractall(unique_timestamp)
        rename_file(f'{unique_timestamp}/_chat.txt', text_file_name)
    num_possible_files, not_downloaded = handle_text_file(text_file_name)
    for nd in not_downloaded:
        update.message.reply_text(
            f'\"{nd}\" does not contain a YouTube url. It can\'t be processed.'
        )
    update.message.reply_text(
        f"{'All' if len(not_downloaded) == 0 else f'{len(not_downloaded)}/{num_possible_files-len(not_downloaded)}'} urls in the file can be processed and those will be downloaded soon."
    )
    remove_file(out_file_path)
    remove_file(text_file_name)


"""
Business logic handlers
"""


def handle_text_file(file_path: str) -> Tuple[int, list]:
    """Opens file with name file_path, reads its content and marks for downloading all available files, returns the number of file rows and the list of impossibile to download files."""

    file = open(file_path, mode='r', encoding="utf-8")
    rows = [r for r in file.read().split('\n')]
    file.close()
    not_yt_urls = []
    empty_rows = 0
    for r in rows:
        if len(r.strip()) == 0:
            empty_rows = empty_rows + 1
            continue
        if not handle_message_text(r):
            not_yt_urls.append(r)
    return len(rows) - empty_rows, not_yt_urls


def handle_message_text(text: str) -> bool:
    """If text contains a YouTube url, it sends it to the Redis subscriber to be downloaded via youtube-dl."""

    text = text.strip()
    if text.find('https://youtu.be/') != -1 or text.find('https://www.youtube.com/watch?v=') != -1:
        url_start_index = text.find('https://youtu.be/')
        if url_start_index != -1:
            url_end_index = url_start_index + 17 + 11
        else:
            url_start_index = text.find('https://www.youtube.com/watch?v=')
            url_end_index = url_start_index + 32 + 11
        redis_conn = Redis(host=redis_host, port=redis_pwd, db=redis_db)
        redis_conn.publish('yt-urls', text[url_start_index:url_end_index])
        redis_conn.close()
        return True
    else:
        return False


def download_video(redis_message: dict) -> None:
    """Parses redis_message and retrieves the url of the video to be downloaded."""

    url: str = redis_message['data'].decode()
    logger.info(f"Downloading video with url {url}")
    ydl = YoutubeDL(ydl_opts)
    try:
        ydl.download([url])
    except:
        logger.error(f"There was an error downloading video with url: {url}")


def main() -> None:
    # Retrieve the bot token
    token = environ.get("BOT_TOKEN", default="")
    if len(token) > 0 and token[0] == "\"" and token[len(token)-1] == "\"":
        token = token.replace("\"", "")

    # Setup the Redis subscriber
    redis_conn = Redis(host=redis_host, port=redis_pwd, db=redis_db)
    redis_pubsub = redis_conn.pubsub(ignore_subscribe_messages=True)
    redis_pubsub.subscribe(**{'yt-urls': download_video})
    redis_sub_thread = redis_pubsub.run_in_thread(sleep_time=5)

    # Loading the accepted usernames
    if path.exists('./accepted_usernames.txt'):
        with open('./accepted_usernames.txt', mode='r') as un_list:
            accepted_usernames = un_list.read().split('\n')
            # Skipping the first 2 rows since there are explanations.
            for un in accepted_usernames[2:]:
                if not un.startswith('@'):
                    un = '@' + un
    else:
        accepted_usernames = []

    # Create the user filter for the handlers
    user_filter = Filters.user(username=accepted_usernames)

    # Create the Updater and pass it your bot's token.
    updater = Updater(token)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("alive", alive_command, user_filter))
    dispatcher.add_handler(CommandHandler("help", help_command, user_filter))

    # on non command i.e text message - adds the message to a queue for downloading if message contains a YouTube url
    dispatcher.add_handler(
        MessageHandler(Filters.text & ~Filters.command &
                       user_filter, text_handler)
    )

    # on non command, non text i.e. .txt files
    dispatcher.add_handler(
        MessageHandler(Filters.document.txt & ~Filters.command &
                       user_filter, txt_file_handler)
    )

    # on non command, non text i.e. WhatsApp .zip files
    dispatcher.add_handler(
        MessageHandler(Filters.document.zip & ~Filters.command &
                       user_filter, zip_file_handler)
    )

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()

    redis_sub_thread.stop()


if __name__ == '__main__':
    main()
