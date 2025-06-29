"""
Token Storage Module
Handles persistent storage of Trello authentication tokens
"""

import json
import os
from typing import Dict, Optional
from datetime import datetime


class TokenStorage:
    def __init__(self, storage_file: str = '.trello_tokens.json'):
        """
        Initialize token storage
        
        Args:
            storage_file: Path to the token storage file
        """
        self.storage_file = storage_file
    
    def save_tokens(self, api_key: str, access_token: str, access_token_secret: str, 
                   board_id: Optional[str] = None) -> bool:
        """
        Save authentication tokens to storage
        
        Args:
            api_key: Trello API key
            access_token: OAuth access token
            access_token_secret: OAuth access token secret
            board_id: Optional board ID
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        try:
            token_data = {
                'api_key': api_key,
                'access_token': access_token,
                'access_token_secret': access_token_secret,
                'board_id': board_id,
                'saved_at': datetime.now().isoformat()
            }
            
            with open(self.storage_file, 'w') as f:
                json.dump(token_data, f, indent=2)
            
            print(f"✅ Token'lar başarıyla kaydedildi: {self.storage_file}")
            return True
            
        except Exception as e:
            print(f"❌ Token kaydetme hatası: {e}")
            return False
    
    def load_tokens(self) -> Optional[Dict[str, str]]:
        """
        Load authentication tokens from storage
        
        Returns:
            Dict containing tokens if found, None otherwise
        """
        try:
            if not os.path.exists(self.storage_file):
                print(f"📂 Token dosyası bulunamadı: {self.storage_file}")
                return None
            
            with open(self.storage_file, 'r') as f:
                token_data = json.load(f)
            
            # Check if required fields exist
            required_fields = ['api_key', 'access_token', 'access_token_secret']
            if not all(field in token_data for field in required_fields):
                print("⚠️ Token dosyası eksik alan içeriyor")
                return None
            
            print(f"✅ Token'lar başarıyla yüklendi: {self.storage_file}")
            return token_data
            
        except Exception as e:
            print(f"❌ Token yükleme hatası: {e}")
            return None
    
    def update_board_id(self, board_id: str) -> bool:
        """
        Update board ID in existing token storage
        
        Args:
            board_id: Board ID to update
            
        Returns:
            bool: True if updated successfully, False otherwise
        """
        try:
            token_data = self.load_tokens()
            if not token_data:
                print("⚠️ Güncellenecek token bulunamadı")
                return False
            
            token_data['board_id'] = board_id
            token_data['updated_at'] = datetime.now().isoformat()
            
            with open(self.storage_file, 'w') as f:
                json.dump(token_data, f, indent=2)
            
            print(f"✅ Board ID güncellendi: {board_id}")
            return True
            
        except Exception as e:
            print(f"❌ Board ID güncelleme hatası: {e}")
            return False
    
    def clear_tokens(self) -> bool:
        """
        Clear stored tokens
        
        Returns:
            bool: True if cleared successfully, False otherwise
        """
        try:
            if os.path.exists(self.storage_file):
                os.remove(self.storage_file)
                print(f"✅ Token'lar temizlendi: {self.storage_file}")
            else:
                print(f"📂 Temizlenecek token dosyası bulunamadı: {self.storage_file}")
            return True
            
        except Exception as e:
            print(f"❌ Token temizleme hatası: {e}")
            return False
    
    def has_tokens(self) -> bool:
        """
        Check if valid tokens exist
        
        Returns:
            bool: True if valid tokens exist, False otherwise
        """
        token_data = self.load_tokens()
        return token_data is not None
    
    def get_token_info(self) -> Optional[Dict[str, str]]:
        """
        Get token information for display purposes
        
        Returns:
            Dict containing non-sensitive token info, None if no tokens
        """
        try:
            token_data = self.load_tokens()
            if not token_data:
                return None
            
            return {
                'has_api_key': bool(token_data.get('api_key')),
                'has_access_token': bool(token_data.get('access_token')),
                'has_board_id': bool(token_data.get('board_id')),
                'saved_at': token_data.get('saved_at'),
                'updated_at': token_data.get('updated_at')
            }
            
        except Exception as e:
            print(f"❌ Token bilgi alma hatası: {e}")
            return None