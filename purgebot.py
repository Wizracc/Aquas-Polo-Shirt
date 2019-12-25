import discord
import datetime
import time
import sys
import asyncio
import requests
import os
from config import discord_key, debug
from tools import *

client = discord.Client()
background_task_running = False

@client.event
async def on_ready():
  global background_task_running
  print('Logged in as')
  print(client.user.name)
  print(client.user.id)
  print('------')
  if not background_task_running:
      background_task_running = True
      client.loop.create_task(background_purge())

async def background_purge():
  # Get the output channel, #anything in Aqua Dragon's discord
  output_channel = discord.utils.get(client.get_all_channels(), id=173937505651916801)
  # Put on loop
  while not client.is_closed():
    # Find the next time to try to purge. Always 1 min after midnight GMT
    next_purge_time = current_time_block_start() + seconds_in_day + 60
    time_to_sleep = next_purge_time - int(time.time())
    if time_to_sleep < 0:
      time_to_sleep = seconds_in_day
    # Print how long to sleep, then sleep
    print("Sleeping for {x} hours, {y} minutes, {z} seconds."\
        .format(x=int(time_to_sleep/(60*60)), y=int(time_to_sleep%(60*60)/60), z=time_to_sleep%(60)))
    await asyncio.sleep(time_to_sleep)
    # Time to wake up
    print("Waking up to cull and purge.")
    # Cull = 4 or fewer uses in the last 20 days is removed
    # Only for 20 - 39 day old
    # Purge = 4 or fewer uses in the last 40 days is removed
    # Only for 40+ days old
    emojis_list = await get_emojis(output_channel.guild)
    cull_eligible = []
    purge_eligible = []
    young_emojis = []

    for emoji in emojis_list:
      emoji_age = int(time.time()) - time.mktime(emoji.created_at.timetuple())
      if emoji_age >= seconds_in_day * 20 and emoji_age < seconds_in_day * 40:
        cull_eligible.append(emoji)
      elif emoji_age > seconds_in_day * 40:
        purge_eligible.append(emoji)

    print("starting counts")

    cull_numbers = await get_emoji_count(output_channel.guild, cull_eligible, 20, client.user.id, True)
    purge_numbers = await get_emoji_count(output_channel.guild, purge_eligible, 40, client.user.id, True)

    cull_list = []
    purge_list = []

    for emoji_id in cull_numbers.keys():
      if cull_numbers[emoji_id] < 4:
        cull_list.append(discord.utils.get(emojis_list, id=int(emoji_id)))

    for emoji_id in purge_numbers.keys():
      if purge_numbers[emoji_id] < 4:
        purge_list.append(discord.utils.get(emojis_list, id=int(emoji_id)))

    # print purge results first, then purge
    if not (len(cull_list) == 0 and len(purge_list) == 0):
      desc_str = ""
      if len(cull_list) > 0:
        desc_str += "{c} feeble emoji ha{sve} been culled."\
          .format(c=len(cull_list), sve=("s","ve")[len(cull_list)>=2])
        if len(purge_list) > 0:
          desc_str += "\n"
      if len(purge_list) > 0:
        desc_str += "{c} insignificant emoji ha{sve} been purged."\
          .format(c=len(purge_list), sve=("s","ve")[len(purge_list)>=2])

      emb = discord.Embed(title="Purge Report:", color=0xcc0000, description=desc_str)
      thumb_url="https://cdn.discordapp.com/attachments/556686449513201666/559921702448922627/unknown.png"
      emb.set_thumbnail(url=thumb_url)

      for culled in cull_list:
        created_time = culled.created_at
        age_in_days = int((time.time() - time.mktime(created_time.timetuple()))/seconds_in_day)
        culled_uses = cull_numbers[str(culled.id)]
        title = "Culled: {c}".format(c=culled.name)
        text = "{e}\n".format(e=str(culled))\
          + "Age: {d} days.\n".format(d=age_in_days)\
          + "Uses: {u} in the last 20 days.".format(u=culled_uses)
        emb.add_field(name=title, value=text, inline=False)

      for purged in purge_list:
        created_time = purged.created_at
        age_in_days = int((time.time() - time.mktime(created_time.timetuple()))/seconds_in_day)
        purged_uses = purge_numbers[str(purged.id)]
        title = "Purged: {c}".format(c=purged.name)
        text = "{e}\n".format(e=str(purged))\
          + "Age: {d} days.\n".format(d=age_in_days)\
          + "Uses: {u} in the last 40 days.".format(u=purged_uses)
        emb.add_field(name=title, value=text, inline=False)
      
      foot_text = "Ping @just_Grynn#0574 with any questions, or for backed-up images of purged emoji."
      emb.set_footer(text=foot_text)

      await output_channel.send(embed=emb)

      for culled in cull_list:
        culled_name = culled.name
        await download_emoji(culled.guild, culled)
        await culled.delete(reason="Emoji has been culled.")
        print("culled " + culled_name)
      for purged in purge_list:
        purged_name = purged.name
        await download_emoji(purged.guild, purged)
        await purged.delete(reason="Emoji has been purged.")
        print("purged " + purged_name)

    emojis_list = await get_emojis(output_channel.guild)
    for emoji in emojis_list:
      emoji_age = int(time.time()) - time.mktime(emoji.created_at.timetuple())
      if emoji_age < seconds_in_day * 20:
        young_emojis.append(emoji)
    await get_emoji_count(output_channel.guild, young_emojis, 3, client.user.id, True)

