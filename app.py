from flask import Flask, render_template, request, jsonify, redirect, session, url_for
import requests
import json
from datetime import datetime, timedelta
import re
from collections import defaultdict
from requests_oauthlib import OAuth1Session
import os
from token_storage import TokenStorage
from sprinter_exceptions import SprinterExceptions

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-2025'  # Gerçek uygulamada güvenli bir key kullanın

# Trello OAuth URLs
REQUEST_TOKEN_URL = "https://trello.com/1/OAuthGetRequestToken"
ACCESS_TOKEN_URL = "https://trello.com/1/OAuthGetAccessToken"
AUTHORIZE_URL = "https://trello.com/1/OAuthAuthorizeToken"

# OAuth ayarları
APP_NAME = "Sprint Planner"
SCOPE = "read"
EXPIRATION = "never"

class TrelloOAuth:
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.callback_url = "http://localhost:8080/callback"
    
    def get_authorization_url(self):
        """OAuth authorization URL'i al"""
        oauth = OAuth1Session(
            self.api_key,
            client_secret=self.api_secret,
            callback_uri=self.callback_url
        )
        
        try:
            # Request token al
            fetch_response = oauth.fetch_request_token(REQUEST_TOKEN_URL)
            
            # Request token'ı session'da sakla
            session['oauth_token'] = fetch_response.get('oauth_token')
            session['oauth_token_secret'] = fetch_response.get('oauth_token_secret')
            
            # Authorization URL oluştur
            authorization_url = oauth.authorization_url(
                AUTHORIZE_URL,
                name=APP_NAME,
                scope=SCOPE,
                expiration=EXPIRATION
            )
            
            return authorization_url
            
        except Exception as e:
            print(f"OAuth authorization URL hatası: {e}")
            return None
    
    def get_access_token(self, oauth_verifier):
        """OAuth verifier ile access token al"""
        oauth = OAuth1Session(
            self.api_key,
            client_secret=self.api_secret,
            resource_owner_key=session.get('oauth_token'),
            resource_owner_secret=session.get('oauth_token_secret'),
            verifier=oauth_verifier
        )
        
        try:
            # Access token al
            oauth_tokens = oauth.fetch_access_token(ACCESS_TOKEN_URL)
            
            return {
                'oauth_token': oauth_tokens.get('oauth_token'),
                'oauth_token_secret': oauth_tokens.get('oauth_token_secret')
            }
            
        except Exception as e:
            print(f"Access token hatası: {e}")
            return None

class TrelloAPI:
    def __init__(self, api_key, oauth_token, oauth_token_secret, board_id):
        self.api_key = api_key
        self.oauth_token = oauth_token
        self.oauth_token_secret = oauth_token_secret
        self.board_id = board_id
        self.base_url = "https://api.trello.com/1"
        
        # OAuth session oluştur
        self.oauth_session = OAuth1Session(
            self.api_key,
            resource_owner_key=self.oauth_token,
            resource_owner_secret=self.oauth_token_secret
        )
    
    def get_board_data(self):
        """Trello board'undan tüm kartları ve listleri çek"""
        url = f"{self.base_url}/boards/{self.board_id}/cards"
        params = {
            'members': 'true',
            'list': 'true',
            'customFieldItems': 'true'
        }
        
        try:
            response = self.oauth_session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Trello API hatası: {e}")
            return []
    
    def get_custom_fields(self):
        """Board'daki custom field tanımlarını çek"""
        url = f"{self.base_url}/boards/{self.board_id}/customFields"
        
        try:
            response = self.oauth_session.get(url)
            response.raise_for_status()
            result = response.json()
            
            if not result:
                print("⚠️ Board'da custom field bulunamadı!")
                return []
                
            print(f"✅ {len(result)} custom field bulundu")
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"Custom field çekerken hata: {e}")
            return []
        except Exception as e:
            print(f"Custom field parse hatası: {e}")
            return []
    
    def get_lists(self):
        """Board'daki tüm listleri çek"""
        url = f"{self.base_url}/boards/{self.board_id}/lists"
        
        try:
            response = self.oauth_session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Liste çekerken hata: {e}")
            return []

