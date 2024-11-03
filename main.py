import typing
from collections import OrderedDict
from operator import truediv
from random import random
from typing import List
import os
import json
import random

import numpy as np
from dotenv import load_dotenv

import discord
from discord import app_commands
from discord.app_commands import tree, CommandTree
from discord.ext import commands
import mysql.connector
import nltk

from nltk.sentiment.vader import SentimentIntensityAnalyzer
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer

load_dotenv()
DISCORDTOKEN: str = os.getenv("TOKEN")
DBUSER: str = os.getenv("DBUSERNAME")
DBPASS: str = os.getenv("DB5PASSWORD")
print(DBUSER)
print(DBPASS)

f = open('config.json')
config = json.load(f)
f.close()

filterListBase = set(config['baseFilter'])
rolesList = set(config['authorizedRoles'])
userFilter = set([])
filterList = set([])
penalty = config['penalty']
castes:dict = dict(config['castes'])

def isAuthorized(user: discord.Member):
    flag = 0
    rolesList = set(config['authorizedRoles'])
    if user.guild.owner.id == user.id:
        #flag = 1
        pass
    for role in user.roles:
        for i in rolesList:
            if role.id == int(i):
                flag = 1
                break
    return flag

def buildFilters():
    global filterListBase
    global rolesList
    global penalty
    global castes
    f = open('config.json')
    config = json.load(f)
    f.close()

    filterListBase = set(config['baseFilter'])
    rolesList = set(config['authorizedRoles'])
    penalty = config['penalty']
    castes = dict(config['castes'])

    userFilter.clear()
    filterList.clear()
    members = bot.get_all_members()
    for x in members:
        flag = 0
        for i in x.roles:
            print(i)
            for j in rolesList:
                if i.id == int(j):
                    print(f'{x}: {i.name.lower()}, {j.lower()}')
                    flag = 1
                    break
        if flag == 1:
            userFilter.add(x.display_name)
            userFilter.add(x.mention)

    for x in filterListBase:
        filterList.add(x)

    for x in rolesList:
        filterList.add(x)
    print('userfilter:')
    for x in userFilter:
        filterList.add(x)
        print(x)
    print('======')

    return filterList

def preprocess_text(text):
    # Tokenize the text
    tokens = word_tokenize(text.lower())

    # Remove stop words
    filtered_tokens = [token for token in tokens if token not in stopwords.words('english')]

    # Lemmatize the tokens
    lemmatizer = WordNetLemmatizer()
    lemmatized_tokens = [lemmatizer.lemmatize(token) for token in filtered_tokens]

    # Join the tokens back into a string
    processed_text = ' '.join(lemmatized_tokens)
    return processed_text

def get_sentiment(text):
    scores = analyzer.polarity_scores(text)
    sentiment = scores['compound']
    #sentiment = 1 if sentiment >= 0 else 0
    return sentiment

async def setSC(mention:str, value:int, interaction:discord.Interaction):
    id = mention.replace('<', '')
    id = id.replace('>', '')
    id = id.replace('@', '')

    query = f'SELECT update_credit(\'{id}\', {value})'
    print(query)
    cursor.execute(query)
    for x in cursor:
        read = True
    await checkCaste(interaction.guild.get_member(int(id)), interaction.guild)
    return value

async def adjSC(mention:str, value:int, interaction: discord.Interaction | discord.Message):
    # print(username)
    id = mention.replace('<', '')
    id = id.replace('>', '')
    id = id.replace('@', '')
    # print(username)
    # print(ctx.author.id)

    query = f'SELECT modify_social_credit(\'{id}\', {value})'
    print(query)
    cursor.execute(query)

    for x in cursor:
        newValue = x[0]

    for x in interaction.guild.roles:
        print(x)
    await checkCaste(interaction.guild.get_member(int(id)), interaction.guild)
    return(newValue)

async def checkCaste(member: discord.Member, guild: discord.Guild):
    query = f'SELECT credit FROM usercredit WHERE id = \'{member.id}\''
    print(query)
    cursor.execute(query)
    for x in cursor:
        sc = x[0]
        print(sc)
        prevId = None
        if len(castes) > 0:
            print('castes')
            for roleId, t in castes.items():
                print(f'{sc}, {t}')
                if int(sc) >= int(t):
                    if prevId:
                        await member.remove_roles(guild.get_role(int(prevId)))
                    print(f'add {guild.get_role(int(roleId))}')
                    await member.add_roles(guild.get_role(int(roleId)))
                    prevId = roleId
                else:
                    print(f'remove {guild.get_role(int(roleId))}')
                    await member.remove_roles(guild.get_role(int(roleId)))



