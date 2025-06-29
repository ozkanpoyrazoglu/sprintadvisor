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
            # Target and Base Settings
            'target_sp_per_person': 21,     # Target SP for 100% utilization
            'sprint_working_days': 5,       # Default working days per sprint
            'min_sp_threshold': 3,          # Minimum SP to assign (avoid very low assignments)
            'target_push_factor': 0.7,     # How aggressively to push towards target (0.5-1.0)
            
            # Exception Settings
            'customer_delegate_min_sp': 2,  # Minimum SP for customer delegates
            'customer_delegate_days': 5,    # Default customer delegate duration (days)
            'on_call_reduction_sp': 3,      # SP reduction for on-call sprinters
            'vacation_reduction_per_day': 0.2,  # SP reduction per vacation day (20% per day)
            
            # Zero Prevention Settings
            'min_sp_unless_fully_unavailable': 2,  # Never go below this unless 100% unavailable
            'full_unavailability_threshold': 1.0,  # When 100% of sprint is exceptions (1.0 = full sprint)
            
            # Algorithm Settings
            'capacity_growth_limit': 1.5,   # Maximum growth factor per sprint (50% increase max)
            'low_performer_boost': 2.0,     # Boost factor for consistently low performers
            'team_balance_factor': 0.3      # How much to consider team balance (0.0-1.0)
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
            saved_settings = data.get('settings', {})
            # Always merge with defaults to ensure all keys are present
            return {**self.default_settings, **saved_settings}
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
                                  sprint_number: int, team_average_sp: float = 0,
                                  sprint_working_days: int = None) -> Dict:
        """
        Calculate adjusted capacity for a sprinter based on exceptions
        
        Args:
            sprinter_id: Sprinter identifier
            base_capacity: Base story point capacity
            sprint_number: Current sprint number
            team_average_sp: Team average SP (for on-call calculation)
            sprint_working_days: Working days in sprint (for holiday adjustments)
            
        Returns:
            Dict containing adjusted capacity and explanation
        """
        try:
            exceptions = self.load_exceptions(sprint_number)
            settings = self.get_settings()
            
            # Use provided working days or default
            working_days = sprint_working_days or settings.get('sprint_working_days', 5)
            
            if not exceptions or sprinter_id not in exceptions:
                # Apply working days adjustment even without exceptions
                default_working_days = settings.get('sprint_working_days', 5)
                if working_days != default_working_days:
                    working_day_factor = working_days / default_working_days
                    adjusted_sp = base_capacity * working_day_factor
                    return {
                        'adjusted_sp': round(adjusted_sp, 1),
                        'original_sp': base_capacity,
                        'adjustments': [f"Çalışma günü ayarı: {working_days} gün"],
                        'explanation': f'Çalışma günü ayarı: {working_days} gün'
                    }
                
                return {
                    'adjusted_sp': base_capacity,
                    'original_sp': base_capacity,
                    'adjustments': [],
                    'explanation': 'Exception yok'
                }
            
            sprinter_exceptions = exceptions[sprinter_id]
            adjusted_sp = base_capacity
            adjustments = []
            
            # Working days adjustment (applied first)
            default_working_days = settings.get('sprint_working_days', 5)
            if working_days != default_working_days:
                working_day_factor = working_days / default_working_days
                adjusted_sp = adjusted_sp * working_day_factor
                adjustments.append(f"Çalışma günü ayarı: {working_days} gün")
            
            # Customer Delegate - Duration-based calculation
            if sprinter_exceptions.get('customer_delegate', False):
                try:
                    delegate_days = sprinter_exceptions.get('customer_delegate_days', settings.get('customer_delegate_days', 5))
                    
                    if delegate_days >= working_days:
                        # Full sprint dedication
                        min_sp = settings.get('customer_delegate_min_sp', 2)
                        adjusted_sp = min_sp
                        adjustments.append(f"Müşteri dedikesi (tam sprint): {min_sp} SP")
                    else:
                        # Partial dedication
                        dedication_factor = delegate_days / working_days
                        remaining_factor = 1 - dedication_factor
                        partial_sp = max(settings.get('customer_delegate_min_sp', 2), adjusted_sp * remaining_factor)
                        adjusted_sp = partial_sp
                        adjustments.append(f"Müşteri dedikesi ({delegate_days}/{working_days} gün): {partial_sp:.1f} SP")
                except Exception as customer_delegate_error:
                    print(f"⚠️ Customer delegate hesaplama hatası: {customer_delegate_error}")
                    # Fallback to simple minimum SP
                    min_sp = settings.get('customer_delegate_min_sp', 2)
                    adjusted_sp = min_sp
                    adjustments.append(f"Müşteri dedikesi (fallback): {min_sp} SP")
            
            # Vacation - Day-based reduction
            vacation_days = sprinter_exceptions.get('vacation_days', 0)
            if vacation_days > 0:
                try:
                    vacation_factor = max(0, (working_days - vacation_days) / working_days)
                    pre_vacation_sp = adjusted_sp
                    adjusted_sp = adjusted_sp * vacation_factor
                    reduction_amount = pre_vacation_sp - adjusted_sp
                    adjustments.append(f"İzin ({vacation_days}/{working_days} gün): -{reduction_amount:.1f} SP")
                except Exception as vacation_error:
                    print(f"⚠️ Vacation hesaplama hatası: {vacation_error}")
                    adjustments.append(f"İzin hesaplama hatası")
            
            # On-call - Fixed reduction
            if sprinter_exceptions.get('on_call', False):
                try:
                    reduction = settings.get('on_call_reduction_sp', 3)
                    adjusted_sp = max(0, adjusted_sp - reduction)
                    adjustments.append(f"Nöbetçi: -{reduction} SP")
                except Exception as oncall_error:
                    print(f"⚠️ On-call hesaplama hatası: {oncall_error}")
                    adjustments.append(f"Nöbetçi hesaplama hatası")
            
            # Prevent 0 SP unless fully unavailable
            try:
                # Calculate total unavailability factor
                total_unavailable_days = 0
                
                # Count vacation days
                if vacation_days > 0:
                    total_unavailable_days += vacation_days
                
                # Count customer delegate days (if full dedication)
                if sprinter_exceptions.get('customer_delegate', False):
                    delegate_days = sprinter_exceptions.get('customer_delegate_days', settings.get('customer_delegate_days', 5))
                    if delegate_days >= working_days:
                        total_unavailable_days += working_days  # Full sprint dedication
                    else:
                        total_unavailable_days += delegate_days  # Partial dedication
                
                # Calculate unavailability ratio
                unavailability_ratio = total_unavailable_days / working_days
                full_threshold = settings.get('full_unavailability_threshold', 1.0)
                
                # If not fully unavailable, enforce minimum SP
                if unavailability_ratio < full_threshold:
                    min_sp_unless_unavailable = settings.get('min_sp_unless_fully_unavailable', 2)
                    if adjusted_sp < min_sp_unless_unavailable:
                        adjusted_sp = min_sp_unless_unavailable
                        adjustments.append(f"0 SP önleme: {min_sp_unless_unavailable} SP (tam müsait değil ama 0 olamaz)")
                else:
                    # Fully unavailable, but still ensure some minimum
                    if adjusted_sp <= 0:
                        min_emergency_sp = 1
                        adjusted_sp = min_emergency_sp
                        adjustments.append(f"Acil durum minimumu: {min_emergency_sp} SP")
                
            except Exception as zero_prevention_error:
                print(f"⚠️ 0 SP önleme hatası: {zero_prevention_error}")
                # Emergency fallback
                if adjusted_sp <= 0:
                    adjusted_sp = 1
                    adjustments.append("Acil durum: 1 SP")
            
            # Ensure normal minimum threshold for reasonable assignments
            try:
                min_threshold = settings.get('min_sp_threshold', 3)
                if adjusted_sp > 0 and adjusted_sp < min_threshold:
                    # Only apply if it's not an exception case (don't override zero prevention)
                    if adjusted_sp >= settings.get('min_sp_unless_fully_unavailable', 2):
                        adjusted_sp = min_threshold
                        adjustments.append(f"Minimum eşik: {min_threshold} SP")
            except Exception as threshold_error:
                print(f"⚠️ Minimum threshold hatası: {threshold_error}")
                # Safe fallback
                if adjusted_sp <= 0:
                    adjusted_sp = 1
            
            explanation = "; ".join(adjustments) if adjustments else "Exception yok"
            
            return {
                'adjusted_sp': round(adjusted_sp, 1),
                'original_sp': base_capacity,
                'adjustments': adjustments,
                'explanation': explanation
            }
            
        except Exception as e:
            print(f"❌ Kapasite hesaplama hatası: {e}")
            print(f"Debug info - sprinter_id: {sprinter_id}, base_capacity: {base_capacity}, sprint_number: {sprint_number}")
            print(f"Debug info - sprint_working_days: {sprint_working_days}, team_average_sp: {team_average_sp}")
            import traceback
            traceback.print_exc()
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
                else:
                    # Migrate existing settings by merging with defaults
                    data['settings'] = {**self.default_settings, **data['settings']}
                    
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