class SprintAnalyzer:
    def __init__(self):
        self.story_points_map = {1: 1, 3: 3, 5: 5}
        self.sprint_field_id = None  # SprintNo custom field ID'si
        self.story_point_field_id = None  # StoryPoint custom field ID'si
        self.sprinter_field_id = None  # Sprinter custom field ID'si
        self.sprinter_field_definition = None  # Sprinter field tanımı (dropdown options için)
        
    def find_custom_field_ids(self, custom_fields):
        """SprintNo, StoryPoint ve Sprinter custom field'larının ID'lerini bul"""
        if not custom_fields:
            print("⚠️ Custom fields bulunamadı!")
            return None, None, None
            
        for field in custom_fields:
            if not field or not isinstance(field, dict):
                continue
                
            field_name = field.get('name', '').lower()
            field_type = field.get('type', '')
            
            if field_name == 'sprintno':
                self.sprint_field_id = field['id']
                print(f"✅ SprintNo field bulundu: {field['id']} (tip: {field_type})")
            elif field_name == 'storypoint':
                self.story_point_field_id = field['id']
                print(f"✅ StoryPoint field bulundu: {field['id']} (tip: {field_type})")
            elif field_name == 'sprinter':
                self.sprinter_field_id = field['id']
                self.sprinter_field_definition = field  # Dropdown options için sakla
                print(f"✅ Sprinter field bulundu: {field['id']} (tip: {field_type})")
                
                # Dropdown ise option'ları göster
                if field_type == 'list' and 'options' in field:
                    options = [opt.get('value', {}).get('text', opt.get('text', 'Unknown')) for opt in field.get('options', [])]
                    print(f"📋 Sprinter dropdown seçenekleri: {options}")
        
        return self.sprint_field_id, self.story_point_field_id, self.sprinter_field_id
    
    def extract_sprinter_from_custom_field(self, card):
        """Kartın custom field'ından sprinter ismini çıkar"""
        try:
            if not self.sprinter_field_id or not card or not card.get('customFieldItems'):
                return None
                
            custom_field_items = card.get('customFieldItems', [])
            if not custom_field_items:
                return None
                
            for custom_field_item in custom_field_items:
                if not custom_field_item or not isinstance(custom_field_item, dict):
                    continue
                    
                if custom_field_item.get('idCustomField') == self.sprinter_field_id:
                    # Trello dropdown format: idValue field'ında option ID var
                    id_value = custom_field_item.get('idValue')
                    
                    if id_value:
                        # Option ID'sini isimle eşleştir
                        option_name = self.get_dropdown_option_name(id_value)
                        if option_name:
                            return option_name.strip()
                    
                    # Fallback: value field'ını kontrol et
                    value = custom_field_item.get('value', {})
                    
                    # Değer None ise field var ama seçim yapılmamış
                    if value is None and not id_value:
                        return "FIELD_EMPTY"  # Özel durum işareti
                    
                    if not value:
                        continue
                    
                    # Text field için
                    if 'text' in value and value['text']:
                        return value['text'].strip()
                    
                    # Eski format dropdown/List field için - option ID'si gelir
                    elif 'idListOption' in value and value['idListOption']:
                        option_id = value['idListOption']
                        option_name = self.get_dropdown_option_name(option_id)
                        if option_name:
                            return option_name.strip()
                    
                    # Alternatif dropdown formatı
                    elif 'option' in value and value['option']:
                        if isinstance(value['option'], dict) and 'value' in value['option']:
                            return value['option']['value'].strip()
                        elif isinstance(value['option'], dict) and 'text' in value['option']:
                            return value['option']['text'].strip()
                        elif isinstance(value['option'], str):
                            return value['option'].strip()
            
            # Field kendisi yok
            return None
            
        except Exception as e:
            print(f"⚠️ Sprinter field okuma hatası: {e}")
            return None
    
    def get_dropdown_option_name(self, option_id):
        """Dropdown option ID'sinden option ismini al"""
        try:
            if not hasattr(self, 'sprinter_field_definition') or not self.sprinter_field_definition:
                return None
                
            options = self.sprinter_field_definition.get('options', [])
            for option in options:
                if option.get('id') == option_id:
                    return option.get('value', {}).get('text', option.get('text', ''))
            
            return None
        except Exception as e:
            print(f"⚠️ Dropdown option okuma hatası: {e}")
            return None
    
    def extract_story_points_from_custom_field(self, card):
        """Kartın custom field'ından story point değerini çıkar"""
        try:
            if not self.story_point_field_id or not card or not card.get('customFieldItems'):
                return None
                
            custom_field_items = card.get('customFieldItems', [])
            if not custom_field_items:
                return None
                
            for custom_field_item in custom_field_items:
                if not custom_field_item or not isinstance(custom_field_item, dict):
                    continue
                    
                if custom_field_item.get('idCustomField') == self.story_point_field_id:
                    value = custom_field_item.get('value', {})
                    
                    if not value:
                        continue
                    
                    # Value text, number veya farklı formatlarda olabilir
                    if 'text' in value and value['text']:
                        try:
                            return int(value['text'])
                        except (ValueError, TypeError):
                            pass
                    elif 'number' in value and value['number'] is not None:
                        try:
                            return int(value['number'])
                        except (ValueError, TypeError):
                            pass
                            
            return None
        except Exception as e:
            print(f"⚠️ StoryPoint field okuma hatası: {e}")
            return None
    
    def extract_story_points(self, card_name):
        """Eski metod - kart isminden story point değerini çıkar (fallback)"""
        try:
            if not card_name:
                return 0
                
            # Story point paternleri: (1), (3), (5) şeklinde olabilir
            pattern = r'\(([135])\)'
            match = re.search(pattern, card_name)
            if match:
                return int(match.group(1))
            return 0
        except Exception as e:
            print(f"⚠️ Kart isminden SP okuma hatası: {e}")
            return 0
    
    def extract_sprint_number_from_custom_field(self, card):
        """Kartın custom field'ından sprint numarasını çıkar"""
        try:
            if not self.sprint_field_id or not card or not card.get('customFieldItems'):
                return None
                
            custom_field_items = card.get('customFieldItems', [])
            if not custom_field_items:
                return None
                
            for custom_field_item in custom_field_items:
                if not custom_field_item or not isinstance(custom_field_item, dict):
                    continue
                    
                if custom_field_item.get('idCustomField') == self.sprint_field_id:
                    value = custom_field_item.get('value', {})
                    
                    if not value:
                        continue
                    
                    # Value text, number veya farklı formatlarda olabilir
                    if 'text' in value and value['text']:
                        try:
                            return int(value['text'])
                        except (ValueError, TypeError):
                            pass
                    elif 'number' in value and value['number'] is not None:
                        try:
                            return int(value['number'])
                        except (ValueError, TypeError):
                            pass
                            
            return None
        except Exception as e:
            print(f"⚠️ SprintNo field okuma hatası: {e}")
            return None
    
    def extract_sprint_number(self, card_name):
        """Eski metod - kart isminden sprint numarasını çıkar (fallback)"""
        try:
            if not card_name:
                return None
                
            # Sprint numarası genelde başta olur: "235 - Task Name" gibi
            pattern = r'^(\d{3})'
            match = re.search(pattern, card_name)
            if match:
                return int(match.group(1))
            return None
        except Exception as e:
            print(f"⚠️ Kart isminden sprint no okuma hatası: {e}")
            return None
    
    def get_last_3_sprints(self, cards, archive_list_id, current_sprint_number, custom_fields):
        """ArchiveNew listesindeki son 3 sprintin kartlarını filtrele"""
        # SprintNo, StoryPoint ve Sprinter custom field ID'lerini bul
        sprint_field_id, story_point_field_id, sprinter_field_id = self.find_custom_field_ids(custom_fields)
        
        if not sprint_field_id:
            print("⚠️ SprintNo custom field bulunamadı!")
        if not story_point_field_id:
            print("⚠️ StoryPoint custom field bulunamadı!")
        if not sprinter_field_id:
            print("⚠️ Sprinter custom field bulunamadı!")
        
        archive_cards = [card for card in cards if card.get('idList') == archive_list_id]
        
        # Son 3 sprintin numaralarını hesapla
        last_3_sprints = [current_sprint_number - 3, current_sprint_number - 2, current_sprint_number - 1]
        
        print(f"📊 Analiz edilecek sprintler: {last_3_sprints}")
        
        # Bu sprintlere ait kartları filtrele
        filtered_cards = []
        found_sprints = set()
        
        for card in archive_cards:
            sprint_num = self.extract_sprint_number_from_custom_field(card)
            
            # Fallback: Eğer custom field'dan alınamadıysa kart isminden dene
            if sprint_num is None:
                sprint_num = self.extract_sprint_number(card['name'])
            
            if sprint_num in last_3_sprints:
                filtered_cards.append(card)
                found_sprints.add(sprint_num)
        
        print(f"📈 Bulunan sprintler: {sorted(found_sprints)}")
        print(f"🎯 Toplam kart sayısı: {len(filtered_cards)}")
        
        return filtered_cards, sorted(found_sprints)
    
    def analyze_member_performance(self, cards):
        """Üyelerin geçmiş performansını analiz et"""
        member_stats = defaultdict(lambda: {
            'total_assigned': 0,
            'total_completed': 0,
            'completion_rate': 0,
            'avg_sp_per_sprint': 0,
            'sprints_participated': set()
        })
        
        if not cards:
            print("⚠️ Analiz edilecek kart bulunamadı!")
            return dict(member_stats)
        
        cards_processed = 0
        cards_with_sp = 0
        cards_with_sprinter = 0
        cards_with_empty_sprinter = 0
        debug_sample_count = 0
        
        # Debug için field ID'leri göster
        print(f"🔍 Debug Field ID'ler:")
        print(f"   SprintNo ID: {self.sprint_field_id}")
        print(f"   StoryPoint ID: {self.story_point_field_id}")
        print(f"   Sprinter ID: {self.sprinter_field_id}")
        
        # Sprinter field definition'ını göster
        if hasattr(self, 'sprinter_field_definition') and self.sprinter_field_definition:
            print(f"🔍 Sprinter Field Definition:")
            print(f"   Type: {self.sprinter_field_definition.get('type')}")
            options = self.sprinter_field_definition.get('options', [])
            for i, option in enumerate(options):
                option_id = option.get('id')
                option_text = option.get('value', {}).get('text', option.get('text', 'Unknown'))
                print(f"   Option {i+1}: ID={option_id}, Text={option_text}")
        
        for card in cards:
            if not card or not isinstance(card, dict):
                continue
                
            cards_processed += 1
            
            # İlk 5 kart için TÜM custom field'ları detaylı debug et
            if debug_sample_count < 5:
                card_name = card.get('name', 'Unknown')[:30]
                custom_field_items = card.get('customFieldItems', [])
                print(f"\n🔍 Debug Kart {debug_sample_count + 1}: {card_name}")
                print(f"   Custom Field sayısı: {len(custom_field_items)}")
                
                for i, item in enumerate(custom_field_items):
                    field_id = item.get('idCustomField', 'Unknown')
                    value = item.get('value', {})
                    print(f"   Field {i+1} ID: {field_id}")
                    print(f"   Field {i+1} Value (raw): {item}")  # Ham veriyi göster
                    print(f"   Field {i+1} Value: {value}")
                    
                    # Hangi field olduğunu belirle
                    if field_id == self.sprinter_field_id:
                        print(f"   ^^^ Bu SPRINTER field")
                        # Sprinter field için ek debug
                        id_value = item.get('idValue')
                        if id_value:
                            print(f"   >>> SPRINTER idValue: {id_value}")
                            option_name = self.get_dropdown_option_name(id_value)
                            print(f"   >>> SPRINTER option name: {option_name}")
                        elif value is None and not id_value:
                            print(f"   >>> SPRINTER değeri NULL VE idValue yok - dropdown seçimi yapılmamış")
                        elif isinstance(value, dict):
                            if 'idListOption' in value:
                                option_id = value['idListOption']
                                print(f"   >>> SPRINTER option ID (eski format): {option_id}")
                                option_name = self.get_dropdown_option_name(option_id)
                                print(f"   >>> SPRINTER option name: {option_name}")
                            else:
                                print(f"   >>> SPRINTER değeri dict ama idListOption yok: {value}")
                        else:
                            print(f"   >>> SPRINTER değeri başka format: {type(value)} = {value}")
                            
                    elif field_id == self.sprint_field_id:
                        print(f"   ^^^ Bu SPRINTNO field")
                    elif field_id == self.story_point_field_id:
                        print(f"   ^^^ Bu STORYPOINT field")
                    else:
                        print(f"   ^^^ Bu bilinmeyen field")
                        
                debug_sample_count += 1
            
            # Custom field'dan sprinter ismini al
            sprinter_name = self.extract_sprinter_from_custom_field(card)
            
            # Eğer sprinter bulunamazsa kartı atla
            if not sprinter_name:
                if debug_sample_count <= 5:
                    card_name = card.get('name', 'Unknown')[:50]
                    print(f"⚠️ Sprinter field yok - Kart: {card_name}...")
                continue
            elif sprinter_name == "FIELD_EMPTY":
                cards_with_empty_sprinter += 1
                if debug_sample_count <= 5:
                    card_name = card.get('name', 'Unknown')[:50]
                    print(f"⚠️ Sprinter dropdown boş - Kart: {card_name}...")
                continue
                
            cards_with_sprinter += 1
            
            # İlk başarılı kartı göster
            if cards_with_sprinter == 1:
                card_name = card.get('name', 'Unknown')[:50]
                print(f"✅ İLK BAŞARILI KART: {card_name} - Sprinter: {sprinter_name}")
            
            # Custom field'dan story point al
            story_points = self.extract_story_points_from_custom_field(card)
            
            # Fallback: Eğer custom field'dan alınamadıysa kart isminden dene
            if story_points is None or story_points == 0:
                story_points = self.extract_story_points(card.get('name', ''))
            
            # Custom field'dan sprint numarasını al
            sprint_num = self.extract_sprint_number_from_custom_field(card)
            
            # Fallback: Eğer custom field'dan alınamadıysa kart isminden dene
            if sprint_num is None:
                sprint_num = self.extract_sprint_number(card.get('name', ''))
            
            if not story_points or not sprint_num:
                if debug_sample_count <= 5:
                    card_name = card.get('name', 'Unknown')[:50]
                    print(f"⚠️ Kart atlandı - SP: {story_points}, Sprint: {sprint_num}, Kart: {card_name}...")
                continue
            
            cards_with_sp += 1
            
            # Sprinter ismini ID olarak kullan (normalize et)
            try:
                sprinter_id = sprinter_name.lower().replace(' ', '_').replace('ç', 'c').replace('ğ', 'g').replace('ı', 'i').replace('ö', 'o').replace('ş', 's').replace('ü', 'u')
                
                member_stats[sprinter_id]['name'] = sprinter_name
                member_stats[sprinter_id]['total_assigned'] += story_points
                member_stats[sprinter_id]['sprints_participated'].add(sprint_num)
                
                # Tamamlanmış kabul ediyoruz (ArchiveNew'de oldukları için)
                member_stats[sprinter_id]['total_completed'] += story_points
                
            except Exception as e:
                print(f"⚠️ Sprinter data işleme hatası: {e}, Sprinter: {sprinter_name}")
                continue
        
        print(f"📋 İşlenen kartlar: {cards_processed}")
        print(f"👤 Sprinter'lı kartlar: {cards_with_sprinter}")
        print(f"🔴 Boş sprinter field'lı kartlar: {cards_with_empty_sprinter}")
        print(f"📊 SP'li kartlar: {cards_with_sp}")
        print(f"👥 Bulunan sprinter'lar: {list(member_stats.keys())}")
        
        # İstatistikleri hesapla
        for member_id, stats in member_stats.items():
            try:
                if stats['total_assigned'] > 0:
                    stats['completion_rate'] = (stats['total_completed'] / stats['total_assigned']) * 100
                    sprints_count = len(stats['sprints_participated'])
                    if sprints_count > 0:
                        stats['avg_sp_per_sprint'] = stats['total_completed'] / sprints_count
                    stats['sprints_participated'] = list(stats['sprints_participated'])
            except Exception as e:
                print(f"⚠️ İstatistik hesaplama hatası: {e}, Member: {member_id}")
                continue
        
        return dict(member_stats)
    
    def calculate_historical_sprint_totals(self, cards):
        """Geçmiş sprintlerin toplam SP'lerini hesapla"""
        sprint_totals = defaultdict(int)
        
        for card in cards:
            if not card or not isinstance(card, dict):
                continue
            
            # Sprint numarasını al
            sprint_num = self.extract_sprint_number_from_custom_field(card)
            if sprint_num is None:
                sprint_num = self.extract_sprint_number(card.get('name', ''))
            
            # Story point al
            story_points = self.extract_story_points_from_custom_field(card)
            if story_points is None or story_points == 0:
                story_points = self.extract_story_points(card.get('name', ''))
            
            if sprint_num and story_points:
                sprint_totals[sprint_num] += story_points
        
        return dict(sprint_totals)

    def suggest_capacity(self, member_stats, current_sprint_total_sp, current_sprint_number, 
                       sprinter_exceptions_manager=None, historical_cards=None, 
                       sprint_working_days=None):
        """
        Gelişmiş kapasite önerisi algoritması
        
        Algoritma:
        1. Geçmiş sprint verilerini analiz et
        2. Her sprinter için hedef SP'ye yaklaştırıcı hesaplama yap
        3. Düşük performanslıları yukarı çek, yüksekleri dengele
        4. Exception'ları ve çalışma günü ayarlarını uygula
        """
        suggestions = {}
        base_suggestions = {}
        
        # Settings al
        settings = sprinter_exceptions_manager.get_settings() if sprinter_exceptions_manager else {}
        target_sp = settings.get('target_sp_per_person', 21)
        min_sp_threshold = settings.get('min_sp_threshold', 3)
        target_push_factor = settings.get('target_push_factor', 0.7)
        capacity_growth_limit = settings.get('capacity_growth_limit', 1.5)
        low_performer_boost = settings.get('low_performer_boost', 2.0)
        
        # Geçmiş sprint totalleri hesapla
        sprint_totals = {}
        if historical_cards:
            sprint_totals = self.calculate_historical_sprint_totals(historical_cards)
        
        # Her sprinter için detaylı analiz
        for member_id, stats in member_stats.items():
            if stats['avg_sp_per_sprint'] <= 0:
                continue
                
            # Sprinter'ın sprint detaylarını hesapla
            sprinter_sprint_details = self._calculate_sprinter_sprint_details(
                member_id, historical_cards
            )
            
            # Pay oranlarını hesapla
            avg_percentage = self._calculate_average_percentage(
                sprinter_sprint_details, sprint_totals, len(member_stats)
            )
            
            # Mevcut sprint'te beklenen SP
            current_projected_sp = (avg_percentage / 100) * current_sprint_total_sp
            
            # Gelişmiş kapasite hesaplama
            suggested_sp = self._calculate_enhanced_capacity(
                current_projected_sp=current_projected_sp,
                historical_avg=stats['avg_sp_per_sprint'],
                target_sp=target_sp,
                completion_rate=stats['completion_rate'],
                target_push_factor=target_push_factor,
                capacity_growth_limit=capacity_growth_limit,
                low_performer_boost=low_performer_boost,
                min_sp_threshold=min_sp_threshold
            )
            
            base_suggestions[member_id] = {
                'name': stats['name'],
                'base_suggested_sp': round(suggested_sp, 1),
                'historical_avg': round(stats['avg_sp_per_sprint'], 1),
                'completion_rate': round(stats['completion_rate'], 1),
                'avg_percentage': round(avg_percentage, 1),
                'projected_sp': round(current_projected_sp, 1),
                'target_sp': target_sp
            }
        
        # Takım ortalaması hesapla
        team_average_sp = (sum([s['base_suggested_sp'] for s in base_suggestions.values()]) / 
                          len(base_suggestions)) if base_suggestions else 0
        
        # Exception'ları uygula
        for member_id, base_suggestion in base_suggestions.items():
            base_capacity = base_suggestion['base_suggested_sp']
            
            if sprinter_exceptions_manager:
                # Exception'ları hesapla
                adjustment_result = sprinter_exceptions_manager.calculate_adjusted_capacity(
                    sprinter_id=member_id, 
                    base_capacity=base_capacity, 
                    sprint_number=current_sprint_number, 
                    team_average_sp=team_average_sp, 
                    sprint_working_days=sprint_working_days
                )
                
                suggestions[member_id] = {
                    'name': base_suggestion['name'],
                    'suggested_sp': round(adjustment_result['adjusted_sp']),
                    'base_suggested_sp': round(adjustment_result['original_sp'], 1),
                    'historical_avg': base_suggestion['historical_avg'],
                    'completion_rate': base_suggestion['completion_rate'],
                    'avg_percentage': base_suggestion['avg_percentage'],
                    'projected_sp': base_suggestion['projected_sp'],
                    'target_sp': base_suggestion['target_sp'],
                    'adjustments': adjustment_result['adjustments'],
                    'rationale': f"Gelişmiş algoritma: Hedef {base_suggestion['target_sp']} SP, "
                                f"Geçmiş %{base_suggestion['avg_percentage']}, "
                                f"Exception: {adjustment_result['explanation']}"
                }
            else:
                suggestions[member_id] = {
                    'name': base_suggestion['name'],
                    'suggested_sp': round(base_capacity),
                    'base_suggested_sp': round(base_capacity, 1),
                    'historical_avg': base_suggestion['historical_avg'],
                    'completion_rate': base_suggestion['completion_rate'],
                    'avg_percentage': base_suggestion['avg_percentage'],
                    'projected_sp': base_suggestion['projected_sp'],
                    'target_sp': base_suggestion['target_sp'],
                    'adjustments': [],
                    'rationale': f"Gelişmiş algoritma: Hedef {base_suggestion['target_sp']} SP, "
                                f"Geçmiş %{base_suggestion['avg_percentage']}"
                }
        
        return suggestions
    
    def _calculate_sprinter_sprint_details(self, member_id, historical_cards):
        """Sprinter'ın sprint bazlı detaylarını hesapla"""
        sprinter_sprint_details = {}
        
        for card in historical_cards or []:
            if not card or not isinstance(card, dict):
                continue
            
            # Sprinter kontrolü
            card_sprinter = self.extract_sprinter_from_custom_field(card)
            if not card_sprinter or card_sprinter == "FIELD_EMPTY":
                continue
            
            # Sprinter ID'sini normalize et
            card_sprinter_id = card_sprinter.lower().replace(' ', '_').replace('ç', 'c').replace('ğ', 'g').replace('ı', 'i').replace('ö', 'o').replace('ş', 's').replace('ü', 'u')
            
            if card_sprinter_id != member_id:
                continue
            
            # Sprint numarası
            sprint_num = self.extract_sprint_number_from_custom_field(card)
            if sprint_num is None:
                sprint_num = self.extract_sprint_number(card.get('name', ''))
            
            # Story point
            story_points = self.extract_story_points_from_custom_field(card)
            if story_points is None or story_points == 0:
                story_points = self.extract_story_points(card.get('name', ''))
            
            if sprint_num and story_points:
                if sprint_num not in sprinter_sprint_details:
                    sprinter_sprint_details[sprint_num] = 0
                sprinter_sprint_details[sprint_num] += story_points
        
        return sprinter_sprint_details
    
    def _calculate_average_percentage(self, sprinter_sprint_details, sprint_totals, team_size):
        """Ortalama pay yüzdesini hesapla"""
        total_percentage = 0
        valid_sprints = 0
        
        for sprint_num, sprinter_sp in sprinter_sprint_details.items():
            if sprint_num in sprint_totals and sprint_totals[sprint_num] > 0:
                percentage = (sprinter_sp / sprint_totals[sprint_num]) * 100
                total_percentage += percentage
                valid_sprints += 1
        
        if valid_sprints > 0:
            return total_percentage / valid_sprints
        else:
            # Fallback: Takımda eşit dağılım varsay
            return 100 / team_size if team_size > 0 else 15
    
    def _calculate_enhanced_capacity(self, current_projected_sp, historical_avg, target_sp, 
                                   completion_rate, target_push_factor, capacity_growth_limit,
                                   low_performer_boost, min_sp_threshold):
        """Gelişmiş kapasite hesaplama algoritması"""
        
        # Hedef mesafesi hesapla
        target_distance = target_sp - current_projected_sp
        
        # Düşük performanslı mı?
        is_low_performer = current_projected_sp < target_sp * 0.5
        
        if is_low_performer:
            # Düşük performanslı için agresif artış
            target_boost = target_distance * target_push_factor * low_performer_boost
            suggested_sp = current_projected_sp + target_boost
            
            # Maksimum artış sınırı
            max_growth = historical_avg * capacity_growth_limit
            suggested_sp = min(suggested_sp, max_growth)
            
            # Hedefin %80'ini geçmesin (kademeli artış)
            suggested_sp = min(suggested_sp, target_sp * 0.8)
            
        elif current_projected_sp < target_sp * 0.8:
            # Orta seviye için dengeli artış
            target_boost = target_distance * target_push_factor
            suggested_sp = current_projected_sp + target_boost
            
            # Hedefin %90'ını geçmesin
            suggested_sp = min(suggested_sp, target_sp * 0.9)
            
        else:
            # Hedef civarında ise hafif artış
            growth_factor = 1.05  # %5 artış
            suggested_sp = current_projected_sp * growth_factor
            
            # Hedefi geçmesin
            suggested_sp = min(suggested_sp, target_sp)
        
        # Tamamlama oranını uygula
        completion_adjustment = completion_rate / 100
        suggested_sp = suggested_sp * completion_adjustment
        
        # Minimum eşiği garantile
        if suggested_sp > 0:
            suggested_sp = max(suggested_sp, min_sp_threshold)
        
        return suggested_sp