async def addCaste(interaction: discord.Interaction, id: int, threshold: int):
    flag = 0
    if len(castes)>0:
        if 'id' in castes:
            flag = 1
            await interaction.response.send_message(f'A caste already exists with {interaction.guild.get_role(id).name} with a credit threshold of {castes['id']}. Updating threshold to {threshold}', ephemeral=True)
    castes[f'{id}'] = threshold

    #val_based = {k: v for k, v in sorted(castes.items(), key=lambda item: item[1])}
    keys = list(castes.keys())
    values = list(castes.values())
    sorted_value_index = np.argsort(values)
    sorted_castes = {keys[i]: values[i] for i in sorted_value_index}
    config['castes'] = sorted_castes
    with open('config.json', 'w') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
        f.close()
    buildFilters()
    if not flag:
        await interaction.response.send_message(f'Added caste {interaction.guild.get_role(int(id)).name} with a credit threshold of {threshold}', ephemeral=True)
    for member in interaction.guild.members:
        await checkCaste(member, interaction.guild)

# download nltk corpus (first time only)
nltk.download('all')
analyzer = SentimentIntensityAnalyzer()

# Creating connection object
mydb = mysql.connector.connect(
    host = "localhost",
    user = DBUSER,
    password = DBPASS,
    database = "socialcredit"
)

# Printing the connection object
print(mydb)

mydb.autocommit = True

cursor = mydb.cursor()

cursor.execute("SELECT * FROM usercredit")
for x in cursor:
    print(x)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='/', intents=intents)

@bot.tree.command(name="setsc", description="Set someone's social credit to a given value")
@app_commands.describe(user = "target user", value = "New social credit")
async def setsc(interaction: discord.Interaction, user: str, value: int):
    if isAuthorized(interaction.user):
        value = await setSC(user, value, interaction)
        await interaction.response.send_message(f'Set {user}\'s credit to {value}')
    else:
        value = await adjSC(interaction.user.mention, penalty * -1, interaction)
        await interaction.response.send_message(f'Unauthorized User. {interaction.user.mention}\'s social credit is now {value}')

@setsc.autocomplete("user")
async def setsc_autocompletion(interaction: discord.Interaction, current:str) -> typing.List[app_commands.Choice[str]]:
    members = interaction.guild.members
    data = []
    for member in members:
        if current.lower() in member.display_name.lower():
            if len(data) < 24:
                data.append(app_commands.Choice(name=member.display_name, value=member.mention))
            elif len(data) < 25:
                data.append(app_commands.Choice(name="...", value=""))
    return data

@bot.tree.command(name="adjustsc", description="Change someone's social credit")
@app_commands.describe(user="target user", value="amount")
async def adjustsc(interaction: discord.Interaction, user: str, value: int):
    if isAuthorized(interaction.user):
        newVal = await adjSC(user, value, interaction)
        await interaction.response.send_message(f'{user}\'s social credit is now {newVal}')
    else:
        value = await adjSC(interaction.user.mention, penalty * -1, interaction)
        await interaction.response.send_message(f'Unauthorized User. {interaction.user.mention}\'s social credit is now {value}')

@adjustsc.autocomplete("user")
async def adjustsc_autocompletion(interaction: discord.Interaction, current:str) -> typing.List[app_commands.Choice[str]]:
    members = interaction.guild.members
    data = []
    for member in members:
        if current.lower() in member.display_name.lower():
            if len(data) < 24:
                data.append(app_commands.Choice(name=member.display_name, value=member.mention))
            elif len(data) < 25:
                data.append(app_commands.Choice(name="...", value=""))
    return data

@bot.event
async def on_ready():
    #print(userFilter[0])
    buildFilters()
    try:
        await bot.tree.sync()
    except Exception as e:
        print(e)
    print(f'We have logged in as {bot.user}')
    pass

@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    splitMessage = message.content.lower().split(" ")

    flag = 0
    if isAuthorized(message.author):
        print('user is authorized')
        for i in splitMessage:
            for j in filterListBase:
                if i == j.lower():
                    flag = 1
                    break
    else:
        print('user is not authorized')
        for i in splitMessage:
            for j in filterList:
                print(f'{i}: {j.lower()}')

                if i == j.lower():

                    flag = 1
                    break
    league = 1
    if 'league' in splitMessage:
        league = 2
        flag = 1

    if flag == 1:
        processedText = preprocess_text(message.content)

        sentiment = get_sentiment(processedText)

        if sentiment < 0 or league == 2:
            value = await adjSC(message.author.mention, penalty * -1*league, message)
            await message.channel.send(content = f'{message.author.display_name}:||{message.content}||\nTHIS MESSAGE HAS BEEN CENSORED BY THE STATE. YOU HAVE BEEN FINED {penalty*league} SOCIAL CREDIT\nYOUR SOCIAL CREDIT IS NOW {value}')
            await message.delete()
    await bot.process_commands(message)

@bot.event
async def on_member_update(old: discord.Member, new: discord.Member):
    buildFilters()
    pass

