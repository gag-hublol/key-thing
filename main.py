import uvicorn, discord, asyncio, json, random, string, os
from fastapi import FastAPI, Request
from pydantic import BaseModel
from datetime import datetime, timedelta
from fastapi.responses import JSONResponse, PlainTextResponse
import os, secrets, time, uvicorn
from fastapi import FastAPI, Request, Form, Depends, status
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse
from discord.ext import commands
from discord import Intents, Embed, ButtonStyle, Interaction
from discord.ui import View, Button
import discord
import asyncio

app = FastAPI()
security = HTTPBasic()
intents = Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

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

@app.get("/robots.txt")
async def deny_all_robots():
    return HTMLResponse(content="User-agent: *\nDisallow: /", status_code=401)

@app.post("/validate")
async def validate_key(request: Request):
    body = await request.json()
    key = body.get("key")
    ip = request.client.host
    if ip in data["blacklist"]["ips"]:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    if key in data["keys"]:
        discord_id, ts = data["keys"][key]
        if time.time() - ts <= 86400:
            data["used_keys"][key] = {"discord_id": discord_id, "ip": ip, "used_at": time.time()}
            return {"valid": True}
    return {"valid": False}

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.password != os.environ["PASSWORD"]:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    html = "<h2>Used Keys</h2><ul>"
    for k, v in data["used_keys"].items():
        html += f"<li>Key: {k} | Discord ID: {v['discord_id']} | IP: {v['ip']} <form method='post' action='/blacklist'><input type='hidden' name='ip' value='{v['ip']}'><input type='hidden' name='discord_id' value='{v['discord_id']}'><button type='submit'>Blacklist</button></form></li>"
    html += "</ul>"
    return html

@app.post("/blacklist")
async def blacklist(ip: str = Form(...), discord_id: str = Form(...), credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.password != os.environ["PASSWORD"]:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    data["blacklist"]["ips"].add(ip)
    data["blacklist"]["discord_ids"].add(discord_id)
    return RedirectResponse(url="/admin", status_code=303)

@bot.event
async def on_ready():
    channel = discord.utils.get(bot.get_all_channels(), name="general")
    if channel:
        embed = Embed(title="Key Generator", description="Press the button to receive your key.", color=0x00ff00)
        view = View()
        async def callback(interaction: Interaction):
            user_id = str(interaction.user.id)
            if user_id in data["blacklist"]["discord_ids"]:
                await interaction.response.send_message("You are not allowed to generate keys.", ephemeral=True)
                return
            key = ''.join(secrets.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(16))
            data["keys"][key] = (user_id, time.time())
            try:
                await interaction.user.send(f"Your 24-hour access key:\n`{key}`")
                await interaction.response.send_message("Check your DMs for the key.", ephemeral=True)
            except:
                await interaction.response.send_message("Unable to send you a DM. Please enable DMs.", ephemeral=True)

        button = Button(label="Get Key", style=ButtonStyle.success)
        button.callback = callback
        view.add_item(button)
        await channel.send(embed=embed, view=view)

if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: uvicorn.run(app, host="0.0.0.0", port=8000)).start()
    bot.run(os.environ["DISCORD_BOT"])
app = FastAPI()
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Bot(intents=intents)

DB_FILE = "keys.json"

class KeyData(BaseModel):
    key: str
    expires: str

def load_keys():
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_keys(keys):
    with open(DB_FILE, "w") as f:
        json.dump(keys, f)

@app.post("/api/save_key")
async def save_key_blocked(_: Request):
    return JSONResponse(status_code=401, content={"error": "Unauthorized"})

@app.get("/api/validate_key/{key}")
async def validate_key_blocked(_: Request, key: str):
    return JSONResponse(status_code=401, content={"error": "Unauthorized"})

@app.get("/robots.txt")
async def robots_blocked():
    return PlainTextResponse("User-agent: *\nDisallow: /", status_code=200)

def generate_key():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=16))

class KeyButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Get Key", style=discord.ButtonStyle.primary, custom_id="get_key_button")
    async def get_key(self, button: discord.ui.Button, interaction: discord.Interaction):
        key = generate_key()
        expire = (datetime.utcnow() + timedelta(hours=24)).isoformat()
        keys = load_keys()
        keys[key] = expire
        save_keys(keys)

        try:
            await interaction.user.send(f"🎟️ Your 24-hour key is:\n`{key}`")
            await interaction.response.send_message("✅ I sent you a DM with your key!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I couldn't DM you. Please enable DMs from server members.", ephemeral=True)

@bot.slash_command(name="getkey")
async def getkey(ctx):
    embed = discord.Embed(
        title="Get your access key",
        description="Click the button below to receive your 24-hour key in a DM.",
        color=discord.Color.blue()
    )
    await ctx.respond(embed=embed, view=KeyButton())

async def start():
    loop = asyncio.get_event_loop()
    loop.create_task(bot.start(os.getenv("DISCORD_BOT")))
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(start())
