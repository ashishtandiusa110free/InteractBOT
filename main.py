import logging
import os
import time
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import json
from keep_alive import keep_alive, heartbeat, set_bot_ready, update_bot_status  # Import keep_alive functions

# Configuration - Get bot token from environment variables with fallback
BOT_TOKEN = os.getenv('BOT_TOKEN', 'your_bot_token_here')
OWNER_ID = int(os.getenv('OWNER_ID', '0'))  # Replace with your Telegram user ID

# Data storage for messages and feedback
message_log = []
feedback_log = []
user_registry = {}  # Store user info for username-based replies

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def start(update: Update, context: CallbackContext):
    """Handle /start command"""
    try:
        user_id = update.message.from_user.id
        user_name = update.message.from_user.first_name
        username = update.message.from_user.username
        
        # Register user in user_registry for future reference
        user_registry[user_id] = {
            'user_name': user_name,
            'username': username,
            'first_seen': update.message.date.isoformat()
        }
        
        # Update keep-alive status with current user count
        update_bot_status(users=len(user_registry))
        
        welcome_message = (
            f"Hello {user_name}! 👋\n\n"
            "I'm your personal assistant bot. How can I help you today?\n"
            "Use /help to see all available commands."
        )
        update.message.reply_text(welcome_message)
        logger.info(f"User {user_name} started the bot")
    except Exception as e:
        logger.error(f"Error in start command: {str(e)}")
        update.message.reply_text("Sorry, something went wrong. Please try again.")

def help_command(update: Update, context: CallbackContext):
    """Handle /help command"""
    try:
        help_text = (
            "📋 Available Commands:\n\n"
            "🔹 /start - Start the bot\n"
            "🔹 /help - Show this help message\n"
            "🔹 /ask <your question> - Ask me anything or send files\n"
            "🔹 /feedback <1-5> <comment> - Leave feedback\n\n"
            "👨‍💼 Admin Only Commands:\n"
            "🔹 /view_messages - View all user messages\n"
            "🔹 /reply <user_id> <message> - Reply to user by ID\n"
            "🔹 /reply @<username> <message> - Reply to user by username\n"
            "🔹 /broadcast <message> - Send message to all users\n"
            "🔹 /view_feedback - View all feedback\n"
            "🔹 /stats - View bot statistics"
        )
        update.message.reply_text(help_text)
        logger.info(f"Help requested by user {update.message.from_user.id}")
    except Exception as e:
        logger.error(f"Error in help command: {str(e)}")
        update.message.reply_text("Sorry, something went wrong. Please try again.")