@bot.tree.command(name="showsc", description="Display your social credit")
async def showSC(interaction: discord.Interaction):
    id = interaction.user.id
    query = f'SELECT get_credit(\'{id}\')'
    print(query)
    cursor.execute(query)

    for x in cursor:
        credit = x
    await interaction.response.send_message(f'Your social credit is {credit[0]}', ephemeral = True)

@bot.tree.command(name="authorizerole", description="Add a role to the list of authorized roles")
@app_commands.describe(role="role to authorize for commands")
async def authorizerole(interaction: discord.Interaction, role: str):
    if isAuthorized(interaction.user):
        role = role.replace('<@&', '')
        role = role.replace('>', '')
        rolesList.add(role)
        config['authorizedRoles'] = list(rolesList)
        with open('config.json', 'w') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
            f.close()
            await interaction.response.send_message(f'Successfully added {interaction.guild.get_role(int(role)).name} to the list of authorized roles', ephemeral = True)
    else:
        value = await adjSC(interaction.user.mention, penalty * -1, interaction)
        await interaction.response.send_message(f'Unauthorized User. {interaction.user.mention}\'s social credit is now {value}')
    pass

@authorizerole.autocomplete("role")
async def authorizerole_autocompletion(interaction: discord.Interaction, current:str) -> typing.List[app_commands.Choice[str]]:
    roles = interaction.guild.roles
    data = []
    for role in roles:
        if current.lower() in role.name.lower():
            if len(data) < 24:
                data.append(app_commands.Choice(name=role.name, value=role.mention))
            elif len(data) < 25:
                data.append(app_commands.Choice(name="...", value=""))
    return data

@bot.tree.command(name="removerole", description="Remove a role from the list of authorized roles")
@app_commands.describe(role="role to revoke authorization")
async def removerole(interaction: discord.Interaction, role: str):
    if isAuthorized(interaction.user):
        role = role.replace('<@&', '')
        role = role.replace('>', '')
        rolesList.remove(role)
        config['authorizedRoles'] = list(rolesList)
        with open('config.json', 'w') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
            f.close()
        buildFilters()
        await interaction.response.send_message(f'Successfully removed {interaction.guild.get_role(int(role)).name} from the list of authorized roles', ephemeral = True)
    else:
        value = await adjSC(interaction.user.mention, penalty * -1, interaction)
        await interaction.response.send_message(f'Unauthorized User. {interaction.user.mention}\'s social credit is now {value}')
    pass

@removerole.autocomplete("role")
async def removerole_autocompletion(interaction: discord.Interaction, current:str) -> typing.List[app_commands.Choice[str]]:
    roles = interaction.guild.roles
    data = []
    for role in roles:
        if str(role.id) in rolesList:
            if current.lower() in role.name.lower():
                if len(data) < 24:
                    data.append(app_commands.Choice(name=role.name, value=role.mention))
                elif len(data) < 25:
                    data.append(app_commands.Choice(name="...", value=""))
    return data

@bot.tree.command(name="setpenalty", description="Set the penalty for unauthorized command use")
@app_commands.describe(value="penalty amount")
async def setpenalty(interaction: discord.Interaction, value: int):
    if isAuthorized(interaction.user):
        config['penalty'] = value
        with open('config.json', 'w') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
            f.close()
            await interaction.response.send_message(f'Successfully set penalty to {value}', ephemeral = True)
    else:
        value = await adjSC(interaction.user.mention, penalty * -1)
        await interaction.response.send_message(f'Unauthorized User. {interaction.user.mention}\'s social credit is now {value}')
    pass


#Remove after testing
@bot.tree.command(name="addcaste", description="add a caste")
@app_commands.describe(threshold="social credit threshold", role="role to make caste")
async def addcaste(interaction: discord.Interaction, role: str, threshold: int):
    if isAuthorized(interaction.user):
        id = role.replace('<@&', '')
        id = id.replace('>', '')

        await addCaste(interaction, int(id), threshold)
        #await interaction.response.send_message(f'{mention}', ephemeral = True)
    else:
        value = await adjSC(interaction.user.mention, penalty * -1, interaction)
        await interaction.response.send_message(f'Unauthorized User. {interaction.user.mention}\'s social credit is now {value}')
    pass

@addcaste.autocomplete("role")
async def addcaste_autocompletion(interaction: discord.Interaction, current:str) -> typing.List[app_commands.Choice[str]]:
    roles = interaction.guild.roles
    data = []
    for role in roles:
        if current.lower() in role.name.lower():
            if len(data) < 24:
                data.append(app_commands.Choice(name=role.name, value=role.mention))
            elif len(data) < 25:
                data.append(app_commands.Choice(name="...", value=""))
    return data

