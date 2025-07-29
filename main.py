import os
import asyncio
import time
import random
import string
from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import JSONResponse, PlainTextResponse, HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from discord.ext import commands
from discord import Embed, Intents, Interaction, ButtonStyle
from discord.ui import View, Button
import uvicorn
import secrets

app = FastAPI()
security = HTTPBasic()

app.mount("/static", StaticFiles(directory="static"), name="static")

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

def verify(credentials: HTTPBasicCredentials = Depends(security)):
    correct = os.getenv("PASSWORD")
    if not secrets.compare_digest(credentials.password, correct):
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(authorized: bool = Depends(verify)):
    html = """
    <html>
    <head>
      <link rel="stylesheet" href="/static/style.css">
      <title>Admin Panel</title>
    </head>
    <body>
      <h2>Used Keys</h2>
      <ul>
    """
    for key, info in data["used_keys"].items():
        html += f"<li>Key: {key} | Discord ID: {info['discord_id']} | IP: {info['ip']} <form method='post' action='/blacklist' style='display:inline'><input type='hidden' name='ip' value='{info['ip']}'><input type='hidden' name='discord_id' value='{info['discord_id']}'><button type='submit'>Blacklist</button></form></li>"
    html += """
      </ul>
    </body>
    </html>
    """
    return HTMLResponse(html)

@app.post("/blacklist")
async def blacklist(ip: str = Form(...), discord_id: str = Form(...), authorized: bool = Depends(verify)):
    data["blacklist"]["ips"].add(ip)
    data["blacklist"]["discord_ids"].add(discord_id)
    return RedirectResponse(url="/admin", status_code=303)

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

async def start_services():
    bot_task = asyncio.create_task(bot.start(os.getenv("DISCORD_BOT")))
    config = uvicorn.Config(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)), loop="asyncio")
    server = uvicorn.Server(config)
    api_task = asyncio.create_task(server.serve())
    await asyncio.gather(bot_task, api_task)

if __name__ == "__main__":
    asyncio.run(start_services())