def ask(update: Update, context: CallbackContext):
    """Handle /ask command - log user questions and files"""
    try:
        user_id = update.message.from_user.id
        user_name = update.message.from_user.first_name
        username = update.message.from_user.username if update.message.from_user.username else "No Username"

        # Register/update user in user_registry
        user_registry[user_id] = {
            'user_name': user_name,
            'username': username,
            'last_seen': update.message.date.isoformat()
        }

        # Handle text message with /ask command
        if update.message.text:
            if len(update.message.text) <= 5:  # Just "/ask" without content
                update.message.reply_text(
                    "Please provide your question after /ask\n"
                    "Examples:\n"
                    "• /ask What is the weather today?\n"
                    "• Send a file with /ask to share documents"
                )
                return
                
            user_message = update.message.text[5:].strip()  # Remove "/ask " prefix
            message_type = "text"
            file_info = None
        
        # Handle file attachments (documents, photos, videos, etc.)
        else:
            user_message = update.message.caption if update.message.caption else "[File sent without caption]"
            if update.message.caption and update.message.caption.startswith('/ask'):
                user_message = update.message.caption[5:].strip() if len(update.message.caption) > 5 else "[File sent]"
            
            file_info = {}
            message_type = "file"
            
            # Handle different file types
            if update.message.document:
                file_info = {
                    'type': 'document',
                    'file_name': update.message.document.file_name,
                    'file_size': update.message.document.file_size,
                    'file_id': update.message.document.file_id,
                    'mime_type': update.message.document.mime_type
                }
            elif update.message.photo:
                file_info = {
                    'type': 'photo',
                    'file_id': update.message.photo[-1].file_id,  # Get highest resolution
                    'file_size': update.message.photo[-1].file_size
                }
            elif update.message.video:
                file_info = {
                    'type': 'video',
                    'file_id': update.message.video.file_id,
                    'file_size': update.message.video.file_size,
                    'duration': update.message.video.duration
                }
            elif update.message.audio:
                file_info = {
                    'type': 'audio',
                    'file_id': update.message.audio.file_id,
                    'file_size': update.message.audio.file_size,
                    'duration': update.message.audio.duration
                }
            elif update.message.voice:
                file_info = {
                    'type': 'voice',
                    'file_id': update.message.voice.file_id,
                    'file_size': update.message.voice.file_size,
                    'duration': update.message.voice.duration
                }

        # Store the message in the log for admin review
        message_entry = {
            'user_id': user_id,
            'user_name': user_name,
            'username': username,
            'message': user_message,
            'message_type': message_type,
            'file_info': file_info,
            'timestamp': update.message.date.isoformat()
        }
        message_log.append(message_entry)
        
        # Update keep-alive status with message count
        update_bot_status(messages=len(message_log))

        # Respond to user
        if message_type == "file":
            response = f"Thank you, {user_name}! 📎\n\nYour file and message have been logged and will be reviewed shortly. You'll receive a personal response soon!"
        else:
            response = f"Thank you, {user_name}! 📝\n\nYour question has been logged and will be reviewed shortly. You'll receive a personal response soon!"
        
        update.message.reply_text(response)

        # Notify the bot owner about the incoming question (if not from owner)
        if user_id != OWNER_ID and OWNER_ID != 0:
            if message_type == "file":
                file_type = file_info.get('type', 'unknown')
                file_details = ""
                if file_info.get('file_name'):
                    file_details = f"\n📄 File: {file_info['file_name']}"
                elif file_type in ['photo', 'video', 'audio', 'voice']:
                    file_details = f"\n📄 File: {file_type.title()}"
                
                admin_notification = (
                    f"🔔 New File Message Alert!\n\n"
                    f"👤 From: @{username} ({user_name})\n"
                    f"💬 Caption: {user_message}{file_details}\n"
                    f"🆔 User ID: {user_id}"
                )
            else:
                admin_notification = (
                    f"🔔 New Message Alert!\n\n"
                    f"👤 From: @{username} ({user_name})\n"
                    f"💬 Message: {user_message}\n"
                    f"🆔 User ID: {user_id}"
                )
            
            try:
                context.bot.send_message(chat_id=OWNER_ID, text=admin_notification)
                
                # Forward the file to admin if it's a file message
                if message_type == "file":
                    context.bot.forward_message(
                        chat_id=OWNER_ID,
                        from_chat_id=user_id,
                        message_id=update.message.message_id
                    )
            except Exception as e:
                logger.error(f"Failed to notify admin: {str(e)}")

        logger.info(f"{'File' if message_type == 'file' else 'Question'} logged from user {user_name} ({user_id})")
        
    except Exception as e:
        logger.error(f"Error in ask command: {str(e)}")
        update.message.reply_text("Sorry, something went wrong while processing your message. Please try again.")