@bot.tree.command(name="removecaste", description="remove a caste")
@app_commands.describe(role="role to remove caste of")
async def removecaste(interaction: discord.Interaction, role: str):
    if isAuthorized(interaction.user):
        id = role.replace('<@&', '')
        id = id.replace('>', '')

        del castes[f'{id}']
        config['castes'] = castes
        with open('config.json', 'w') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
            f.close()
        await interaction.response.send_message(f'Removed {interaction.guild.get_role(int(id))} caste', ephemeral = True)
    else:
        value = await adjSC(interaction.user.mention, penalty * -1, interaction)
        await interaction.response.send_message(f'Unauthorized User. {interaction.user.mention}\'s social credit is now {value}')
    pass

@removecaste.autocomplete("role")
async def removecaste_autocompletion(interaction: discord.Interaction, current:str) -> typing.List[app_commands.Choice[str]]:
    roles = castes.keys()
    data = []
    for role in roles:
        if current.lower() in interaction.guild.get_role(int(role)).name.lower():
            if len(data) < 24:
                data.append(app_commands.Choice(name=interaction.guild.get_role(int(role)).name,
                                                value=interaction.guild.get_role(int(role)).mention))
            elif len(data) < 25:
                data.append(app_commands.Choice(name="...", value=""))
    return data

@bot.tree.command(name="showcastes", description="display castes")
async def showcastes(interaction: discord.Interaction):
    out = ''
    for roleId, threshold in castes.items():
        out = f'{out}\n{threshold}: {interaction.guild.get_role(int(roleId)).name}'
    await interaction.response.send_message(out, ephemeral = True)
    pass

@bot.tree.command(name="addfilter", description="add a filter")
@app_commands.describe(word="word to filter for")
async def addfilter(interaction: discord.Interaction, word: str):
    if isAuthorized(interaction.user):
        filterListBase.add(word)

        config['baseFilter'] = list(filterListBase)
        print(filterListBase)
        with open('config.json', 'w') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
            f.close()
        await interaction.response.send_message(f'Added {word} to filter', ephemeral = True)
    else:
        value = await adjSC(interaction.user.mention, penalty * -1, interaction)
        await interaction.response.send_message(f'Unauthorized User. {interaction.user.mention}\'s social credit is now {value}')
    pass


@bot.tree.command(name="removefilter", description="add a filter")
@app_commands.describe(word="word to filter for")
async def removefilter(interaction: discord.Interaction, word: str):
    if isAuthorized(interaction.user):
        filterListBase.remove(word)

        config['baseFilter'] = list(filterListBase)
        print(config['baseFilter'])
        with open('config.json', 'w') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
            f.close()
        await interaction.response.send_message(f'Removed {word} from filter', ephemeral=True)
    else:
        value = await adjSC(interaction.user.mention, penalty * -1, interaction)
        await interaction.response.send_message(f'Unauthorized User. {interaction.user.mention}\'s social credit is now {value}')
    pass

@bot.tree.command(name="gamble", description="gamble your social credit")
@app_commands.describe(value="amount to wager")
async def gamble(interaction: discord.Interaction, value: int):
    if value <= 0:
        await interaction.response.send_message(
            f'You must gamble more than 0 credit', ephemeral = True)
        return

    query = f'SELECT credit FROM usercredit WHERE id = \'{interaction.user.id}\''
    cursor.execute(query)
    for x in cursor:
        maxBet = x[0]
    if maxBet < value:
        await interaction.response.send_message(
            f'You cannot gamble more credit than you have', ephemeral=True)
        return

    odds = 0.6 - ((maxBet/100)*0.1)
    x = random.random()
    emojis = set(interaction.guild.emojis)
    if x <= odds:
        value = await adjSC(interaction.user.mention, value, interaction)
        emoji = random.choice(list(emojis))
        await interaction.response.send_message(f'{emoji}{emoji}{emoji}\nYou win! Your social credit is now {value}', ephemeral = True)
    else:
        value = await adjSC(interaction.user.mention, value * -1, interaction)
        emoji = random.choice(list(emojis))
        emoji2 = random.choice(list(emojis))
        emojis.remove(emoji2)
        emoji3 = random.choice(list(emojis))
        await interaction.response.send_message(f'{emoji}{emoji2}{emoji3}\nYou lose. Your social credit is now {value}', ephemeral = True)
    print(odds)
    pass

@bot.tree.command(name="scleaderboard", description="show the social credit leaderboard")
async def scleaderboard(interaction: discord.Interaction):
    query = 'SELECT * FROM usercredit ORDER BY credit DESC'
    cursor.execute(query)
    out = "STATE RANKING"
    for x in cursor:
        if bot.get_user(int(x[0])):
            out += f'\n{bot.get_user(int(x[0])).display_name}: {x[1]}'
    await interaction.response.send_message(out, ephemeral = True)

bot.run(DISCORDTOKEN)