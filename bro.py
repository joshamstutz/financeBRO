import discord
from discord.ext import commands, tasks
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_PATH, scope)
client = gspread.authorize(credentials)

spreadsheet = client.open('hackerfinance')
sheet = spreadsheet.sheet1

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Store users waiting for image uploads
waiting_for_image = {}


@bot.event
async def on_ready():
    await bot.tree.sync()
    # Start the cleanup task after the bot is ready and the event loop is running
    cleanup_waiting_list.start()
    print(f'financeBRO ready to crunch numbers')


async def get_last_image(channel):
    async for message in channel.history(limit=20):
        if message.attachments:
            for attachment in message.attachments:
                if attachment.filename.lower().endswith((".jpg", ".jpeg", ".png")):
                    return attachment.url
    return None


@bot.tree.command(name="add", description="Add data to the sheet and wait for a receipt image")
async def add(interaction: discord.Interaction, name: str, memo: str, date: str, amount: str):
    try:
        column_b = sheet.col_values(2)[2:]
        id_num = 3 + len(column_b)

        amount_value = float(amount.lstrip('+')) if amount.lstrip('+-').replace('.', '', 1).isdigit() else amount
        if not amount.startswith("+"):
            amount_value = -abs(amount_value)
        formatted_amount = f"${amount_value}" if amount_value >= 0 else f"-{abs(amount_value)}"

        sheet.update_cell(id_num, 1, id_num)
        sheet.update_cell(id_num, 2, name)
        sheet.update_cell(id_num, 3, memo)
        sheet.update_cell(id_num, 4, date)
        sheet.update_cell(id_num, 5, amount_value)
        sheet.update_cell(id_num, 7, "N")
        # Don't add any image URL yet - wait for user to upload one

        # Store the user's ID and record ID for future image upload
        waiting_for_image[interaction.user.id] = {
            "record_id": id_num,
            "expires_at": asyncio.get_event_loop().time() + 300  # 5 minutes timeout
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
    # Skip bot messages
    if message.author.bot:
        return

    # Check if the user is waiting for an image upload
    if message.author.id in waiting_for_image:
        record_info = waiting_for_image[message.author.id]

        # Check if the waiting period has expired
        if asyncio.get_event_loop().time() > record_info["expires_at"]:
            del waiting_for_image[message.author.id]
            return

        # Check if the message contains an image attachment
        if message.attachments:
            for attachment in message.attachments:
                if attachment.filename.lower().endswith((".jpg", ".jpeg", ".png")):
                    try:
                        # Update the spreadsheet with the image URL
                        record_id = record_info["record_id"]
                        sheet.update_cell(record_id, 13, attachment.url)

                        # Send confirmation message
                        await message.channel.send(f"receipt added to record **{record_id}**!")

                        # Remove the user from the waiting list
                        del waiting_for_image[message.author.id]
                        return
                    except Exception as e:
                        await message.channel.send(f"Error adding image to record: {e}")

    # Process commands
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
        # Find the cell with the record ID
        cell = sheet.find(str(record_id))

        if cell and cell.col == 1:
            # Get the status from column F (column 7)
            status = sheet.cell(cell.row, 7).value

            # Format the status message
            status_text = "Reimbursed" if status == "Y" else "Pending"
            status_emoji = "✅" if status == "Y" else "⏳"

            # Send the status information
            await interaction.response.send_message(
                f"**Status for record {record_id}**: {status_emoji} {status_text}\n"
            )
        else:
            await interaction.response.send_message(f"Record ID {record_id} not found.")
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}")


# Clean up expired waiting records every minute
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


# Run the bot
bot.run(DISCORD_BOT_TOKEN)