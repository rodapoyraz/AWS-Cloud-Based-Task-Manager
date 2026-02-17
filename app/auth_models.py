from flask_login import UserMixin

class User(UserMixin):
    def __init__(self, user_id: str, email: str, password_hash: str):
        self.id = user_id
        self.email = email
        self.password_hash = password_hash

    @staticmethod
    def from_cosmos(data: dict):
        if not data:
            return None
        return User(
            user_id=data.get("id"),
            email=data.get("email"),
            password_hash=data.get("password_hash"),
        )
