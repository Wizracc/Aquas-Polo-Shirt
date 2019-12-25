import discord
import datetime
import time
import sys
import sqlite3
from config import discord_key, debug
from tools import *

just_grynn_ID = 0 # This was my discord ID. Just so the bot would listen to only me for some commands
client = discord.Client()
#seconds_in_day = 60 * 60 * 24

@client.event
async def on_ready():
  print('Logged in as')
  print(client.user.name)
  print(client.user.id)
  print('------')
  activity=discord.Activity(name="the void", type=discord.ActivityType.watching)
  await client.change_presence(activity=activity)

last_sent_emoji_stats = 0
command_in_use = False
emoji_stats_cd = (5, 0)[debug]

@client.event
async def on_message(message):
  # used for cooldown checking  
  message_time = int(time.time())

  ########################
  # Server-Only commands #
  ########################
  # These commands will not work in PMs
  if not (type(message.guild) == type(None)):
    ## Emoji Stats Command:
    #  Shows emoji stats from the X most recent blocks + current block
    #  Default 30
    #  Debug 0
    #  Also need an if statement for the cooldown
    #  Cooldown must also be declared as global scope here
    global last_sent_emoji_stats
    global command_in_use
    emoji_stats_on_cd = last_sent_emoji_stats >= message_time - emoji_stats_cd
      
    if(message.content.startswith("!emoji_stats") and (command_in_use or emoji_stats_on_cd)):
      reply_message = "Command on global cooldown, try again in a bit"
      await message.channel.send(reply_message)


    if(message.content.startswith("!emoji_stats") and not emoji_stats_on_cd and not command_in_use):
      command_in_use = True
      # set the timer so we get accurate cooldown
      last_sent_emoji_stats = message_time
      
      # Split the message to get args if present
      message_bits = message.content.split()

      num_days = 0
      debug_default_days = 0
      default_days = 40
      recount = False

      # If there are args, check if they're valid
      # Then, assign a number to the number of days to check
      if len(message_bits) > 1 and message_bits[1] not in ["-r"]:
        try:
          num_days = int(message_bits[1])
          max_time = message.guild.created_at
          max_days = int((message_time - time.mktime(max_time.timetuple())) / seconds_in_day)
          if num_days < 0:
            raise ValueError
          elif num_days > max_days:
            error_message = "The server is only " + str(max_days)\
              + " days old! Trying that number instead. This could take a **LONG** time..."
            num_days = max_days + 1
            try:
              await message.channel.send(error_message)
            except Exception as e:
              print(e)
          else:
            pass #If things go correctly, then nothing needs to be done here
        except ValueError as e:
          num_days = (default_days, debug_default_days)[debug]
          error_message = "Did not enter a valid number, trying default value instead (" 
          error_message = error_message + str(num_days) + "). "
          try:
            await message.channel.send(error_message)
          except Exception as e:
            print(e)
      else:
        num_days = (default_days, debug_default_days)[debug]
        
      out_mess = "Counting emojis from the last **" + str(num_days)\
            + (" days", " day")[(num_days==1)] + "** of messages on this server."\
            + " This operation may take a while if this is my first time looking at that time frame."

      if message.author.id == just_grynn_ID and len(message_bits) > 1 and "-r" in message_bits:
        out_mess += " A recount has been requested on this interval."
        recount = True
        
      try:
        await message.channel.send(out_mess)
      except Exception as e:
        print(e)

      try:
        async with message.channel.typing():
          # Call the command to get the emojis that aren't twitch managed
          emojis_collection = await get_emojis(message.guild)

          if emojis_collection == False:
            try:
              await message.channel.send("There was a problem with fetching the emoji list.")
            except Exception as e:
              print(e)
          if len(emojis_collection) == 0:
            try:
              await message.channel.send("There are no server emojis to count!")
            except Exception as e:
              print(e)
          else:
            # Create a dictionary from IDs to Emojis, then populate it
            ids_to_emojis = dict()
            ids_to_emojis = {str(e.id):str(e) for e in emojis_collection}
            # Fetch the stat dictionary
            stat_dict = await \
                get_emoji_count(message.guild, emojis_collection, num_days, client.user.id, recount)
            sorted_ids = sorted(stat_dict, key=stat_dict.__getitem__, reverse=True)
            # Generate an output list. If a message exceeds 2k characters, we must split it
            output_list = [""]
            message_count = 0
            line_count = 0
            for emoji in sorted_ids:
              output_chunk = "{e}`:{s:>5}`".format(e=str(ids_to_emojis[emoji]), s=stat_dict[str(emoji)])
              if len(output_list[message_count]) + len(output_chunk) >= 2000:
                line_count = 0
                output_list.append(output_chunk)
              else:
                if(line_count % 3 == 2):
                  output_chunk += "\n"
                output_list[message_count] = output_list[message_count] + output_chunk
                line_count += 1
            try:
              for output_string in output_list:
                await message.channel.send(output_string)
            except Exception as e:
              print(e)
      except Exception as e:
        print(e)
      command_in_use = False
          
    ## END EMOJI_STATS COMMAND

    if message.content.startswith("!emoji_list"):
      pass

# Bot Loop. If it runs into a problem, it tries to restart.
# Also should properly exit on a ctrl c

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
