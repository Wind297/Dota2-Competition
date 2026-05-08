from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import settings

_serializer = URLSafeTimedSerializer(settings.secret_key, salt="dota2-admin-session")


def create_access_token() -> str:
    return _serializer.dumps({"role": "admin"})


def verify_access_token(token: str, max_age_seconds: int = 604800) -> bool:
    try:
        _serializer.loads(token, max_age=max_age_seconds)
        return True
    except (BadSignature, SignatureExpired):
        return False