def feedback(update: Update, context: CallbackContext):
    """Handle /feedback command - collect user feedback with ratings"""
    try:
        if len(context.args) < 2:
            update.message.reply_text(
                "Please provide feedback in this format:\n"
                "/feedback <1-5> <your comment>\n\n"
                "Example: /feedback 5 Great bot, very helpful!"
            )
            return
        
        rating = context.args[0]
        comment = ' '.join(context.args[1:])
        
        # Validate rating
        if rating not in ['1', '2', '3', '4', '5']:
            update.message.reply_text("⚠️ Please provide a rating between 1 and 5.")
            return
        
        # Store feedback
        feedback_entry = {
            'user_id': update.message.from_user.id,
            'user_name': update.message.from_user.first_name,
            'username': update.message.from_user.username,
            'rating': int(rating),
            'comment': comment,
            'timestamp': update.message.date.isoformat()
        }
        feedback_log.append(feedback_entry)
        
        # Create rating stars
        stars = "⭐" * int(rating)
        response = (
            f"Thank you for your feedback! 🙏\n\n"
            f"Rating: {stars} ({rating}/5)\n"
            f"Comment: {comment}"
        )
        update.message.reply_text(response)
        
        # Notify admin of new feedback
        if OWNER_ID != 0 and update.message.from_user.id != OWNER_ID:
            admin_feedback = (
                f"📊 New Feedback Received!\n\n"
                f"👤 From: {update.message.from_user.first_name}\n"
                f"⭐ Rating: {rating}/5\n"
                f"💬 Comment: {comment}"
            )
            try:
                context.bot.send_message(chat_id=OWNER_ID, text=admin_feedback)
            except Exception as e:
                logger.error(f"Failed to notify admin of feedback: {str(e)}")
        
        logger.info(f"Feedback received: {rating}/5 from user {update.message.from_user.id}")
        
    except Exception as e:
        logger.error(f"Error in feedback command: {str(e)}")
        update.message.reply_text("Sorry, something went wrong while processing your feedback. Please try again.")

def view_messages(update: Update, context: CallbackContext):
    """Admin command to view all logged messages"""
    try:
        if update.message.from_user.id != OWNER_ID:
            update.message.reply_text("❌ You are not authorized to view messages.")
            return

        if not message_log:
            update.message.reply_text("📭 No messages logged yet.")
            return
        
        # Send messages in chunks to avoid hitting Telegram's message length limit
        for i, msg in enumerate(message_log, 1):
            message_type = msg.get('message_type', 'text')
            file_info = msg.get('file_info')
            
            message_text = (
                f"📨 Message #{i}\n"
                f"👤 From: @{msg['username']} ({msg['user_name']})\n"
                f"🆔 User ID: {msg['user_id']}\n"
                f"💬 Message: {msg['message']}\n"
            )
            
            if message_type == 'file' and file_info:
                file_details = f"📎 File Type: {file_info.get('type', 'unknown').title()}\n"
                if file_info.get('file_name'):
                    file_details += f"📄 File Name: {file_info['file_name']}\n"
                if file_info.get('file_size'):
                    file_details += f"📏 File Size: {file_info['file_size']} bytes\n"
                message_text += file_details
            
            message_text += (
                f"⏰ Time: {msg.get('timestamp', 'N/A')}\n"
                f"{'='*30}"
            )
            update.message.reply_text(message_text)
            
        logger.info(f"Admin viewed {len(message_log)} messages")
        
    except Exception as e:
        logger.error(f"Error in view_messages command: {str(e)}")
        update.message.reply_text("Sorry, something went wrong while retrieving messages.")

