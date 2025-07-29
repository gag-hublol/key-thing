import os
import asyncio
import time
import random
import string
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from discord.ext import commands
from discord import Embed, Intents, Interaction, ButtonStyle
from discord.ui import View, Button
import uvicorn

app = FastAPI()

data = {
    "keys": {},
    "used_keys": {},
    "blacklist": {"ips": set(), "discord_ids": set()}
}

@app.middleware("http")
async def block_all(request: Request, call_next):
    ip = request.client.host
    if ip in data["blacklist"]["ips"]:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)

@app.post("/validate")
async def validate_key(request: Request):
    body = await request.json()
    key = body.get("key")
    ip = request.client.host
    if key in data["keys"]:
        discord_id, ts = data["keys"][key]
        if time.time() - ts <= 86400:
            data["used_keys"][key] = {"discord_id": discord_id, "ip": ip, "used_at": time.time()}
            return {"valid": True}
    return {"valid": False}

@app.get("/robots.txt")
async def robots():
    return PlainTextResponse("User-agent: *\nDisallow: /", status_code=200)

intents = Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    channel = None
    for guild in bot.guilds:
        for ch in guild.text_channels:
            if ch.name == "general":
                channel = ch
                break
    if channel:
        embed = Embed(title="Key Generator", description="Press the button to receive your key.", color=0x00ff00)
        view = View()

        async def callback(interaction: Interaction):
            user_id = str(interaction.user.id)
            if user_id in data["blacklist"]["discord_ids"]:
                await interaction.response.send_message("You're blacklisted.", ephemeral=True)
                return
            key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
            data["keys"][key] = (user_id, time.time())
            try:
                await interaction.user.send(f"Your 24-hour key:\n`{key}`")
                await interaction.response.send_message("Check your DMs.", ephemeral=True)
            except:
                await interaction.response.send_message("DMs are off.", ephemeral=True)

        button = Button(label="Get Key", style=ButtonStyle.success)
        button.callback = callback
        view.add_item(button)
        await channel.send(embed=embed, view=view)

async def start_bot():
    await bot.start(os.getenv("DISCORD_BOT"))

def run():
    loop = asyncio.get_event_loop()
    loop.create_task(start_bot())
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

if __name__ == "__main__":
    run()