# Global değişkenler
trello_oauth = None
trello_api = None
sprint_analyzer = SprintAnalyzer()
token_storage = TokenStorage()
sprinter_exceptions = SprinterExceptions()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/check-auth', methods=['GET'])
def check_auth():
    """Mevcut authentication durumunu kontrol et"""
    global trello_api
    
    try:
        # Stored token'ları kontrol et
        token_data = token_storage.load_tokens()
        
        if not token_data:
            return jsonify({
                'authenticated': False,
                'message': 'Kayıtlı token bulunamadı'
            })
        
        # TrelloAPI instance'ını oluştur ve test et
        api_key = token_data['api_key']
        access_token = token_data['access_token']
        access_token_secret = token_data['access_token_secret']
        board_id = token_data.get('board_id')
        
        if board_id:
            # Board ID varsa API bağlantısını test et
            trello_api = TrelloAPI(api_key, access_token, access_token_secret, board_id)
            lists = trello_api.get_lists()
            
            if lists:
                return jsonify({
                    'authenticated': True,
                    'board_connected': True,
                    'board_id': board_id,
                    'lists': [{'id': lst['id'], 'name': lst['name']} for lst in lists],
                    'message': 'Trello bağlantısı aktif'
                })
        
        return jsonify({
            'authenticated': True,
            'board_connected': False,
            'message': 'OAuth token mevcut, board ID gerekli'
        })
        
    except Exception as e:
        print(f"Auth check hatası: {e}")
        return jsonify({
            'authenticated': False,
            'message': f'Bağlantı testi başarısız: {str(e)}'
        })