async def download_emoji(server, emoji):
  img_data = requests.get(emoji.url).content
  directory = server.name + '-' + str(server.id) + '-purged/' + datetime.date.today().isoformat()
  if not os.path.exists(directory):
    os.makedirs(directory)
  with open(directory+'/'+emoji.name+'-'+str(emoji.id)+'.png', 'wb') as handler:
    handler.write(img_data)

@client.event
async def on_message(message):
  if(message.author.id == 91250749383655424):
    if(message.content.startswith("!purge_info")):
      try:
        async with message.channel.typing():
          emojis_list = await get_emojis(message.guild)
          cull_eligible = []
          purge_eligible = []

          for emoji in emojis_list:
            emoji_age = int(time.time()) - time.mktime(emoji.created_at.timetuple())
            if emoji_age >= seconds_in_day * 20 and emoji_age < seconds_in_day * 40:
              cull_eligible.append(emoji)
            elif emoji_age > seconds_in_day * 40:
              purge_eligible.append(emoji)

          cull_numbers = await get_emoji_count(message.guild, cull_eligible, 20, client.user.id)
          purge_numbers = await get_emoji_count(message.guild, purge_eligible, 40, client.user.id)

          cull_list = []
          purge_list = []

          for emoji_id in cull_numbers.keys():
            if cull_numbers[emoji_id] < 4:
              cull_list.append(discord.utils.get(emojis_list, id=int(emoji_id)))

          for emoji_id in purge_numbers.keys():
            if purge_numbers[emoji_id] < 4:
              purge_list.append(discord.utils.get(emojis_list, id=int(emoji_id)))

          next_purge_time = current_time_block_start() + seconds_in_day
          time_to_next_check = next_purge_time - int(time.time()) + 60

          out_message1 = "This server allows anyone with the \"moderator\" role to upload custom emojis. "\
            + "To prevent the server from reaching the cap of 50 custom emojis, we've decided to come up "\
            + "with a system to trim down unused emojis. There are three stages in an emoji's life. "\
            + "The first stage, a newly uploaded emoji. After 20 days, it must prove itself, otherwise it "\
            + "may be *culled*. After 40 days, less rigorous use is required from an emoji, however it "\
            + "may still be eligible to be *purged*. An emoji will be *culled* if it is more than 20 "\
            + "and less than 40 days old, and it has been used fewer than 4 times within the last 20 days. "\
            + "An emoji will be *purged* if it is 40 or more days old, and it has been used fewer than 4 "\
            + "times in the last 40 days. These statistics are checked every 24 hours at midnight GMT."\
            + " (about {x} hours and {y} minutes from now)"\
              .format(x=int(time_to_next_check/(60*60)), y=int(time_to_next_check%(60*60)/60))
          await message.channel.send(out_message1)
          
          if len(cull_list) > 0:
            out_message2 = ""
            out_message3 = ""
            if len(cull_list) == 1:
              out_message2 += "This emoji is "
            else:
              out_message2 += "These emojis are "
            out_message2 += "currently eligible to be culled: "
            for emoji in cull_list:
              out_message3 += str(emoji) + " "
            await message.channel.send(out_message2)
            await message.channel.send(out_message3)
          
          if len(purge_list) > 0:
            out_message4 = ""
            out_message5 = ""
            if len(purge_list) == 1:
              out_message4 += "This emoji is "
            else:
              out_message4 += "These emojis are "
            out_message4 += "currently eligible to be purged: "

            for emoji in purge_list:
              out_message5 += str(emoji) + " "
            await message.channel.send(out_message4)
            await message.channel.send(out_message5)
      except Exception as e:
        print(e)
          
while True:
  try:
    print('trying to start!')
    client.loop.run_until_complete(client.start(discord_key))
  except (KeyboardInterrupt, SystemExit):
    print('Manual override.')
    sql_db.close()
    sys.exit()
  except BaseException as e:
    print('ran into a problem!')
    print(e)
    try:
      time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
      print("Manual override while sleeping, exiting.")
      sql_db.close()
      sys.exit()