def reply_to_user(update: Update, context: CallbackContext):
    """Admin command to reply to specific users by ID or username"""
    try:
        if update.message.from_user.id != OWNER_ID:
            update.message.reply_text("❌ You are not authorized to send replies.")
            return

        if len(context.args) < 2:
            update.message.reply_text(
                "Usage:\n"
                "/reply <user_id> <your reply>\n"
                "/reply @<username> <your reply>\n\n"
                "Examples:\n"
                "/reply 123456789 Thank you for your question!\n"
                "/reply @john Hello John!\n\n"
                "💡 Tip: You can also reply with a file by using /reply command as caption!"
            )
            return

        target = context.args[0]
        reply_message = ' '.join(context.args[1:])
        target_user_id = None
        target_display_name = ""

        # Check if target is a username (starts with @)
        if target.startswith('@'):
            username_to_find = target[1:].lower()  # Remove @ and make lowercase
            # Search for user by username
            for user_id, user_info in user_registry.items():
                if user_info.get('username') and user_info['username'].lower() == username_to_find:
                    target_user_id = user_id
                    target_display_name = f"@{user_info['username']} ({user_info['user_name']})"
                    break
            
            if target_user_id is None:
                update.message.reply_text(f"❌ Username {target} not found in user registry.")
                return
        else:
            # Target is user ID
            try:
                target_user_id = int(target)
                if target_user_id in user_registry:
                    user_info = user_registry[target_user_id]
                    target_display_name = f"{user_info['user_name']} (ID: {target_user_id})"
                else:
                    target_display_name = f"User ID: {target_user_id}"
            except ValueError:
                update.message.reply_text("❌ Invalid format. Use numeric user ID or @username.")
                return

        # Send the reply to the user
        try:
            context.bot.send_message(
                chat_id=target_user_id, 
                text=f"📧 Reply from Admin:\n\n{reply_message}"
            )
            update.message.reply_text(f"✅ Reply sent successfully to {target_display_name}")
            logger.info(f"Admin replied to user {target_user_id}")
        except Exception as e:
            error_message = f"❌ Failed to send reply to {target_display_name}: {str(e)}"
            update.message.reply_text(error_message)
            logger.error(error_message)
            
    except Exception as e:
        logger.error(f"Error in reply command: {str(e)}")
        update.message.reply_text("Sorry, something went wrong while sending the reply.")

def reply_with_file(update: Update, context: CallbackContext):
    """Admin command to reply to users with files"""
    try:
        if update.message.from_user.id != OWNER_ID:
            update.message.reply_text("❌ You are not authorized to send replies.")
            return

        # Get caption which should contain the reply command
        caption = update.message.caption or ""
        if not caption.strip().startswith('/reply'):
            update.message.reply_text("❌ Please use /reply command as caption when sending files.\n\nExample: Send a photo with caption '/reply 123456789 Here's your requested file!'")
            return

        # Parse the caption like a normal reply command
        caption_parts = caption.strip().split()
        if len(caption_parts) < 3:
            update.message.reply_text("❌ Usage: Send file with caption '/reply <user_id> <message>'\n\nExample: '/reply 123456789 Here's the document you requested!'")
            return

        # Get target and message
        target = caption_parts[1]
        reply_message = ' '.join(caption_parts[2:])
        target_user_id = None
        target_display_name = ""

        # Check if target is a username (starts with @)
        if target.startswith('@'):
            username_to_find = target[1:].lower()
            for user_id, user_info in user_registry.items():
                if user_info.get('username') and user_info['username'].lower() == username_to_find:
                    target_user_id = user_id
                    target_display_name = f"@{user_info['username']} ({user_info['user_name']})"
                    break
            
            if target_user_id is None:
                update.message.reply_text(f"❌ Username {target} not found in user registry.")
                return
        else:
            try:
                target_user_id = int(target)
                if target_user_id in user_registry:
                    user_info = user_registry[target_user_id]
                    target_display_name = f"{user_info['user_name']} (ID: {target_user_id})"
                else:
                    target_display_name = f"User ID: {target_user_id}"
            except ValueError:
                update.message.reply_text("❌ Invalid format. Use numeric user ID or @username.")
                return

        # Send text message first
        context.bot.send_message(
            chat_id=target_user_id,
            text=f"📧 Reply from Admin:\n\n{reply_message}"
        )

        # Forward the file to the user
        context.bot.forward_message(
            chat_id=target_user_id,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id
        )

        update.message.reply_text(f"✅ Reply with file sent successfully to {target_display_name}")
        logger.info(f"Admin replied with file to user {target_user_id}")

    except Exception as e:
        error_message = f"❌ Failed to send reply with file: {str(e)}"
        update.message.reply_text(error_message)
        logger.error(error_message)

