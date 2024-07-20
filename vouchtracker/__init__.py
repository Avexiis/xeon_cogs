from .vouchtracker import Vouches

__red_end_user_data_statement__ = "This cog does not store personal data."

async def setup(bot):
    await bot.add_cog(Vouches(bot))
