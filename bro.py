import discord
from discord.ext import commands
from discord import app_commands
import gspread
from oauth2client.service_account import ServiceAccountCredentials

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name(
    "/Users/joshamstutz/Downloads/financebro-449105-fc40e9fd863a.json", scope)
client = gspread.authorize(credentials)

spreadsheet = client.open('hackerfinance')
sheet = spreadsheet.sheet1

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)


# commands
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'Logged in as {bot.user}')


# adds spreadsheet record
@bot.tree.command(name="add", description="Add data to the sheet")
async def add(interaction: discord.Interaction, data: str):
    # splits name, memo, and amount
    try:
        name, memo, amount = data.split(',')

        column_b = sheet.col_values(2)[2:]

        # first empty row in column B
        row_number = 3 + len(column_b)  # adding 3 since B3 is first available

        # Insert data into the first available row in columns B, C, and D
        sheet.update_cell(row_number, 2, name)  # column B
        sheet.update_cell(row_number, 3, memo)  # column C
        sheet.update_cell(row_number, 4, amount)  # column D

        await interaction.response.send_message(f'Added data: Name: {name}, Memo: {memo}, Amount: {amount}')
    except ValueError:
        await interaction.response.send_message("Please provide the data in the correct format: name,memo,amount")


# views total (probably gonna be private)
@bot.tree.command(name="view", description="View data from the sheet")
async def view(interaction: discord.Interaction):
    try:
        # H3 is "total" cell
        total = sheet.acell('H3').value
        await interaction.response.send_message(f'Total: {total}')
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}")


# bot token
bot.run("MTMzMzU5Njc5MzA3Nzg5MTIwNQ.G-MGFg.0fa3i6Dke_dzxYu3AEaIqBdtVUcIaaBSlhGS20")
