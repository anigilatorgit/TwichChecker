import uuid
import requests
import config
from typing import Optional, Dict
import hashlib
from urllib.parse import urlencode


async def create_payment(user_id: int, amount: float, description: str = "Подписка на бота") -> Optional[Dict]:
    try:
        if not config.YOOMONEY_WALLET_ID:
            print("❌ YOOMONEY_WALLET_ID не настроен в config.py")
            return None
        
        payment_label = f"subscription_{user_id}_{uuid.uuid4().hex[:8]}"
        
        url = "https://yoomoney.ru/quickpay/confirm.xml"
        
        params = {
            "receiver": config.YOOMONEY_WALLET_ID,
            "quickpay-form": "button",
            "targets": description,
            "paymentType": "AC",
            "sum": f"{amount:.2f}",
            "label": payment_label,
            "successURL": config.BOT_URL
        }
        
        payment_url = f"{url}?{urlencode(params)}"
        
        return {
            "payment_id": payment_label,
            "confirmation_url": payment_url,
            "status": "pending"
        }
    except Exception as e:
        print(f"❌ Ошибка при создании платежа: {e}")
        return None


async def check_payment_status(payment_label: str) -> Optional[bool]:
    try:
        if not config.YOOMONEY_ACCESS_TOKEN:
            return None
        
        url = "https://yoomoney.ru/api/operation-history"
        
        headers = {
            "Authorization": f"Bearer {config.YOOMONEY_ACCESS_TOKEN}"
        }
        
        params = {
            "label": payment_label,
            "records": 10
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("error"):
            return None
        
        operations = data.get("operations", [])
        
        for operation in operations:
            if operation.get("label") == payment_label:
                status = operation.get("status")
                if status == "success":
                    return True
        
        return False
    except Exception as e:
        print(f"❌ Ошибка при проверке статуса платежа: {e}")
        return None


def verify_notification(notification_data: dict) -> bool:
    try:
        if not config.YOOMONEY_NOTIFICATION_SECRET:
            return False
        
        notification_secret = config.YOOMONEY_NOTIFICATION_SECRET
        
        str_for_hash = (
            f"{notification_data.get('notification_type')}&"
            f"{notification_data.get('operation_id')}&"
            f"{notification_data.get('amount')}&"
            f"{notification_data.get('currency')}&"
            f"{notification_data.get('datetime')}&"
            f"{notification_data.get('sender')}&"
            f"{notification_data.get('codepro')}&"
            f"{notification_secret}&"
            f"{notification_data.get('label')}"
        )
        
        hash_value = hashlib.sha1(str_for_hash.encode()).hexdigest()
        
        return hash_value == notification_data.get("sha1_hash", "")
    except Exception as e:
        print(f"❌ Ошибка при проверке уведомления: {e}")
        return False