def view_feedback(update: Update, context: CallbackContext):
    """Admin command to view all feedback"""
    try:
        if update.message.from_user.id != OWNER_ID:
            update.message.reply_text("❌ You are not authorized to view feedback.")
            return

        if not feedback_log:
            update.message.reply_text("📭 No feedback received yet.")
            return
        
        # Calculate average rating
        total_rating = sum(fb['rating'] for fb in feedback_log)
        avg_rating = total_rating / len(feedback_log)
        
        summary = (
            f"📊 Feedback Summary\n"
            f"Total feedback: {len(feedback_log)}\n"
            f"Average rating: {avg_rating:.1f}/5\n"
            f"{'='*30}\n\n"
        )
        update.message.reply_text(summary)
        
        # Send individual feedback entries
        for i, fb in enumerate(feedback_log, 1):
            stars = "⭐" * fb['rating']
            feedback_text = (
                f"📝 Feedback #{i}\n"
                f"👤 From: {fb['user_name']}\n"
                f"⭐ Rating: {stars} ({fb['rating']}/5)\n"
                f"💬 Comment: {fb['comment']}\n"
                f"⏰ Time: {fb.get('timestamp', 'N/A')}\n"
                f"{'='*30}"
            )
            update.message.reply_text(feedback_text)
            
        logger.info(f"Admin viewed {len(feedback_log)} feedback entries")
        
    except Exception as e:
        logger.error(f"Error in view_feedback command: {str(e)}")
        update.message.reply_text("Sorry, something went wrong while retrieving feedback.")

def broadcast(update: Update, context: CallbackContext):
    """Admin command to broadcast message to all users"""
    try:
        if update.message.from_user.id != OWNER_ID:
            update.message.reply_text("❌ You are not authorized to send broadcasts.")
            return

        if len(context.args) < 1:
            update.message.reply_text(
                "Usage: /broadcast <your message>\n\n"
                "Examples:\n"
                "/broadcast Hello everyone! This is an important update.\n\n"
                "💡 Tip: You can also broadcast a file by using /broadcast as caption!"
            )
            return

        broadcast_message = ' '.join(context.args)
        
        if not user_registry:
            update.message.reply_text("❌ No users found to broadcast to.")
            return

        success_count = 0
        failed_count = 0
        
        # Send message to all registered users
        for user_id in user_registry.keys():
            try:
                context.bot.send_message(
                    chat_id=user_id,
                    text=f"📢 Broadcast Message:\n\n{broadcast_message}"
                )
                success_count += 1
            except Exception as e:
                failed_count += 1
                logger.warning(f"Failed to send broadcast to user {user_id}: {str(e)}")

        # Send summary to admin
        summary = (
            f"📊 Broadcast Summary:\n\n"
            f"✅ Successfully sent: {success_count}\n"
            f"❌ Failed: {failed_count}\n"
            f"👥 Total users: {len(user_registry)}"
        )
        update.message.reply_text(summary)
        logger.info(f"Broadcast sent to {success_count}/{len(user_registry)} users")
        
    except Exception as e:
        logger.error(f"Error in broadcast command: {str(e)}")
        update.message.reply_text("Sorry, something went wrong while sending the broadcast.")