@app.route('/auth/setup', methods=['POST'])
def setup_oauth():
    """OAuth ayarlarını başlat"""
    global trello_oauth
    
    data = request.json
    api_key = data.get('api_key')
    api_secret = data.get('api_secret')
    
    if not all([api_key, api_secret]):
        return jsonify({'error': 'API key ve secret gerekli'}), 400
    
    try:
        trello_oauth = TrelloOAuth(api_key, api_secret)
        auth_url = trello_oauth.get_authorization_url()
        
        if auth_url:
            return jsonify({
                'success': True,
                'auth_url': auth_url,
                'message': 'Trello authorization URL hazırlandı'
            })
        else:
            return jsonify({'error': 'Authorization URL oluşturulamadı'}), 400
            
    except Exception as e:
        return jsonify({'error': f'OAuth setup hatası: {str(e)}'}), 500

@app.route('/callback')
def oauth_callback():
    """OAuth callback - Trello'dan dönüş"""
    global trello_api
    
    oauth_verifier = request.args.get('oauth_verifier')
    oauth_token = request.args.get('oauth_token')
    
    if not oauth_verifier or not oauth_token:
        return "OAuth callback hatası: Verifier veya token eksik", 400
    
    if not trello_oauth:
        return "OAuth kurulumu yapılmamış", 400
    
    try:
        # Access token al
        tokens = trello_oauth.get_access_token(oauth_verifier)
        
        if tokens:
            # Token'ları session'da sakla
            session['access_token'] = tokens['oauth_token']
            session['access_token_secret'] = tokens['oauth_token_secret']
            session['api_key'] = trello_oauth.api_key
            
            # Token'ları persistent storage'a kaydet
            token_storage.save_tokens(
                api_key=trello_oauth.api_key,
                access_token=tokens['oauth_token'],
                access_token_secret=tokens['oauth_token_secret']
            )
            
            return redirect('/?auth=success')
        else:
            return redirect('/?auth=error')
            
    except Exception as e:
        print(f"OAuth callback hatası: {e}")
        return redirect('/?auth=error')

