## Telegram client api bot with chatgpt and other models

This bot utilize telegram client api, not a bot api, to response on messages
from user's account.

It monitoring all chat in allowed chats list. The dialogs in different chats
acts as separated dialogs. Only one dialog per chat for user allowed. You can
have active dialogs in any allowed chat for same user either multiple dialogs in single
chat for different users.

To start new dialog – write `/chat <your message>` in any monitored chat.

To proceed dialog write messages as replies to chatgpt responses.

To delete old dialog and start a new one, write message with `/chat` cmd again.

### Install
You need `python3` with **venv** installed

* `git clone <this respo>`
* `cd <repo folder>`
* `python3 -m venv venv`
* `source venv/bin/activate`
* `pip3 install -r requirements.txt`
* `cp .env.example .env`

Next you need replace example config credentials with your own.
* Go to https://platform.openai.com and register an account or skip this step if you have one.
* Create new Openai API key https://platform.openai.com/account/api-keys and 
copy it to `OPENAI_API_KEY` variable in `.env` file
* For TG api credentials go to https://my.telegram.org/auth?to=apps login by phone and get your api id and hash, then fill vars in `.env` file.

Next you should provide chat id's where bot allowed to. If you don't know them, you can invert condition where it check it in `handler`,
example:
```python
if chat_id in channels:
```
to
```python
if chat_id not in channels:
```
Now bot will monitor all your chats and groups. Write something in chat that you want to add. And check log,
you message will appear in format `chat: <chat_name> chat_id: <chat_id> sender: <sender_id> <first_name> <last_name> text: <you message>`
You interested in `chat_id` value and `<sender_id>`, `sender_id` if this is your message, will be `SELF_ID` value, fill it.
`chat_id` is id of chat you interested to, it can be negative value or positive. Do this for every chat that you want to monitor. 
The ids should be separated with comma and following space `, `.
DO NOT forget to revert your changes in code, remove `not` condition to let bot monitor only allowed chats.

Thats all.

### Notes:
OpenAI models can be overloaded sometimes, they can generate responses slowly or fractured.
You can check openai services status page.
Also TG API can limit you requests with timeout cooldown, ~300 seconds if your bot using intensively. You can set `CHUNK_AMOUNT`
parameter to higher values to lower bot requests rate to TG API.
