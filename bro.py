import discord
from discord.ext import commands, tasks
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from dotenv import load_dotenv
import asyncio
import requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_PATH, scope)

client = gspread.authorize(credentials)
spreadsheet = client.open('hackerfinance')
sheet = spreadsheet.sheet1

drive_service = build('drive', 'v3', credentials=credentials)

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

waiting_for_image = {}


@bot.event
async def on_ready():
    await bot.tree.sync()
    cleanup_waiting_list.start()
    print(f'financeBRO ready to crunch numbers')


async def upload_to_drive(image_url, filename):
    response = requests.get(image_url)
    if response.status_code == 200:
        file_path = f"./{filename}"
        with open(file_path, "wb") as file:
            file.write(response.content)

        try:
            file_metadata = {
                'name': filename,
                'parents': [GOOGLE_DRIVE_FOLDER_ID]
            }

            media = MediaFileUpload(file_path, resumable=True)
            file = drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,webViewLink'
            ).execute()

            drive_service.permissions().create(
                fileId=file.get('id'),
                body={'type': 'anyone', 'role': 'reader'},
                fields='id'
            ).execute()

            os.remove(file_path)

            return file.get('webViewLink')
        except Exception as e:
            print(f"Drive upload error: {e}")
            if os.path.exists(file_path):
                os.remove(file_path)
            return None
    return None


@bot.tree.command(name="add", description="Add data to the sheet and wait for a receipt image")
async def add(interaction: discord.Interaction, name: str, memo: str, date: str, amount: str):
    try:
        column_b = sheet.col_values(2)[2:]
        id_num = 3 + len(column_b)

        amount_value = float(amount.lstrip('+')) if amount.lstrip('+-').replace('.', '', 1).isdigit() else amount
        if not amount.startswith("+"):
            amount_value = -abs(amount_value)
        formatted_amount = f"${amount_value}" if amount_value >= 0 else f"-${abs(amount_value)}"

        sheet.update_cell(id_num, 1, id_num)
        sheet.update_cell(id_num, 2, name)
        sheet.update_cell(id_num, 3, memo)
        sheet.update_cell(id_num, 4, date)
        sheet.update_cell(id_num, 5, amount_value)
        sheet.update_cell(id_num, 7, "N")

        waiting_for_image[interaction.user.id] = {
            "record_id": id_num,
            "expires_at": asyncio.get_event_loop().time() + 300
        }

        await interaction.response.send_message(
            f'added record:\n'
            f'id: **{id_num}**\n'
            f'payee: **{name}**\n'
            f'memo: **{memo}**\n'
            f'date purchased: **{date}**\n'
            f'amount: **{formatted_amount}**\n \n \n'
            f'**upload a receipt image to attach it to this record**'
        )
    except Exception as e:
        await interaction.response.send_message(f"an error occurred: {e}")


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.author.id in waiting_for_image:
        record_info = waiting_for_image[message.author.id]

        if asyncio.get_event_loop().time() > record_info["expires_at"]:
            del waiting_for_image[message.author.id]
            return

        if message.attachments:
            for attachment in message.attachments:
                if attachment.filename.lower().endswith((".jpg", ".jpeg", ".png")):
                    processing_msg = await message.channel.send("Uploading receipt to Google Drive...")

                    try:
                        drive_link = await upload_to_drive(attachment.url, attachment.filename)

                        if drive_link:
                            record_id = record_info["record_id"]
                            sheet.update_cell(record_id, 13, drive_link)

                            await processing_msg.edit(
                                content=f"Receipt uploaded to Google Drive and added to record **{record_id}**!\n{drive_link}")
                        else:
                            await processing_msg.edit(content="Error uploading receipt to Google Drive.")

                        del waiting_for_image[message.author.id]
                        return
                    except Exception as e:
                        await processing_msg.edit(content=f"Error: {str(e)}")
                        del waiting_for_image[message.author.id]
                        return

    await bot.process_commands(message)


@bot.tree.command(name="reimburse", description="mark a record as reimbursed")
async def reimburse(interaction: discord.Interaction, record_id: int):
    try:
        cell = sheet.find(str(record_id))
        if cell and cell.col == 1:
            sheet.update_cell(cell.row, 7, "Y")
            await interaction.response.send_message(f"record {record_id} marked as reimbursed.")
        else:
            await interaction.response.send_message("id not found.")
    except Exception as e:
        await interaction.response.send_message(f"an error occurred: {e}")


@bot.tree.command(name="status", description="Check the reimbursement status of a record")
async def status(interaction: discord.Interaction, record_id: int):
    try:
        cell = sheet.find(str(record_id))

        if cell and cell.col == 1:
            status = sheet.cell(cell.row, 7).value

            status_text = "Reimbursed" if status == "Y" else "Pending"
            status_emoji = "✅" if status == "Y" else "⏳"

            await interaction.response.send_message(
                f"**Status for record {record_id}**: {status_emoji} {status_text}\n"
            )
        else:
            await interaction.response.send_message(f"Record ID {record_id} not found.")
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}")


@tasks.loop(minutes=1)
async def cleanup_waiting_list():
    current_time = asyncio.get_event_loop().time()
    expired_users = [user_id for user_id, info in waiting_for_image.items()
                     if current_time > info["expires_at"]]

    for user_id in expired_users:
        del waiting_for_image[user_id]


@cleanup_waiting_list.before_loop
async def before_cleanup():
    await bot.wait_until_ready()


bot.run(DISCORD_BOT_TOKEN)