@app.route('/setup', methods=['POST'])
def setup_trello():
    """Trello board ayarlarını yap"""
    global trello_api
    
    # OAuth token'ları kontrol et (önce session, sonra storage)
    api_key = session.get('api_key')
    access_token = session.get('access_token')
    access_token_secret = session.get('access_token_secret')
    
    # Session'da yoksa storage'dan yükle
    if not all([api_key, access_token, access_token_secret]):
        token_data = token_storage.load_tokens()
        if token_data:
            api_key = token_data['api_key']
            access_token = token_data['access_token']
            access_token_secret = token_data['access_token_secret']
            
            # Session'ı güncelle
            session['api_key'] = api_key
            session['access_token'] = access_token
            session['access_token_secret'] = access_token_secret
        else:
            return jsonify({'error': 'Önce OAuth authentication yapın'}), 400
    
    data = request.json
    board_id = data.get('board_id')
    
    if not board_id:
        return jsonify({'error': 'Board ID gerekli'}), 400
    
    try:
        print(f"Debug - API Key: {api_key is not None}")
        print(f"Debug - Access Token: {access_token is not None}")
        print(f"Debug - Access Token Secret: {access_token_secret is not None}")
        print(f"Debug - Board ID: {board_id}")
        
        # OAuth token'ları ile TrelloAPI oluştur
        trello_api = TrelloAPI(api_key, access_token, access_token_secret, board_id)
        
        # Bağlantıyı test et
        lists = trello_api.get_lists()
        
        # Board ID'yi storage'a kaydet
        token_storage.update_board_id(board_id)
        
        return jsonify({
            'success': True,
            'message': 'Trello bağlantısı başarılı',
            'lists': [{'id': lst['id'], 'name': lst['name']} for lst in lists]
        })
        
    except Exception as e:
        print(f"Setup error details: {e}")
        return jsonify({'error': f'Trello bağlantısı başarısız: {str(e)}'}), 400

