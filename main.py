import os
import asyncio
import json
import discord
from discord.ext import commands
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("TOKEN")
PORT = int(os.environ.get("PORT", 8000))
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}


def save_config(data: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


@bot.event
async def on_ready():
    bot.add_view(VerifyView())
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Connected to {len(bot.guilds)} server(s)")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="verifikasi anggota"
        )
    )


class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="✅ Verifikasi",
        style=discord.ButtonStyle.success,
        custom_id="verify_button"
    )
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user

        await interaction.response.defer(ephemeral=True)

        config = load_config()
        role_id = config.get(str(guild.id))

        async def dm(embed: discord.Embed):
            try:
                await member.send(embed=embed)
            except discord.Forbidden:
                await interaction.followup.send(embed=embed, ephemeral=True)

        if role_id is None:
            embed = discord.Embed(
                description="❌ Role verifikasi belum diatur. Minta admin jalankan `!setup @role`.",
                color=discord.Color.red()
            )
            await dm(embed)
            return

        role = guild.get_role(int(role_id))

        if role is None:
            embed = discord.Embed(
                description="❌ Role tidak ditemukan di server. Minta admin jalankan `!setup @role` ulang.",
                color=discord.Color.red()
            )
            await dm(embed)
            return

        if role in member.roles:
            embed = discord.Embed(
                description="✅ Kamu sudah terverifikasi!",
                color=discord.Color.green()
            )
            await dm(embed)
            return

        try:
            await member.add_roles(role, reason="Verifikasi tombol")
            embed = discord.Embed(
                title="✅ Verifikasi Berhasil!",
                description=(
                    f"Halo {member.mention}, kamu berhasil diverifikasi di **{guild.name}**!\n\n"
                    f"Role **{role.name}** telah diberikan. Selamat bergabung! 🎉"
                ),
                color=discord.Color.green()
            )
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
            embed.set_footer(text=guild.name)
            await dm(embed)
            print(f"Verified: {member} ({member.id}) → {role.name} ({role.id})")
        except discord.Forbidden:
            embed = discord.Embed(
                description="❌ Bot tidak punya izin untuk memberikan role. Pastikan posisi role bot lebih tinggi dari role yang dituju.",
                color=discord.Color.red()
            )
            await dm(embed)


@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def setup(ctx, role: discord.Role):
    config = load_config()
    config[str(ctx.guild.id)] = str(role.id)
    save_config(config)

    embed = discord.Embed(
        title="🔒 Verifikasi Anggota",
        description=(
            f"Selamat datang di **{ctx.guild.name}**!\n\n"
            "Tekan tombol di bawah untuk memverifikasi diri kamu dan "
            f"mendapatkan akses sebagai **{role.name}**."
        ),
        color=discord.Color.green()
    )
    embed.set_footer(text=f"{ctx.guild.name} • Sistem Verifikasi")
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)

    await ctx.message.delete()
    await ctx.send(embed=embed, view=VerifyView())


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Kamu tidak punya izin untuk perintah ini.", delete_after=5)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Cara pakai: `!setup @role` — mention role yang ingin diberikan saat verifikasi.", delete_after=8)
    elif isinstance(error, commands.RoleNotFound):
        await ctx.send("❌ Role tidak ditemukan. Pastikan kamu mention rolenya langsung, contoh: `!setup @Member`", delete_after=8)
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        await ctx.send(f"❌ Terjadi kesalahan: {error}", delete_after=8)


async def health_server():
    async def handle(request):
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_get("/", handle)
    app.router.add_get("/healthz", handle)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"Health server running on port {PORT}")


async def main():
    await health_server()
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
