import discord
from redbot.core import commands, Config, checks
from redbot.core.bot import Red

class Vouches(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        default_guild = {
            "tracked_roles": [],
            "vouch_channel_id": None,
        }
        default_member = {
            "vouch_count": 0
        }
        self.config.register_guild(**default_guild)
        self.config.register_member(**default_member)
        self.leaderboard_cooldown = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.bot:
            return

        guild_config = await self.config.guild(message.guild).all()
        if message.channel.id != guild_config["vouch_channel_id"]:
            return

        for member in message.mentions:
            if any(role.id in guild_config["tracked_roles"] for role in member.roles):
                vouch_count = await self.config.member(member).vouch_count()
                await self.config.member(member).vouch_count.set(vouch_count + 1)

                embed = discord.Embed(
                    title="Vouch Recorded",
                    description=f"{member.mention} has {vouch_count + 1} vouches!",
                    timestamp=message.created_at
                )
                await message.channel.send(embed=embed)

    @commands.hybrid_command(name="vouches", description="Check user vouches")
    @commands.guild_only()
    @checks.admin_or_permissions(administrator=True)
    async def vouches_command(self, ctx: commands.Context, user: discord.Member):
        vouch_count = await self.config.member(user).vouch_count()
        await ctx.send(f"{user.mention} has {vouch_count} vouches.")

    @commands.hybrid_command(name="addvouch", description="Add user vouches")
    @commands.guild_only()
    @checks.admin_or_permissions(administrator=True)
    async def addvouch_command(self, ctx: commands.Context, user: discord.Member, number: int):
        vouch_count = await self.config.member(user).vouch_count()
        await self.config.member(user).vouch_count.set(vouch_count + number)
        await ctx.send(f"Added {number} vouch(es) for {user.mention}. They now have {vouch_count + number} vouches.")

    @commands.hybrid_command(name="removevouch", description="Remove user vouches")
    @commands.guild_only()
    @checks.admin_or_permissions(administrator=True)
    async def removevouch_command(self, ctx: commands.Context, user: discord.Member, number: int):
        vouch_count = await self.config.member(user).vouch_count()
        new_vouch_count = max(0, vouch_count - number)
        await self.config.member(user).vouch_count.set(new_vouch_count)
        await ctx.send(f"Removed {number} vouch(es) from {user.mention}. They now have {new_vouch_count} vouches.")

    @commands.hybrid_command(name="vouchleaderboard", description="Show vouch leaderboard")
    @commands.guild_only()
    @checks.admin_or_permissions(administrator=True)
    async def vouchleaderboard_command(self, ctx: commands.Context):
        if not ctx.author.guild_permissions.administrator:
            if ctx.guild.id in self.leaderboard_cooldown:
                await ctx.send("The leaderboard command is on cooldown. Please try again later.")
                return
            self.leaderboard_cooldown[ctx.guild.id] = True
            self.bot.loop.call_later(30, lambda: self.leaderboard_cooldown.pop(ctx.guild.id, None))

        members_vouches = [(member, await self.config.member(member).vouch_count()) for member in ctx.guild.members]
        sorted_vouches = sorted(members_vouches, key=lambda item: item[1], reverse=True)
        leaderboard = "\n".join([f"#{i + 1} <@{member.id}>: {vouch_count} vouches" for i, (member, vouch_count) in enumerate(sorted_vouches) if vouch_count > 0])
        
        embed = discord.Embed(
            title="Vouch Leaderboard",
            description=leaderboard,
            color=0xFFD700
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="setvouchchannel", description="Set vouch channel")
    @commands.guild_only()
    @checks.admin_or_permissions(administrator=True)
    async def setvouchchannel_command(self, ctx: commands.Context, channel: discord.TextChannel):
        await self.config.guild(ctx.guild).vouch_channel_id.set(channel.id)
        await ctx.send(f"Vouch channel set to {channel.mention}.")

    @commands.hybrid_command(name="setvouchroles", description="Set roles for vouches")
    @commands.guild_only()
    @checks.admin_or_permissions(administrator=True)
    async def setvouchroles_command(self, ctx: commands.Context, role1: discord.Role, role2: discord.Role = None, role3: discord.Role = None, role4: discord.Role = None, role5: discord.Role = None):
        role_ids = [role.id for role in [role1, role2, role3, role4, role5] if role is not None]
        await self.config.guild(ctx.guild).tracked_roles.set(role_ids)
        await ctx.send("Tracked roles updated.")

async def setup(bot):
    await bot.add_cog(Vouches(bot))
