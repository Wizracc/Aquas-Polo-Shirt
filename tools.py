import discord
import datetime
import time
import sys
import sqlite3
from config import discord_key, debug

seconds_in_day = 60 * 60 * 24
sqlite_file = 'db.sqlite'
test_file = 'test.sqlite'
sql_db = sqlite3.connect((sqlite_file, test_file)[debug])
sql_c = sql_db.cursor()

## get_emoji_count
# returns a dictionary of emojis ids -> count
# First, checks if there is a table of Guild_Name:Starting_Timestamp
#   for each time chunk within num_days up to the most recent time chunk's beginning
# If the table is not present, create one by fetching logs in the specified time period
#   and populating a table.
# Finally, append the current (incomplete) time chunk's stats by manually fetching the logs
async def get_emoji_count(guild, emojis_collection, num_days, client_id, force_update=False):
  # Build the dictionary to start
  emoji_dict = dict()
  guild_id = guild.id
  for e in emojis_collection:
    emoji_dict[str(e.id)] = 0

  # Generate a list of numbers representing the start chunks of the requested time period
  # start by getting the most recent time block's start (end of previous whole block)
  recent_block_start = current_time_block_start()
  # Start an empty list to hold the block starts
  block_start_list = []
  # Find the value of the furthest back start of block
  request_start_time = recent_block_start - (seconds_in_day * num_days)
  # create a temp variable to hold the "current" time block to be appended to block_start_list
  temp_time_block = recent_block_start
  # Add the start of the desired block to the list
  # - the first temp time is the end of the first desired block, 
  #   so we must subtract 24 hours to add the start of the desired blocks
  while(temp_time_block > request_start_time):
    temp_time_block = temp_time_block - seconds_in_day
    block_start_list.append(temp_time_block)

  # For each block start, check if there is a corresponding table for that guild
  for block_start in block_start_list:
    table_id = str(guild_id) + ":" + str(block_start)
    table_existance = table_exists(table_id)
    
    # if there is a table...
    if table_existance and not force_update:
      sql_cmd_fetch_emoji_stats = "select * from '{table_name}'".format(table_name=table_id)
      sql_c.execute(sql_cmd_fetch_emoji_stats)
      emoji_results = sql_c.fetchall()
      for result in emoji_results:
        if str(result[0]) in emoji_dict.keys():
          emoji_dict[str(result[0])] = emoji_dict[str(result[0])] + int(result[1])
      
    # if there is NOT a table...
    else:
      # Create the table, then populate it from logs
      field1 = "emoji_str"
      field1_type = "TEXT"
      field2 = "usage_count"
      field2_type = "INTEGER"

      # Declare a temp dictionary to hold values
      block_emoji_count = await generate_block_dict(guild, emojis_collection, block_start, client_id)

      if not table_existance:
        sql_cmd_create_table = "CREATE TABLE '{tn}' ('{f1}' '{f1t}' PRIMARY KEY, '{f2}' '{f2t}')"\
                        .format(tn=table_id, f1=field1, f1t=field1_type, f2=field2, f2t=field2_type)
        sql_c.execute(sql_cmd_create_table)

      for emoji, count in block_emoji_count.items():
        emoji_dict[str(emoji)] = emoji_dict[str(emoji)] + count
        if force_update and table_existance:
          sql_cmd_update = "INSERT OR REPLACE INTO '{tn}' ('{f1}', '{f2}') VALUES('{e_str}', '{c_val}')"\
              .format(tn=table_id, f1=field1, f2=field2, e_str=str(emoji), c_val=int(count))
          sql_c.execute(sql_cmd_update)
        else:
          sql_cmd_insert = "INSERT INTO '{tn}' ('{f1}', '{f2}') VALUES('{e_str}', '{c_val}')"\
              .format(tn=table_id, f1=field1, f2=field2, e_str=str(emoji), c_val=int(count))
          sql_c.execute(sql_cmd_insert)
      sql_db.commit()
  
  # For the trailing non-block emojis up to the present time:
  recent_emojis = await generate_block_dict(guild, emojis_collection, recent_block_start, client_id)
  for emoji, count in recent_emojis.items():
    emoji_dict[str(emoji)] = emoji_dict[str(emoji)] + int(count)

  return emoji_dict

## generate_block_dict
# Generates a dictionary of emojis stats for the given message's server 
#           for the given block of time

async def generate_block_dict(guild, emojis_collection, block_start, client_id):
  block_emoji_count = dict()
  for emoji in emojis_collection:
    block_emoji_count[str(emoji.id)] = 0

  # For each message in the time block starting with the given block_start
  # (for each text channel in the guild, for each message in the channel history)
  block_end = block_start + seconds_in_day - 1
  for channel in guild.text_channels:
    try:
      block_start_time = datetime.datetime.fromtimestamp(block_start)
      block_end_time = datetime.datetime.fromtimestamp(block_end)
      async for log_message in channel.history(after=block_start_time, before=block_end_time, limit=None):
        # Ignore messages sent by bot
        if log_message.author.id != client_id:
          for emoji in emojis_collection:
            try:
              if "<" in log_message.content:
                if str(emoji.id) in log_message.content:
                  block_emoji_count[str(emoji.id)] = block_emoji_count[str(emoji.id)] + 1
            except Exception as e:
              print(e)
          if len(log_message.reactions) > 0:
            for reaction in log_message.reactions:
              re_emoji = reaction.emoji
              if re_emoji in emojis_collection:
                block_emoji_count[str(re_emoji.id)] = block_emoji_count[str(re_emoji.id)] + reaction.count
            
    except Exception as e:
      pass
      #print(e)
  return block_emoji_count    
## table_exists
#  returns if a table exists with the given name
def table_exists(table_name):
  sql_cmd_count_name = "select count(*) from sqlite_master where type='table' and name='{name}'"\
                        .format(name=table_name)
  sql_c.execute(sql_cmd_count_name)
  return sql_c.fetchone()[0]

## get_emojis
#  returns the emojis list object
async def get_emojis(guild):
  try:
    emojis_collection = guild.emojis
  except Exception as e:
    print(e)
    return False

  managed_emojis_collection = [e for e in emojis_collection if e.managed]
  unmanaged_emojis_collection = [e for e in emojis_collection if not e.managed]

  return unmanaged_emojis_collection

## most_recent_time_block_end()
#  returns the end of the most recent GMtime day in seconds since jan 1st 1970
def current_time_block_start():
  current_time = int(time.time())
  time_since_chunk = current_time % seconds_in_day
  last_chunk_time = current_time - time_since_chunk
  return last_chunk_time