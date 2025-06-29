"""
Sprinter Exceptions Management
Handles special cases for capacity planning: customer delegates, vacations, on-call duties
"""

import json
import os
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum


class ExceptionType(Enum):
    CUSTOMER_DELEGATE = "customer_delegate"
    VACATION = "vacation"
    ON_CALL = "on_call"


class SprinterExceptions:
    def __init__(self, storage_file: str = '.sprinter_exceptions.json'):
        """
        Initialize sprinter exceptions management
        
        Args:
            storage_file: Path to the exceptions storage file
        """
        self.storage_file = storage_file
        self.default_settings = {
            'customer_delegate_min_sp': 2,  # Minimum SP for customer delegates
            'on_call_reduction_sp': 3,      # SP reduction for on-call sprinters
            'vacation_reduction_per_day': 0.2  # SP reduction per vacation day (20% per day)
        }
    
    def save_exceptions(self, sprint_number: int, exceptions: Dict) -> bool:
        """
        Save exceptions for a specific sprint
        
        Args:
            sprint_number: Sprint number
            exceptions: Dictionary containing exceptions data
            
        Returns:
            bool: True if saved successfully
        """
        try:
            # Load existing data
            data = self._load_data()
            
            # Update sprint exceptions
            data['sprints'][str(sprint_number)] = {
                'exceptions': exceptions,
                'updated_at': datetime.now().isoformat()
            }
            
            # Save to file
            with open(self.storage_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"✅ Sprint {sprint_number} exception'ları kaydedildi")
            return True
            
        except Exception as e:
            print(f"❌ Exception kaydetme hatası: {e}")
            return False
    
    def load_exceptions(self, sprint_number: int) -> Optional[Dict]:
        """
        Load exceptions for a specific sprint
        
        Args:
            sprint_number: Sprint number
            
        Returns:
            Dict containing exceptions or None if not found
        """
        try:
            data = self._load_data()
            sprint_data = data['sprints'].get(str(sprint_number))
            
            if sprint_data:
                return sprint_data['exceptions']
            return {}
            
        except Exception as e:
            print(f"❌ Exception yükleme hatası: {e}")
            return {}
    
    def get_settings(self) -> Dict:
        """
        Get current exception settings
        
        Returns:
            Dict containing settings
        """
        try:
            data = self._load_data()
            return data.get('settings', self.default_settings)
        except Exception as e:
            print(f"❌ Settings yükleme hatası: {e}")
            return self.default_settings
    
    def update_settings(self, settings: Dict) -> bool:
        """
        Update exception settings
        
        Args:
            settings: New settings dictionary
            
        Returns:
            bool: True if updated successfully
        """
        try:
            data = self._load_data()
            data['settings'] = {**self.default_settings, **settings}
            data['settings_updated_at'] = datetime.now().isoformat()
            
            with open(self.storage_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            print("✅ Exception settings güncellendi")
            return True
            
        except Exception as e:
            print(f"❌ Settings güncelleme hatası: {e}")
            return False
    
    def calculate_adjusted_capacity(self, sprinter_id: str, base_capacity: float, 
                                  sprint_number: int, team_average_sp: float = 0) -> Dict:
        """
        Calculate adjusted capacity for a sprinter based on exceptions
        
        Args:
            sprinter_id: Sprinter identifier
            base_capacity: Base story point capacity
            sprint_number: Current sprint number
            team_average_sp: Team average SP (for on-call calculation)
            
        Returns:
            Dict containing adjusted capacity and explanation
        """
        try:
            exceptions = self.load_exceptions(sprint_number)
            settings = self.get_settings()
            
            if not exceptions or sprinter_id not in exceptions:
                return {
                    'adjusted_sp': base_capacity,
                    'original_sp': base_capacity,
                    'adjustments': [],
                    'explanation': 'Exception yok'
                }
            
            sprinter_exceptions = exceptions[sprinter_id]
            adjusted_sp = base_capacity
            adjustments = []
            
            # Customer Delegate - Minimum SP
            if sprinter_exceptions.get('customer_delegate', False):
                min_sp = settings['customer_delegate_min_sp']
                if adjusted_sp > min_sp:
                    adjusted_sp = min_sp
                    adjustments.append(f"Müşteri dedikesi: {min_sp} SP'ye düşürüldü")
            
            # Vacation - Day-based reduction
            vacation_days = sprinter_exceptions.get('vacation_days', 0)
            if vacation_days > 0:
                reduction_rate = settings['vacation_reduction_per_day']
                reduction_amount = base_capacity * (vacation_days * reduction_rate)
                adjusted_sp = max(0, adjusted_sp - reduction_amount)
                adjustments.append(f"İzin ({vacation_days} gün): -{reduction_amount:.1f} SP")
            
            # On-call - Fixed reduction or percentage of team average
            if sprinter_exceptions.get('on_call', False):
                if team_average_sp > 0:
                    # Use team average based reduction
                    reduction = settings['on_call_reduction_sp']
                    adjusted_sp = max(0, adjusted_sp - reduction)
                    adjustments.append(f"Nöbetçi: -{reduction} SP (takım ortalaması: {team_average_sp:.1f})")
                else:
                    # Fallback to fixed reduction
                    reduction = settings['on_call_reduction_sp']
                    adjusted_sp = max(0, adjusted_sp - reduction)
                    adjustments.append(f"Nöbetçi: -{reduction} SP")
            
            explanation = "; ".join(adjustments) if adjustments else "Exception yok"
            
            return {
                'adjusted_sp': round(adjusted_sp, 1),
                'original_sp': base_capacity,
                'adjustments': adjustments,
                'explanation': explanation
            }
            
        except Exception as e:
            print(f"❌ Kapasite hesaplama hatası: {e}")
            return {
                'adjusted_sp': base_capacity,
                'original_sp': base_capacity,
                'adjustments': [],
                'explanation': f'Hesaplama hatası: {str(e)}'
            }
    
    def _load_data(self) -> Dict:
        """Load data from storage file"""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r') as f:
                    data = json.load(f)
                    
                # Ensure structure exists
                if 'sprints' not in data:
                    data['sprints'] = {}
                if 'settings' not in data:
                    data['settings'] = self.default_settings
                    
                return data
            else:
                return {
                    'sprints': {},
                    'settings': self.default_settings,
                    'created_at': datetime.now().isoformat()
                }
        except Exception as e:
            print(f"❌ Data yükleme hatası: {e}")
            return {
                'sprints': {},
                'settings': self.default_settings,
                'created_at': datetime.now().isoformat()
            }
    
    def get_all_sprinters_from_history(self) -> List[str]:
        """
        Get all sprinter IDs from historical data
        
        Returns:
            List of sprinter IDs
        """
        try:
            data = self._load_data()
            sprinters = set()
            
            for sprint_data in data['sprints'].values():
                if 'exceptions' in sprint_data:
                    sprinters.update(sprint_data['exceptions'].keys())
            
            return sorted(list(sprinters))
            
        except Exception as e:
            print(f"❌ Sprinter listesi alma hatası: {e}")
            return []
    
    def clear_sprint_exceptions(self, sprint_number: int) -> bool:
        """
        Clear exceptions for a specific sprint
        
        Args:
            sprint_number: Sprint number
            
        Returns:
            bool: True if cleared successfully
        """
        try:
            data = self._load_data()
            
            if str(sprint_number) in data['sprints']:
                del data['sprints'][str(sprint_number)]
                
                with open(self.storage_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                print(f"✅ Sprint {sprint_number} exception'ları temizlendi")
                return True
            else:
                print(f"⚠️ Sprint {sprint_number} için exception bulunamadı")
                return True
                
        except Exception as e:
            print(f"❌ Exception temizleme hatası: {e}")
            return False