@app.route('/analyze', methods=['POST'])
def analyze_performance():
    """Geçmiş sprint performansını analiz et"""
    if not trello_api:
        return jsonify({'error': 'Önce Trello ayarlarını yapın'}), 400
    
    data = request.json
    archive_list_id = data.get('archive_list_id')
    current_sprint_number = data.get('current_sprint_number')
    
    if not archive_list_id or not current_sprint_number:
        return jsonify({'error': 'ArchiveNew list ID ve mevcut sprint numarası gerekli'}), 400
    
    try:
        print("🔄 Custom field'ları çekiliyor...")
        # Custom field'ları çek
        custom_fields = trello_api.get_custom_fields()
        
        if not custom_fields:
            return jsonify({'error': 'Board\'da custom field bulunamadı. SprintNo, StoryPoint ve Sprinter field\'larını oluşturun.'}), 400
        
        print("🔄 Kartlar çekiliyor...")
        # Tüm kartları çek
        all_cards = trello_api.get_board_data()
        
        if not all_cards:
            return jsonify({'error': 'Board\'da kart bulunamadı'}), 400
        
        print(f"📊 Toplam {len(all_cards)} kart bulundu")
        
        # Son 3 sprintin kartlarını filtrele
        last_sprint_cards, sprint_numbers = sprint_analyzer.get_last_3_sprints(
            all_cards, archive_list_id, current_sprint_number, custom_fields
        )
        
        if not last_sprint_cards:
            return jsonify({'error': f'ArchiveNew listesinde analiz edilecek sprint bulunamadı. Sprint {current_sprint_number-3}, {current_sprint_number-2}, {current_sprint_number-1} kontrol edin.'}), 400
        
        # Üye performansını analiz et
        member_stats = sprint_analyzer.analyze_member_performance(last_sprint_cards)
        
        if not member_stats:
            return jsonify({'error': 'Kartlarda Sprinter dropdown\'ından seçim yapılmamış. Lütfen ArchiveNew listesindeki kartlarda Sprinter field\'ından kişi seçimlerini yapın.'}), 400
        
        return jsonify({
            'success': True,
            'sprint_numbers': sprint_numbers,
            'member_stats': member_stats,
            'total_cards_analyzed': len(last_sprint_cards),
            'current_sprint': current_sprint_number
        })
    
    except Exception as e:
        print(f"❌ Analiz hatası detayı: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Analiz hatası: {str(e)}'}), 500

@app.route('/suggest', methods=['POST'])
def suggest_capacity():
    """Mevcut sprint için kapasite önerisi yap"""
    if not trello_api:
        return jsonify({'error': 'Önce Trello ayarlarını yapın'}), 400
    
    data = request.json
    archive_list_id = data.get('archive_list_id')
    current_sprint_total = data.get('current_sprint_total', 0)
    current_sprint_number = data.get('current_sprint_number')
    
    if not archive_list_id or not current_sprint_number:
        return jsonify({'error': 'ArchiveNew list ID ve mevcut sprint numarası gerekli'}), 400
    
    try:
        print("🔄 Öneri için veriler hazırlanıyor...")
        
        # Custom field'ları çek
        custom_fields = trello_api.get_custom_fields()
        
        if not custom_fields:
            return jsonify({'error': 'Board\'da custom field bulunamadı'}), 400
        
        # Analiz verilerini al
        all_cards = trello_api.get_board_data()
        
        if not all_cards:
            return jsonify({'error': 'Board\'da kart bulunamadı'}), 400
        
        last_sprint_cards, sprint_numbers = sprint_analyzer.get_last_3_sprints(
            all_cards, archive_list_id, current_sprint_number, custom_fields
        )
        
        if not last_sprint_cards:
            return jsonify({'error': 'Analiz edilecek sprint kartı bulunamadı'}), 400
            
        member_stats = sprint_analyzer.analyze_member_performance(last_sprint_cards)
        
        if not member_stats:
            return jsonify({'error': 'Üye istatistikleri oluşturulamadı'}), 400
        
        # Sprint working days parametresini al
        sprint_working_days = data.get('sprint_working_days', 5)
        print(f"Debug - Received sprint_working_days: {sprint_working_days}")
        
        # Kapasite önerileri yap (exception'lar dahil)
        suggestions = sprint_analyzer.suggest_capacity(
            member_stats, current_sprint_total, current_sprint_number, 
            sprinter_exceptions, last_sprint_cards, sprint_working_days
        )
        
        # Toplam önerilen SP'yi hesapla
        total_suggested = sum([s['suggested_sp'] for s in suggestions.values()])
        
        return jsonify({
            'success': True,
            'suggestions': suggestions,
            'total_suggested_sp': total_suggested,
            'current_sprint_total': current_sprint_total,
            'current_sprint_number': current_sprint_number,
            'analyzed_sprints': sprint_numbers,
            'difference': current_sprint_total - total_suggested
        })
    
    except Exception as e:
        print(f"❌ Öneri hatası detayı: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Öneri hatası: {str(e)}'}), 500

@app.route('/get-sprinters', methods=['POST'])
def get_sprinters():
    """Analiz sonucundaki sprinter listesini döndür"""
    if not trello_api:
        return jsonify({'error': 'Önce Trello ayarlarını yapın'}), 400
    
    data = request.json
    archive_list_id = data.get('archive_list_id')
    current_sprint_number = data.get('current_sprint_number')
    
    if not archive_list_id or not current_sprint_number:
        return jsonify({'error': 'ArchiveNew list ID ve mevcut sprint numarası gerekli'}), 400
    
    try:
        # Custom field'ları çek
        custom_fields = trello_api.get_custom_fields()
        if not custom_fields:
            return jsonify({'error': 'Board\'da custom field bulunamadı'}), 400
        
        # Analiz verilerini al
        all_cards = trello_api.get_board_data()
        if not all_cards:
            return jsonify({'error': 'Board\'da kart bulunamadı'}), 400
        
        last_sprint_cards, sprint_numbers = sprint_analyzer.get_last_3_sprints(
            all_cards, archive_list_id, current_sprint_number, custom_fields
        )
        
        if not last_sprint_cards:
            return jsonify({'error': 'Analiz edilecek sprint kartı bulunamadı'}), 400
            
        member_stats = sprint_analyzer.analyze_member_performance(last_sprint_cards)
        
        if not member_stats:
            return jsonify({'error': 'Üye istatistikleri oluşturulamadı'}), 400
        
        # Sprinter listesini hazırla
        sprinters = []
        for member_id, stats in member_stats.items():
            sprinters.append({
                'id': member_id,
                'name': stats['name']
            })
        
        return jsonify({
            'success': True,
            'sprinters': sprinters,
            'total_sprinters': len(sprinters)
        })
    
    except Exception as e:
        print(f"❌ Sprinter listesi hatası: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Sprinter listesi hatası: {str(e)}'}), 500

@app.route('/save-exceptions', methods=['POST'])
def save_exceptions():
    """Sprinter exception'larını kaydet"""
    try:
        data = request.json
        sprint_number = data.get('sprint_number')
        exceptions = data.get('exceptions', {})
        
        if not sprint_number:
            return jsonify({'error': 'Sprint numarası gerekli'}), 400
        
        # Exception'ları kaydet
        success = sprinter_exceptions.save_exceptions(sprint_number, exceptions)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Sprint {sprint_number} exception\'ları kaydedildi',
                'sprint_number': sprint_number,
                'total_exceptions': len([k for k, v in exceptions.items() if any(v.values())])
            })
        else:
            return jsonify({'error': 'Exception\'lar kaydedilemedi'}), 500
    
    except Exception as e:
        print(f"❌ Exception kaydetme hatası: {e}")
        return jsonify({'error': f'Exception kaydetme hatası: {str(e)}'}), 500

@app.route('/get-exceptions/<int:sprint_number>', methods=['GET'])
def get_exceptions(sprint_number):
    """Belirli bir sprint için exception'ları getir"""
    try:
        exceptions = sprinter_exceptions.load_exceptions(sprint_number)
        
        return jsonify({
            'success': True,
            'sprint_number': sprint_number,
            'exceptions': exceptions,
            'has_exceptions': bool(exceptions)
        })
    
    except Exception as e:
        print(f"❌ Exception getirme hatası: {e}")
        return jsonify({'error': f'Exception getirme hatası: {str(e)}'}), 500

if __name__ == '__main__':
    # Not: pip install requests-oauthlib komutu ile OAuth kütüphanesini yükleyin
    print("🚀 Sprint Planner başlatılıyor...")
    print("📋 http://localhost:8080 adresine gidin")
    print("🔑 Trello API Key ve OAuth Secret'a ihtiyacınız var:")
    print("   - https://trello.com/app-key sayfasından alabilirsiniz")
    app.run(debug=True, port=8080)