def broadcast_with_file(update: Update, context: CallbackContext):
    """Admin command to broadcast files to all users"""
    try:
        if update.message.from_user.id != OWNER_ID:
            update.message.reply_text("❌ You are not authorized to send broadcasts.")
            return

        # Get caption which should contain the broadcast command
        caption = update.message.caption or ""
        if not caption.strip().startswith('/broadcast'):
            update.message.reply_text("❌ Please use /broadcast command as caption when sending files.\n\nExample: Send a photo with caption '/broadcast Check out this image!'")
            return

        # Parse the caption like a normal broadcast command
        caption_parts = caption.strip().split()
        if len(caption_parts) < 2:
            update.message.reply_text("❌ Usage: Send file with caption '/broadcast <message>'\n\nExample: '/broadcast Here's an important document for everyone!'")
            return

        # Remove '/broadcast' and get the message
        broadcast_message = ' '.join(caption_parts[1:])
        
        if not user_registry:
            update.message.reply_text("❌ No users found to broadcast to.")
            return

        success_count = 0
        failed_count = 0
        
        # Send message and file to all registered users
        for user_id in user_registry.keys():
            try:
                # Send text message first
                context.bot.send_message(
                    chat_id=user_id,
                    text=f"📢 Broadcast Message:\n\n{broadcast_message}"
                )
                
                # Forward the file
                context.bot.forward_message(
                    chat_id=user_id,
                    from_chat_id=update.message.chat_id,
                    message_id=update.message.message_id
                )
                success_count += 1
            except Exception as e:
                failed_count += 1
                logger.warning(f"Failed to send broadcast with file to user {user_id}: {str(e)}")

        # Send summary to admin
        summary = (
            f"📊 Broadcast with File Summary:\n\n"
            f"✅ Successfully sent: {success_count}\n"
            f"❌ Failed: {failed_count}\n"
            f"👥 Total users: {len(user_registry)}"
        )
        update.message.reply_text(summary)
        logger.info(f"Broadcast with file sent to {success_count}/{len(user_registry)} users")
        
    except Exception as e:
        logger.error(f"Error in broadcast with file command: {str(e)}")
        update.message.reply_text("Sorry, something went wrong while sending the broadcast with file.")

