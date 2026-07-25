"""
MongoDB database manager for the bot.
"""

import motor.motor_asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from config import Config
from utils.logger import logger


class DatabaseManager:
    """Manages all database operations."""
    
    _instance = None
    _client = None
    _db = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def initialize(self):
        """Initialize database connection."""
        if self._client is None:
            try:
                self._client = motor.motor_asyncio.AsyncIOMotorClient(
                    Config.MONGODB_URI,
                    serverSelectionTimeoutMS=5000
                )
                self._db = self._client[Config.DATABASE_NAME]
                
                # Test connection
                await self._client.admin.command('ping')
                logger.info("Database connection established successfully")
                
                # Create indexes
                await self._create_indexes()
                
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                raise
    
    async def _create_indexes(self):
        """Create necessary database indexes."""
        try:
            # Warnings collection indexes
            await self._db.warnings.create_index([('guild_id', 1), ('user_id', 1)])
            
            # Tickets collection indexes
            await self._db.tickets.create_index([('guild_id', 1), ('channel_id', 1)])
            
            # Guild settings indexes
            await self._db.guild_settings.create_index('guild_id', unique=True)
            
            # Mod logs indexes
            await self._db.moderation_logs.create_index([('guild_id', 1), ('timestamp', -1)])
            
            logger.info("Database indexes created successfully")
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")
    
    async def close(self):
        """Close database connection."""
        if self._client:
            self._client.close()
            logger.info("Database connection closed")
    
    # Guild Settings Methods
    async def get_guild_settings(self, guild_id: int) -> Dict[str, Any]:
        """Get guild settings, creating defaults if not exists."""
        settings = await self._db.guild_settings.find_one({'guild_id': guild_id})
        
        if not settings:
            from utils.constants import DEFAULT_GUILD_SETTINGS
            settings = DEFAULT_GUILD_SETTINGS.copy()
            settings['guild_id'] = guild_id
            settings['created_at'] = datetime.utcnow()
            await self._db.guild_settings.insert_one(settings)
        
        return settings
    
    async def update_guild_setting(
        self,
        guild_id: int,
        setting: str,
        value: Any
    ) -> bool:
        """Update a specific guild setting."""
        try:
            result = await self._db.guild_settings.update_one(
                {'guild_id': guild_id},
                {
                    '$set': {
                        setting: value,
                        'updated_at': datetime.utcnow()
                    }
                },
                upsert=True
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            logger.error(f"Failed to update guild setting: {e}")
            return False
    
    # Warning Methods
    async def add_warning(
        self,
        guild_id: int,
        user_id: int,
        moderator_id: int,
        reason: str,
        severity: int = 1
    ) -> int:
        """Add a warning and return total warning count."""
        warning = {
            'guild_id': guild_id,
            'user_id': user_id,
            'moderator_id': moderator_id,
            'reason': reason,
            'severity': severity,
            'timestamp': datetime.utcnow()
        }
        
        await self._db.warnings.insert_one(warning)
        
        # Get total warnings
        count = await self._db.warnings.count_documents({
            'guild_id': guild_id,
            'user_id': user_id
        })
        
        return count
    
    async def get_warnings(
        self,
        guild_id: int,
        user_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get warnings for a user."""
        cursor = self._db.warnings.find(
            {'guild_id': guild_id, 'user_id': user_id}
        ).sort('timestamp', -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def remove_warning(
        self,
        guild_id: int,
        user_id: int,
        warning_index: int
    ) -> bool:
        """Remove a specific warning by index."""
        warnings = await self.get_warnings(guild_id, user_id)
        
        if 0 <= warning_index < len(warnings):
            warning_id = warnings[warning_index]['_id']
            result = await self._db.warnings.delete_one({'_id': warning_id})
            return result.deleted_count > 0
        
        return False
    
    async def clear_warnings(self, guild_id: int, user_id: int) -> int:
        """Clear all warnings for a user."""
        result = await self._db.warnings.delete_many({
            'guild_id': guild_id,
            'user_id': user_id
        })
        return result.deleted_count
    
    # Moderation Log Methods
    async def log_moderation_action(
        self,
        guild_id: int,
        moderator_id: int,
        target_id: int,
        action: str,
        reason: str = None,
        duration: str = None,
        details: Dict[str, Any] = None
    ):
        """Log a moderation action."""
        log_entry = {
            'guild_id': guild_id,
            'moderator_id': moderator_id,
            'target_id': target_id,
            'action': action,
            'reason': reason,
            'duration': duration,
            'details': details or {},
            'timestamp': datetime.utcnow()
        }
        
        await self._db.moderation_logs.insert_one(log_entry)
    
    # Security Log Methods
    async def log_security_event(
        self,
        guild_id: int,
        event_type: str,
        details: Dict[str, Any]
    ):
        """Log a security event."""
        log_entry = {
            'guild_id': guild_id,
            'event_type': event_type,
            'details': details,
            'timestamp': datetime.utcnow()
        }
        
        await self._db.security_logs.insert_one(log_entry)
    
    # Ticket Methods
    async def create_ticket(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        category: str,
        priority: int = 0
    ):
        """Create a new ticket."""
        ticket = {
            'guild_id': guild_id,
            'channel_id': channel_id,
            'user_id': user_id,
            'category': category,
            'priority': priority,
            'status': 'open',
            'assigned_to': None,
            'created_at': datetime.utcnow(),
            'closed_at': None,
            'closed_by': None
        }
        
        await self._db.tickets.insert_one(ticket)
    
    async def get_ticket(self, guild_id: int, channel_id: int) -> Optional[Dict[str, Any]]:
        """Get ticket by channel ID."""
        return await self._db.tickets.find_one({
            'guild_id': guild_id,
            'channel_id': channel_id
        })
    
    async def update_ticket_status(
        self,
        guild_id: int,
        channel_id: int,
        status: str,
        closed_by: int = None
    ):
        """Update ticket status."""
        update_data = {'status': status}
        
        if status == 'closed':
            update_data['closed_at'] = datetime.utcnow()
            update_data['closed_by'] = closed_by
        
        await self._db.tickets.update_one(
            {'guild_id': guild_id, 'channel_id': channel_id},
            {'$set': update_data}
        )
    
    # Verification Methods
    async def set_verified(self, guild_id: int, user_id: int):
        """Mark a user as verified."""
        await self._db.verification.update_one(
            {'guild_id': guild_id, 'user_id': user_id},
            {
                '$set': {
                    'verified_at': datetime.utcnow()
                }
            },
            upsert=True
        )
    
    async def is_verified(self, guild_id: int, user_id: int) -> bool:
        """Check if user is verified."""
        result = await self._db.verification.find_one({
            'guild_id': guild_id,
            'user_id': user_id
        })
        return result is not None
    
    # Backup Methods
    async def save_backup(self, guild_id: int, backup_data: Dict[str, Any]):
        """Save a guild backup."""
        backup = {
            'guild_id': guild_id,
            'data': backup_data,
            'created_at': datetime.utcnow()
        }
        
        await self._db.backups.insert_one(backup)
    
    async def get_latest_backup(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get the latest backup for a guild."""
        return await self._db.backups.find_one(
            {'guild_id': guild_id},
            sort=[('created_at', -1)]
        )