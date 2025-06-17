import datetime
import json
import time
import requests
import os

TELEGRAM_CONFIG = os.path.join(os.path.dirname(__file__), "telegram_config.json")



def load_subscribers():
    try:
        with open(TELEGRAM_CONFIG, "r") as file:
            data = json.load(file)
            return data.get("subscribers", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_config(user_id):
    data = {"subscribers": load_subscribers(), "bot_token": TELEGRAM_BOT_TOKEN}
    if user_id not in data["subscribers"]:
        data["subscribers"].append(user_id)
        with open(TELEGRAM_CONFIG, "w") as file:
            json.dump(data, file)


def load_token():
    try:
        with open(TELEGRAM_CONFIG, "r") as file:
            data = json.load(file)
            return data.get("bot_token", "")
    except (FileNotFoundError, json.JSONDecodeError):
        return ""


TELEGRAM_BOT_TOKEN = load_token()
TELEGRAM_API_URL = "https://api.telegram.org/bot{}/sendMessage".format(TELEGRAM_BOT_TOKEN)
TELEGRAM_UPDATE_URL = "https://api.telegram.org/bot{}/getUpdates".format(TELEGRAM_BOT_TOKEN)


def send_telegram_message(message, specific_user_id=None):
    if TELEGRAM_BOT_TOKEN == '':
        return

    subscribers = load_subscribers()
    try:
        if specific_user_id:
            requests.post(TELEGRAM_API_URL, data={"chat_id": specific_user_id, "text": message})
        else:
            for user_id in subscribers:
                requests.post(TELEGRAM_API_URL, data={"chat_id": user_id, "text": message})
    except requests.exceptions.RequestException as e:
        print(datetime.now() + f"Error while Telegram bot was sending message: {e}")



def reply_to_message(message, chat_id):
    if message == "/start":
        save_config(chat_id)
        send_telegram_message(
            "You have subscribed to benchmark notifications!",
                    specific_user_id=chat_id)

    elif message == "/stop":
        data = {"subscribers": load_subscribers(), "bot_token": TELEGRAM_BOT_TOKEN}
        if chat_id in data["subscribers"]:
            data["subscribers"].remove(chat_id)
            with open(TELEGRAM_CONFIG, "w") as file:
                json.dump(data, file)
            send_telegram_message(
                "You have unsubscribed from benchmark notifications!",
                        specific_user_id=chat_id)

    else:
        send_telegram_message(
            "Unknown command.\n Use /start to subscribe and /stop to unsubscribe.",
                    specific_user_id=chat_id)


def listen_for_messages():
    if TELEGRAM_BOT_TOKEN == '':
        return

    last_update_id = None
    while True:
        try:
            params = {"offset": last_update_id + 1} if last_update_id else {}
            response = requests.get(TELEGRAM_UPDATE_URL, params=params).json()
            if "result" in response:
                for update in response["result"]:
                    last_update_id = update["update_id"]
                    if "message" in update and "text" in update["message"]:
                        reply_to_message(update["message"]["text"],
                                         update["message"]["chat"]["id"])

        except requests.exceptions.RequestException as e:
            print(f"Errore nella ricezione degli aggiornamenti: {e}")
        time.sleep(5)