def handle_file_reply(update: Update, context: CallbackContext):
    """Handle files sent as replies to bot messages"""
    try:
        user_id = update.message.from_user.id
        user_name = update.message.from_user.first_name
        username = update.message.from_user.username
        
        # Check if this is a reply to a bot message
        if not update.message.reply_to_message:
            return
            
        # Register/update user in user_registry
        user_registry[user_id] = {
            'user_name': user_name,
            'username': username,
            'last_seen': update.message.date.isoformat()
        }
        
        # Update keep-alive status with current user count
        update_bot_status(users=len(user_registry))
        
        # Get file information
        file_info = {}
        message_type = "file"
        
        if update.message.document:
            file_info = {
                'type': 'document',
                'file_name': update.message.document.file_name,
                'file_size': update.message.document.file_size,
                'mime_type': update.message.document.mime_type
            }
        elif update.message.photo:
            file_info = {
                'type': 'photo',
                'file_size': update.message.photo[-1].file_size
            }
        elif update.message.video:
            file_info = {
                'type': 'video',
                'duration': update.message.video.duration,
                'file_size': update.message.video.file_size
            }
        elif update.message.audio:
            file_info = {
                'type': 'audio',
                'duration': update.message.audio.duration,
                'file_size': update.message.audio.file_size,
                'title': update.message.audio.title
            }
        elif update.message.voice:
            file_info = {
                'type': 'voice',
                'duration': update.message.voice.duration,
                'file_size': update.message.voice.file_size
            }
        
        # Log the message with file info
        message_entry = {
            'user_id': user_id,
            'user_name': user_name,
            'username': username,
            'message': update.message.caption or f"[{file_info.get('type', 'file').upper()} FILE REPLY]",
            'message_type': message_type,
            'file_info': file_info,
            'timestamp': update.message.date.isoformat(),
            'reply_to_bot': True
        }
        message_log.append(message_entry)
        
        # Update keep-alive status with message count
        update_bot_status(messages=len(message_log))
        
        # Forward the file to admin for review
        if update.message.from_user.id != OWNER_ID:
            try:
                context.bot.forward_message(
                    chat_id=OWNER_ID,
                    from_chat_id=update.message.chat_id,
                    message_id=update.message.message_id
                )
                
                # Send notification to admin
                file_type = file_info.get('type', 'file')
                notification = (
                    f"📎 New {file_type} reply from {user_name} (@{username or 'no_username'}):\n"
                    f"👤 User ID: {user_id}\n"
                    f"📝 Caption: {update.message.caption or 'No caption'}\n"
                    f"📅 Time: {update.message.date.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                context.bot.send_message(chat_id=OWNER_ID, text=notification)
                
            except Exception as forward_error:
                logger.error(f"Failed to forward file to admin: {forward_error}")
        
        # Respond to user
        response = f"Thank you for sharing the {file_info.get('type', 'file')}! I've received it and will review it shortly."
        update.message.reply_text(response)
        
        logger.info(f"File reply logged from user {user_name} ({user_id})")
        
    except Exception as e:
        logger.error(f"Error in handle_file_reply: {str(e)}")
        update.message.reply_text("Thank you for sharing the file!")

def stats(update: Update, context: CallbackContext):
    """Admin command to view bot statistics"""
    try:
        if update.message.from_user.id != OWNER_ID:
            update.message.reply_text("❌ You are not authorized to view statistics.")
            return

        stats_text = (
            f"📊 Bot Statistics\n\n"
            f"📨 Total Messages: {len(message_log)}\n"
            f"📝 Total Feedback: {len(feedback_log)}\n"
            f"👥 Registered Users: {len(user_registry)}\n"
        )
        
        if feedback_log:
            avg_rating = sum(fb['rating'] for fb in feedback_log) / len(feedback_log)
            stats_text += f"⭐ Average Rating: {avg_rating:.1f}/5\n"
        
        # Count unique users from messages and feedback
        unique_users = set()
        for msg in message_log:
            unique_users.add(msg['user_id'])
        for fb in feedback_log:
            unique_users.add(fb['user_id'])
        
        stats_text += f"💬 Active Users: {len(unique_users)}"
        
        update.message.reply_text(stats_text)
        logger.info("Admin viewed bot statistics")
        
    except Exception as e:
        logger.error(f"Error in stats command: {str(e)}")
        update.message.reply_text("Sorry, something went wrong while retrieving statistics.")

# Auto-reply system with predefined responses
auto_replies = {
    "hello": "Hi there! 👋 How can I assist you today? Use /help to see available commands.",
    "hi": "Hello! 😊 How can I help you?",
    "bye": "Goodbye! 👋 Have a great day!",
    "goodbye": "See you later! 😊 Take care!",
    "thanks": "You're welcome! 😊 Happy to help!",
    "thank you": "My pleasure! 🙏 Is there anything else I can help you with?",
    "help": "I'm here to help! Use /help to see all available commands. 📋"
}

def auto_reply(update: Update, context: CallbackContext):
    """Handle automatic replies for common messages"""
    try:
        user_id = update.message.from_user.id
        user_name = update.message.from_user.first_name
        username = update.message.from_user.username
        
        # Register/update user in user_registry
        user_registry[user_id] = {
            'user_name': user_name,
            'username': username,
            'last_seen': update.message.date.isoformat()
        }
        
        # Update keep-alive status
        update_bot_status(users=len(user_registry))
        
        user_message = update.message.text.lower().strip()
        
        # Check if message matches any auto-reply keywords
        for keyword, response in auto_replies.items():
            if keyword in user_message:
                update.message.reply_text(response)
                logger.info(f"Auto-reply sent for keyword '{keyword}' to user {update.message.from_user.id}")
                return

        # Default response for unmatched messages
        default_response = (
            "I'm here to help! 🤖\n\n"
            "To ask me a question, use: /ask <your question>\n"
            "For help with commands, use: /help"
        )
        update.message.reply_text(default_response)
        logger.info(f"Default auto-reply sent to user {update.message.from_user.id}")
        
    except Exception as e:
        logger.error(f"Error in auto_reply: {str(e)}")
        # Don't send error message for auto-replies to avoid spam

def error_handler(update: Update, context: CallbackContext):
    """Handle errors caused by Updates"""
    logger.warning(f'Update {update} caused error {context.error}')
    
    # Update status to indicate error handling
    if "Conflict" in str(context.error):
        # Don't change status for conflict errors as they're common during restarts
        pass
    else:
        update_bot_status('error_handled')

def main():
    """Main function to set up and run the Telegram bot"""
    # Validate configuration
    if BOT_TOKEN == 'your_bot_token_here' or not BOT_TOKEN:
        logger.error("BOT_TOKEN not set! Please set the BOT_TOKEN environment variable.")
        print("Error: BOT_TOKEN not configured. Please set the BOT_TOKEN environment variable.")
        return
    
    if OWNER_ID == 0:
        logger.warning("OWNER_ID not set! Admin commands will not work. Please set the OWNER_ID environment variable.")
        print("Warning: OWNER_ID not configured. Admin commands will not work.")
    
    try:
        # Create the Updater and pass it the bot's token
        updater = Updater(BOT_TOKEN, use_context=True)

        # Get the dispatcher to register handlers
        dispatcher = updater.dispatcher

        # Register command handlers
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("help", help_command))
        dispatcher.add_handler(CommandHandler("ask", ask))
        dispatcher.add_handler(CommandHandler("feedback", feedback))
        dispatcher.add_handler(CommandHandler("view_messages", view_messages))
        dispatcher.add_handler(CommandHandler("reply", reply_to_user))
        dispatcher.add_handler(CommandHandler("broadcast", broadcast))
        dispatcher.add_handler(CommandHandler("view_feedback", view_feedback))
        dispatcher.add_handler(CommandHandler("stats", stats))

        # Register message handlers for files with commands (caption-based)
        dispatcher.add_handler(MessageHandler(
            (Filters.document | Filters.photo | Filters.video | Filters.audio | Filters.voice) & 
            Filters.caption_regex(r'^/ask'), ask))
        
        dispatcher.add_handler(MessageHandler(
            (Filters.document | Filters.photo | Filters.video | Filters.audio | Filters.voice) & 
            Filters.caption_regex(r'^/reply'), reply_with_file))
        
        dispatcher.add_handler(MessageHandler(
            (Filters.document | Filters.photo | Filters.video | Filters.audio | Filters.voice) & 
            Filters.caption_regex(r'^/broadcast'), broadcast_with_file))
        
        # Register message handlers for files without commands (reply-to-message based)
        dispatcher.add_handler(MessageHandler(
            (Filters.document | Filters.photo | Filters.video | Filters.audio | Filters.voice) & 
            Filters.reply, handle_file_reply))
        
        # Register message handler for automatic replies (non-command messages)
        dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, auto_reply))
        
        # Register error handler
        dispatcher.add_error_handler(error_handler)

        logger.info("Bot handlers registered successfully")
        print("🤖 Telegram bot is starting...")
        print(f"🔑 Bot token configured: {'✅' if BOT_TOKEN != 'your_bot_token_here' else '❌'}")
        print(f"👨‍💼 Admin configured: {'✅' if OWNER_ID != 0 else '❌'}")
        
        # Start the bot
        updater.start_polling()
        logger.info("Bot started successfully! Polling for updates...")
        print("✅ Bot is now running! Press Ctrl+C to stop.")
        
        # Mark bot as ready in keep-alive system
        set_bot_ready()
        
        # Run the bot until you press Ctrl-C
        updater.idle()
        
    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}")
        print(f"❌ Failed to start bot: {str(e)}")
        update_bot_status('error')

if __name__ == '__main__':
    # Start keep-alive server first
    print("🔄 Initializing keep-alive system...")
    keep_alive_thread = keep_alive()
    
    # Start heartbeat system
    print("💓 Starting heartbeat system...")
    heartbeat_thread = heartbeat()
    
    # Give servers a moment to initialize
    time.sleep(1)
    
    # Start the main bot
    print("🤖 Starting Telegram bot...")
    main()
