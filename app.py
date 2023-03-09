import logging
import os
from dataclasses import dataclass
from typing import List, Dict

import openai
import telethon
import tiktoken
from dotenv import load_dotenv
from telethon import TelegramClient, events

logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
                    level=logging.WARNING)

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
chats_env = os.getenv('ALLOWED_CHATS')
channels = [int(_chat) for _chat in chats_env.split(', ')]
self_id = int(os.getenv('SELF_ID'))
chunk_amount = int(os.getenv('CHUNK_AMOUNT'))  # post every x chunks to avoid Telegram flood limit error
client = TelegramClient('openai', api_id, api_hash)

roles = ['system', 'user', 'assistant']
models = {
    'chatgpt': 'gpt-3.5-turbo',
    'cushman': 'code-cushman-001',
    'codex': 'code-davinci-002'
}


@dataclass
class Message:
    message_id: int
    role: str
    content: str


@dataclass
class Dialog:
    user_id: int
    start_message_id: int
    chat: bool
    model: str
    messages: List[Message]


active_dialogs: Dict[str, Dialog] = dict()


async def is_reply_to_me(chat, message):
    async for replied_msg in client.iter_messages(chat, ids=message.reply_to_msg_id):
        if replied_msg.sender_id == self_id:
            return True
        else:
            return False


async def append_message(chat, msg, text: str):
    if msg is None:
        raise ValueError('msg can\'t be None.')
    try:
        m = await client.edit_message(chat, msg, text=text)
        return m
    except ValueError as e:
        print(e)
    except telethon.errors.rpcerrorlist.MessageNotModifiedError as e:
        print(e)
    except Exception as e:
        print(e)
    return msg


@client.on(events.NewMessage())
async def handler(event):
    chat = await event.get_chat()
    sender = await event.get_sender()
    chat_id = event.chat_id
    sender_id = event.sender_id
    text: str = event.raw_text
    if chat_id in channels:
        print('chat:', chat.title, 'chat_id:', chat_id, 'sender:', sender_id, sender.first_name, sender.last_name,
              sender.username,
              'text:', text)

        key = str(chat_id) + str(sender_id)
        message = event.message
        if event.message.is_reply and key in active_dialogs and await is_reply_to_me(chat, message):
            dialog = active_dialogs[key]
            print("Continue dialog", key, 'type', dialog.model)
            msg = Message(
                message_id=event.message.id,
                role=roles[1],
                content=text
            )
            if dialog.chat:
                dialog.messages.append(msg)
                r_count = 0
                response = ''
                m = None
                async for fract_response in openai_api_stream(dialog.model, dialog):
                    if r_count == 0:
                        response += fract_response
                        # first response of chatgpt is '\n\n', telethon and TG parse this as incorrect msg, so there is
                        # a placeholder
                        m = await event.reply("ChatGPT:")
                    else:
                        response += fract_response
                        if r_count % chunk_amount == 0:
                            m = await append_message(chat, m, response)
                    print(response)
                    r_count += 1
                await append_message(chat, m, response)
                msg = Message(
                    message_id=m.id,
                    role=roles[2],
                    content=response
                )
                dialog.messages.append(msg)
            else:
                msg = Message(
                    message_id=event.message.id,
                    role=roles[1],
                    content=text
                )
                dialog.messages.append(msg)
                response = await openai_api(dialog.model, dialog)
                await event.reply(response)

        if '/chat' in text:
            if key in active_dialogs:
                active_dialogs.pop(key)
            prompt = text.split('/chat')[-1].strip()
            model = 'chatgpt'
            print("Start new dialog, type", model)
            if len(prompt) > 5:
                msg = Message(
                    message_id=event.message.id,
                    role=roles[0],
                    content=prompt
                )
                dialog = Dialog(
                    user_id=sender_id,
                    start_message_id=event.message.id,
                    chat=True,
                    model=model,
                    messages=[msg]
                )
                active_dialogs[key] = dialog
                messages = [{"role": m.role, "content": m.content} for m in dialog.messages]
                if num_tokens_from_messages(messages) > 1000:
                    await event.reply("Prompt too long. Please start new chat with /chat")
                else:
                    r_count = 0
                    response = ''
                    m = None
                    async for fract_response in openai_api_stream(model, dialog):
                        if r_count == 0:
                            response += fract_response
                            m = await event.reply("ChatGPT:")
                        else:
                            response += fract_response
                            if r_count % chunk_amount == 0:
                                m = await append_message(chat, m, response)
                        r_count += 1
                    await append_message(chat, m, response)
                    print(response)

                    msg = Message(
                        message_id=m.id,
                        role=roles[2],
                        content=response
                    )
                    dialog.messages.append(msg)

        if '/codex' in text:
            if key in active_dialogs:
                active_dialogs.pop(key)
            prompt = text.split('/codex')[-1].strip()
            model = 'codex'
            print("Start new dialog, type", model)
            msg = Message(
                message_id=event.message.id,
                role=roles[0],
                content=prompt
            )
            dialog = Dialog(
                user_id=sender_id,
                start_message_id=event.message.id,
                chat=False,
                model=model,
                messages=[msg]
            )
            active_dialogs[key] = dialog
            response = await openai_api(model, dialog)
            await event.reply(response)


async def openai_api(model, dialog: Dialog, temp=0.6):
    try:
        if model == 'chatgpt':
            response = openai.ChatCompletion.create(
                model=models[model],
                messages=[{"role": m.role, "content": m.content} for m in dialog.messages],
            )
            print("[api] finish_reason:", response['choices'][0]['finish_reason'], '| usage',
                  response['usage']['total_tokens'])
            reply = response['choices'][0]['message']['content']
        elif model == 'codex':
            response = openai.Completion.create(
                model=models[model],
                prompt=dialog.messages[-1].content,
                temperature=temp,
            )
            print("[api] finish_reason:", response['choices'][0]['finish_reason'], '| usage',
                  response['usage']['total_tokens'])
            reply = response['choices'][0]['text']
        else:
            reply = None
    except openai.error.RateLimitError as e:
        reply = e.user_message
    return reply


async def openai_api_stream(model, dialog: Dialog, temp=0.6):
    if model == 'chatgpt':
        response = openai.ChatCompletion.create(
            model=models[model],
            messages=[{"role": m.role, "content": m.content} for m in dialog.messages],
            stream=True
        )
        for r in response:
            if 'content' in r['choices'][0]['delta']:
                reply = r['choices'][0]['delta']['content']
            else:
                reply = ''
            yield reply


async def get_thread(message, chat):
    msg = message
    thread = dict()
    while msg.reply_to:
        async for _m in client.iter_messages(chat, ids=msg.reply_to_msg_id):
            thread[_m.from_id.user_id] = _m.message
            msg = _m
            print(_m.message)


def num_tokens_from_messages(messages, model="gpt-3.5-turbo"):
    """Returns the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    if model == "gpt-3.5-turbo":  # note: future models may deviate from this
        num_tokens = 0
        for message in messages:
            num_tokens += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
            for key, value in message.items():
                num_tokens += len(encoding.encode(value))
                if key == "name":  # if there's a name, the role is omitted
                    num_tokens += -1  # role is always required and always 1 token
        num_tokens += 2  # every reply is primed with <im_start>assistant
        return num_tokens
    else:
        raise NotImplementedError(f"""num_tokens_from_messages() is not presently implemented for model {model}.
See https://github.com/openai/openai-python/blob/main/chatml.md 
for information on how messages are converted to tokens.""")


if __name__ == '__main__':
    client.start()
    client.run_until_disconnected()
