import discord
from discord.ext import commands
from discord import app_commands
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

@bot.tree.command(name="add_record", description="Add data to the sheet")
async def add(interaction: discord.Interaction, name: str, memo: str, amount: str):
    try:
        column_b = sheet.col_values(2)[2:]
        row_number = 3 + len(column_b)

        sheet.update_cell(row_number, 2, name)
        sheet.update_cell(row_number, 3, memo)
        sheet.update_cell(row_number, 4, amount)

        await interaction.response.send_message(f'Added record:\nName: **{name}**\nMemo: **{memo}**\nAmount: **{amount}**')
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}")

@bot.tree.command(name="remove_recent", description="Remove the most recent entry from the sheet")
async def remove_recent(interaction: discord.Interaction):
    try:
        column_b = sheet.col_values(2)[2:]
        column_c = sheet.col_values(3)[2:]
        column_d = sheet.col_values(4)[2:]

        last_row = 2 + max(len(column_b), len(column_c), len(column_d))

        if last_row <= 2:
            await interaction.response.send_message("No entries to remove.")
            return

        sheet.update([["", "", ""]], f"B{last_row}:D{last_row}")

        await interaction.response.send_message("Removed the most recent entry from columns B, C, and D.")
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}")

@bot.tree.command(name="view_total", description="View total budget after expenses/credits from the sheet")
async def view(interaction: discord.Interaction):
    try:
        total = sheet.acell('H3').value
        await interaction.response.send_message(f'Total: **{total}**')
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}")

bot.run(DISCORD_BOT_TOKEN)