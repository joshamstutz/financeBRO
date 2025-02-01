import discord
from discord.ext import commands
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_PATH, scope)
client = gspread.authorize(credentials)

spreadsheet = client.open('hackerfinance')
sheet = spreadsheet.sheet1

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'financeBRO ready to crunch numbers')

@bot.tree.command(name="add", description="Add data to the sheet")
async def add(interaction: discord.Interaction, name: str, memo: str, amount: str):
    try:
        column_b = sheet.col_values(2)[2:]
        id_num = 3 + len(column_b)

        formatted_amount = f"-${amount[1:]}" if amount.startswith("-") else f"${amount}"

        sheet.update_cell(id_num, 1, id_num)
        sheet.update_cell(id_num, 2, name)
        sheet.update_cell(id_num, 3, memo)
        amount_value = float(amount) if amount.lstrip('-').replace('.', '', 1).isdigit() else amount
        sheet.update_cell(id_num, 4, amount_value)
        sheet.update_cell(id_num, 6, "N")
        sheet.update_cell(id_num, 7, "N")

        await interaction.response.send_message(f'Added record:\nID: **{id_num}**\nName: **{name}**\nMemo: **{memo}**\nAmount: **{formatted_amount}**')
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}")

@bot.tree.command(name="remove", description="Remove the most recent entry from the sheet")
async def remove_recent(interaction: discord.Interaction):
    try:
        column_b = sheet.col_values(2)[2:]
        column_c = sheet.col_values(3)[2:]
        column_d = sheet.col_values(4)[2:]

        last_row = 2 + max(len(column_b), len(column_c), len(column_d))

        if last_row <= 2:
            await interaction.response.send_message("No entries to remove.")
            return

        sheet.update(f"A{last_row}:G{last_row}", [["", "", "", "", "", "", ""]])
        await interaction.response.send_message("Removed the most recent entry.")
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}")

@bot.tree.command(name="budget", description="View total budget after expenses/credits from the sheet")
async def view(interaction: discord.Interaction):
    try:
        total = sheet.acell('K3').value
        await interaction.response.send_message(f'Total: **{total}**')
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}")

@bot.tree.command(name="authorize", description="Authorize a specific record")
async def authorize(interaction: discord.Interaction, id_num: int):
    try:
        sheet.update_cell(id_num, 6, "Y")
        await interaction.response.send_message(f"Record {id_num} authorized.")
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}")

@bot.tree.command(name="find", description="Find a record by name, memo, and amount")
async def find(interaction: discord.Interaction, name: str, memo: str, amount: str):
    try:
        records = sheet.get_all_values()[2:]
        for record in records:
            if len(record) >= 7 and record[1] == name and record[2] == memo and record[3] == amount:
                record_id = record[0]
                authorize_status = record[5]
                reimburse_status = record[6]
                await interaction.response.send_message(
                    f'Record found:\nID: **{record_id}**\nAuthorized: **{authorize_status}**\nReimbursed: **{reimburse_status}**'
                )
                return
        await interaction.response.send_message("No matching record found.")
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}")

bot.run(DISCORD_BOT_TOKEN)