#!/usr/bin/env python3
"""
Telegram VC DM Bot - Dual Account System
Bot controls, User ID joins VC
"""

import asyncio
import os
import re
from datetime import datetime
from telethon import TelegramClient, errors, events
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest, CheckChatInviteRequest
from telethon.sessions import StringSession
from pytgcalls import PyTgCalls

# Configuration from environment
API_ID = int(os.getenv('API_ID', '2040'))
API_HASH = os.getenv('API_HASH', 'b18441a1ff607e10a989891a5462e627')
BOT_TOKEN = os.getenv('BOT_TOKEN')
STRING_SESSION = os.getenv('STRING_SESSION')

class VCDMBot:
    def __init__(self):
        self.bot = None
        self.user = None
        self.pytgcalls = None
        self.channel_id = None
        self.in_vc = False
        self.msg = None
        self.users = []
    
    async def start(self):
        print("\n" + "="*50)
        print("🤖 TELEGRAM VC DM BOT")
        print("="*50 + "\n")
        
        # Setup Bot Account
        if not BOT_TOKEN:
            BOT_TOKEN = input("🤖 Bot Token (from @BotFather): ").strip()
        
        self.bot = TelegramClient("bot_session", API_ID, API_HASH)
        await self.bot.start(bot_token=BOT_TOKEN)
        bot_me = await self.bot.get_me()
        print(f"✅ Bot Connected: @{bot_me.username}")
        
        # Setup User Account
        if STRING_SESSION:
            print("📱 Using String Session from .env")
            self.user = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)
            await self.user.connect()
            if await self.user.is_user_authorized():
                me = await self.user.get_me()
                print(f"✅ User Connected: {me.first_name} (@{me.username})")
            else:
                print("❌ Invalid String Session")
                return False
        else:
            print("\n" + "="*50)
            print("👤 USER ACCOUNT LOGIN")
            print("="*50)
            phone = input("📞 Phone (e.g., +919876543210): ").strip()
            
            self.user = TelegramClient("user_session", API_ID, API_HASH)
            await self.user.connect()
            
            try:
                await self.user.send_code_request(phone)
                code = input("🔢 OTP Code: ").strip()
                await self.user.sign_in(phone, code)
                
                # Check 2FA
                me = await self.user.get_me()
                if hasattr(me, 'has_password') and me.has_password:
                    pwd = input("🔐 2FA Password: ").strip()
                    await self.user.sign_in(password=pwd)
                
                me = await self.user.get_me()
                print(f"✅ User Connected: {me.first_name} (@{me.username})")
                
                # Save string session
                ss = StringSession.save(self.user.session)
                with open('.env', 'w') as f:
                    f.write(f"BOT_TOKEN={BOT_TOKEN}\n")
                    f.write(f"STRING_SESSION={ss}\n")
                    f.write(f"API_ID={API_ID}\n")
                    f.write(f"API_HASH={API_HASH}\n")
                print("✅ String Session Saved to .env")
                
            except Exception as e:
                print(f"❌ Login Failed: {str(e)}")
                return False
        
        # Setup Bot Commands
        @self.bot.on(events.NewMessage(pattern='/start'))
        async def start_cmd(e):
            await e.reply("""
🤖 **VC DM Bot is Active!**

**Commands:**
/join `<link>` - Join voice chat
/setmsg `<message>` - Set DM message
/senddm - Start sending DMs
/status - Check bot status
/leave - Leave voice chat
/help - Show help

**Message Variables:**
`{name}` - User's first name
`{username}` - User's username  
`{date}` - Current date/time

**Example:**
`/join https://t.me/channel`
`/setmsg Hello {name}! Welcome!`
`/senddm`
            """)
        
        @self.bot.on(events.NewMessage(pattern='/help'))
        async def help_cmd(e):
            await e.reply("""
📖 **Help Guide**

1. **Join Voice Chat:**
   `/join https://t.me/channel`

2. **Set Message:**
   `/setmsg Hello {name}! Thanks for joining!`

3. **Send DMs:**
   `/senddm`

4. **Check Status:**
   `/status`

5. **Leave VC:**
   `/leave`

**Variables:**
- `{name}` - User's first name
- `{username}` - User's username
- `{date}` - Current time
            """)
        
        @self.bot.on(events.NewMessage(pattern='/join (.+)'))
        async def join_cmd(e):
            link = e.pattern_match.group(1)
            await e.reply(f"🔄 Joining: {link}")
            
            channel_id = await self.parse_channel(link)
            if not channel_id:
                await e.reply("❌ Invalid channel link!")
                return
            
            success = await self.join_vc(channel_id)
            if success:
                await e.reply(f"✅ Joined voice chat!\nChannel ID: `{channel_id}`")
            else:
                await e.reply("❌ Failed to join voice chat!")
        
        @self.bot.on(events.NewMessage(pattern='/setmsg (.+)'))
        async def setmsg_cmd(e):
            self.msg = e.pattern_match.group(1)
            await e.reply(f"✅ Message set!\n\n**Preview:**\n{self.msg[:200]}")
        
        @self.bot.on(events.NewMessage(pattern='/senddm'))
        async def senddm_cmd(e):
            if not self.msg:
                await e.reply("❌ Please set a message first using /setmsg")
                return
            
            await e.reply("🔄 Extracting participants from voice chat...")
            await self.get_participants()
            
            if not self.users:
                await e.reply("❌ No users found in voice chat!")
                return
            
            await e.reply(f"📨 Sending DMs to {len(self.users)} users...")
            success, fail = await self.send_dms()
            
            await e.reply(f"""
✅ **DM Campaign Complete!**

📊 Total: {len(self.users)}
✅ Success: {success}
❌ Failed: {fail}
📈 Rate: {(success/len(self.users))*100:.1f}%
            """)
        
        @self.bot.on(events.NewMessage(pattern='/status'))
        async def status_cmd(e):
            status = f"""
📊 **Bot Status**

🤖 Bot: ✅ Running
👤 User: {'✅ Connected' if self.user else '❌ Not connected'}
🎧 Voice Chat: {'✅ Joined' if self.in_vc else '❌ Not joined'}
📝 Message: {'✅ Set' if self.msg else '❌ Not set'}
👥 Participants: {len(self.users)}
            """
            await e.reply(status)
        
        @self.bot.on(events.NewMessage(pattern='/leave'))
        async def leave_cmd(e):
            await self.leave_vc()
            await e.reply("✅ Left voice chat!")
        
        print("\n" + "="*50)
        print("✅ BOT IS RUNNING!")
        print("="*50)
        print("\n📱 Send commands to your bot on Telegram:\n")
        print("  /start")
        print("  /join https://t.me/channel")
        print("  /setmsg Hello {name}!")
        print("  /senddm")
        print("\n" + "="*50 + "\n")
        
        await self.bot.run_until_disconnected()
    
    async def parse_channel(self, channel_input):
        """Parse channel link to ID"""
        if str(channel_input).lstrip('-').isdigit():
            return int(channel_input)
        
        # Invite link
        match = re.search(r't\.me/(?:joinchat/|\+)([a-zA-Z0-9_-]+)', channel_input)
        if match:
            hash_part = match.group(1)
            try:
                updates = await self.user(ImportChatInviteRequest(hash_part))
                if updates.chats:
                    return updates.chats[0].id
            except errors.UserAlreadyParticipantError:
                info = await self.user(CheckChatInviteRequest(hash_part))
                if hasattr(info, 'chat'):
                    return info.chat.id
            except:
                pass
        
        # Username
        username = channel_input.replace('https://t.me/', '').replace('@', '').strip()
        if username:
            try:
                entity = await self.user.get_entity(username)
                return entity.id
            except:
                pass
        
        return None
    
    async def join_vc(self, channel_id):
        """Join voice chat with user account"""
        try:
            full = await self.user(GetFullChannelRequest(channel=channel_id))
            print(f"🎵 Joining: {full.full_chat.title}")
            
            self.pytgcalls = PyTgCalls(self.user)
            await self.pytgcalls.start()
            await self.pytgcalls.join_call(channel_id)
            
            self.channel_id = channel_id
            self.in_vc = True
            return True
        except Exception as e:
            print(f"❌ Join failed: {str(e)}")
            return False
    
    async def get_participants(self):
        """Get VC participants"""
        if not self.pytgcalls or not self.channel_id:
            return []
        
        try:
            participants = await self.pytgcalls.get_participants(self.channel_id)
            self.users = []
            for p in participants:
                uid = getattr(p, 'user_id', getattr(p, 'id', None))
                if uid:
                    self.users.append(uid)
            print(f"📊 Found {len(self.users)} participants")
            return self.users
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return []
    
    async def send_dms(self):
        """Send DMs to all participants"""
        success = 0
        fail = 0
        
        for i, uid in enumerate(self.users, 1):
            try:
                # Get user info
                try:
                    user = await self.user.get_entity(uid)
                    name = getattr(user, 'first_name', 'User')
                    username = getattr(user, 'username', '')
                except:
                    name = 'User'
                    username = ''
                
                # Personalize message
                msg = self.msg
                msg = msg.replace('{name}', name)
                msg = msg.replace('{username}', username)
                msg = msg.replace('{date}', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                
                await self.user.send_message(uid, msg)
                success += 1
                print(f"✅ [{i}/{len(self.users)}] Sent to {uid}")
                
                await asyncio.sleep(1.5)  # Rate limit
                
            except Exception as e:
                fail += 1
                print(f"❌ [{i}/{len(self.users)}] Failed: {uid}")
        
        print(f"\n✅ Complete: {success} success, {fail} failed")
        return success, fail
    
    async def leave_vc(self):
        """Leave voice chat"""
        if self.pytgcalls and self.channel_id:
            try:
                await self.pytgcalls.leave_call(self.channel_id)
                await self.pytgcalls.stop()
                self.in_vc = False
                print("✅ Left voice chat")
            except:
                pass

async def main():
    bot = VCDMBot()
    try:
        await bot.start()
    except KeyboardInterrupt:
        print("\n👋 Bot stopped!")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())