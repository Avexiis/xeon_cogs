import discord
import json
import os
from discord import app_commands
from redbot.core import commands, Config, checks
from redbot.core.bot import Red

VOUCHES_FILE_PATH = os.path.join(os.path.dirname(__file__), 'vouches.json')

class Vouches(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        default_guild = {
            "tracked_roles": [],
            "vouch_channel_id": None,
            "vouch_data": {}
        }
        self.config.register_guild(**default_guild)
        self.leaderboard_cooldown = {}

        # Load vouch data from file
        self.load_vouch_data()

    def load_vouch_data(self):
        if os.path.exists(VOUCHES_FILE_PATH):
            with open(VOUCHES_FILE_PATH, 'r') as f:
                old_data = json.load(f)

            for guild in self.bot.guilds:
                self.bot.loop.create_task(self.import_vouch_data(guild.id, old_data))
    
    async def import_vouch_data(self, guild_id, old_data):
        async with self.config.guild_from_id(guild_id).vouch_data() as vouch_data:
            for user_id, vouches in old_data.items():
                vouch_data[user_id] = vouches

    async def save_vouch_data(self, guild_id):
        all_vouches = {}
        async with self.config.guild_from_id(guild_id).vouch_data() as vouch_data:
            all_vouches.update(vouch_data)

        with open(VOUCHES_FILE_PATH, 'w') as f:
            json.dump(all_vouches, f, indent=4)

    async def cog_load(self):
        self.bot.tree.add_command(app_commands.Command(name="vouches", description="Check user vouches", callback=self.vouches_command))
        self.bot.tree.add_command(app_commands.Command(name="addvouch", description="Add user vouches", callback=self.addvouch_command))
        self.bot.tree.add_command(app_commands.Command(name="removevouch", description="Remove user vouches", callback=self.removevouch_command))
        self.bot.tree.add_command(app_commands.Command(name="vouchleaderboard", description="Show vouch leaderboard", callback=self.vouchleaderboard_command))
        self.bot.tree.add_command(app_commands.Command(name="setvouchchannel", description="Set vouch channel", callback=self.setvouchchannel_command))
        self.bot.tree.add_command(app_commands.Command(name="setvouchroles", description="Set roles for vouches", callback=self.setvouchroles_command))
        await self.bot.tree.sync()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        guild_config = await self.config.guild(message.guild).all()
        if message.channel.id != guild_config["vouch_channel_id"]:
            return

        for member in message.mentions:
            if any(role.id in guild_config["tracked_roles"] for role in member.roles):
                async with self.config.guild(message.guild).vouch_data() as vouch_data:
                    if str(member.id) not in vouch_data:
                        vouch_data[str(member.id)] = 0
                    vouch_data[str(member.id)] += 1

                embed = discord.Embed(
                    title="Vouch Recorded",
                    description=f"{member.mention} has {vouch_data[str(member.id)]} vouches!",
                    timestamp=message.created_at
                )
                await message.channel.send(embed=embed)
        
        await self.save_vouch_data(message.guild.id)

    async def vouches_command(self, interaction: discord.Interaction, user: discord.User):
        guild_config = await self.config.guild(interaction.guild).vouch_data()
        vouch_count = guild_config.get(str(user.id), 0)
        await interaction.response.send_message(f"{user.mention} has {vouch_count} vouches.")

    async def addvouch_command(self, interaction: discord.Interaction, user: discord.User, number: int):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        guild_id = interaction.guild.id
        async with self.config.guild_from_id(guild_id).vouch_data() as vouch_data:
            if str(user.id) not in vouch_data:
                vouch_data[str(user.id)] = 0
            vouch_data[str(user.id)] += number

        await interaction.response.send_message(f"Added {number} vouch(es) for {user.mention}. They now have {vouch_data[str(user.id)]} vouches.")
        await self.save_vouch_data(guild_id)

    async def removevouch_command(self, interaction: discord.Interaction, user: discord.User, number: int):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        guild_id = interaction.guild.id
        async with self.config.guild_from_id(guild_id).vouch_data() as vouch_data:
            if str(user.id) not in vouch_data:
                vouch_data[str(user.id)] = 0
            else:
                vouch_data[str(user.id)] = max(0, vouch_data[str(user.id)] - number)

        await interaction.response.send_message(f"Removed {number} vouch(es) from {user.mention}. They now have {vouch_data[str(user.id)]} vouches.")
        await self.save_vouch_data(guild_id)

    async def vouchleaderboard_command(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            if interaction.guild.id in self.leaderboard_cooldown:
                await interaction.response.send_message("The leaderboard command is on cooldown. Please try again later.", ephemeral=True)
                return
            self.leaderboard_cooldown[interaction.guild.id] = True
            self.bot.loop.call_later(30, lambda: self.leaderboard_cooldown.pop(interaction.guild.id, None))

        guild_config = await self.config.guild(interaction.guild).vouch_data()
        sorted_vouches = sorted(guild_config.items(), key=lambda item: item[1], reverse=True)
        leaderboard = "\n".join([f"#{i + 1} <@{user_id}>: {vouches} vouches" for i, (user_id, vouches) in enumerate(sorted_vouches)])
        
        embed = discord.Embed(
            title="Vouch Leaderboard",
            description=leaderboard,
            color=0xFFD700
        )
        await interaction.response.send_message(embed=embed)

    async def setvouchchannel_command(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        await self.config.guild(interaction.guild).vouch_channel_id.set(channel.id)
        await interaction.response.send_message(f"Vouch channel set to {channel.mention}.")

    async def setvouchroles_command(self, interaction: discord.Interaction, role1: discord.Role, role2: discord.Role = None, role3: discord.Role = None, role4: discord.Role = None, role5: discord.Role = None):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        role_ids = [role.id for role in [role1, role2, role3, role4, role5] if role is not None]
        await self.config.guild(interaction.guild).tracked_roles.set(role_ids)
        await interaction.response.send_message("Tracked roles updated.")

    # Text Command Equivalents
    @commands.command()
    @checks.admin_or_permissions(administrator=True)
    async def setvouchchannel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the vouch channel."""
        await self.config.guild(ctx.guild).vouch_channel_id.set(channel.id)
        await ctx.send(f"Vouch channel set to {channel.mention}.")

    @commands.command()
    @checks.admin_or_permissions(administrator=True)
    async def setvouchroles(self, ctx: commands.Context, *roles: discord.Role):
        """Set the roles to track for vouches."""
        role_ids = [role.id for role in roles]
        await self.config.guild(ctx.guild).tracked_roles.set(role_ids)
        await ctx.send("Tracked roles updated.")

    @commands.command()
    async def vouches(self, ctx: commands.Context, user: discord.User):
        """Check the number of vouches for a user"""
        guild_config = await self.config.guild(ctx.guild).vouch_data()
        vouch_count = guild_config.get(str(user.id), 0)
        await ctx.send(f"{user.mention} has {vouch_count} vouches.")

    @commands.command()
    @checks.admin_or_permissions(administrator=True)
    async def addvouch(self, ctx: commands.Context, user: discord.User, number: int):
        """Manually add vouches for a user"""
        guild_id = ctx.guild.id
        async with self.config.guild_from_id(guild_id).vouch_data() as vouch_data:
            if str(user.id) not in vouch_data:
                vouch_data[str(user.id)] = 0
            vouch_data[str(user.id)] += number

        await ctx.send(f"Added {number} vouch(es) for {user.mention}. They now have {vouch_data[str(user.id)]} vouches.")
        await self.save_vouch_data(guild_id)

    @commands.command()
    @checks.admin_or_permissions(administrator=True)
    async def removevouch(self, ctx: commands.Context, user: discord.User, number: int):
        """Manually remove vouches from a user"""
        guild_id = ctx.guild.id
        async with self.config.guild_from_id(guild_id).vouch_data() as vouch_data:
            if str(user.id) not in vouch_data:
                vouch_data[str(user.id)] = 0
            else:
                vouch_data[str(user.id)] = max(0, vouch_data[str(user.id)] - number)

        await ctx.send(f"Removed {number} vouch(es) from {user.mention}. They now have {vouch_data[str(user.id)]} vouches.")
        await self.save_vouch_data(guild_id)

    @commands.command()
    async def vouchleaderboard(self, ctx: commands.Context):
        """Shows the leaderboard of users with the most vouches"""
        if not ctx.author.guild_permissions.administrator:
            if ctx.guild.id in self.leaderboard_cooldown:
                await ctx.send("The leaderboard command is on cooldown. Please try again later.")
                return
            self.leaderboard_cooldown[ctx.guild.id] = True
            self.bot.loop.call_later(30, lambda: self.leaderboard_cooldown.pop(ctx.guild.id, None))

        guild_config = await self.config.guild(ctx.guild).vouch_data()
        sorted_vouches = sorted(guild_config.items(), key=lambda item: item[1], reverse=True)
        leaderboard = "\n().join([f"#{i + 1} <@{user_id}>: {vouches} vouches" for i, (user_id, vouches) in enumerate(sorted_vouches)])
        
        embed = discord.Embed(
            title="Vouch Leaderboard",
            description=leaderboard,
            color=0xFFD700
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Vouches(bot))
