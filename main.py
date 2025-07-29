import uvicorn, discord, asyncio, json, random, string, os
from fastapi import FastAPI, Request
from pydantic import BaseModel
from datetime import datetime, timedelta
from fastapi.responses import JSONResponse, PlainTextResponse

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
