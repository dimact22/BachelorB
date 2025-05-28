from passlib.context import CryptContext

# Initialize a CryptContext instance with bcrypt hashing scheme
pwd_cxt = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Hash:
    # Hash a password using bcrypt
    @staticmethod
    def bcrypt(password: str) -> str:
        return pwd_cxt.hash(password)

    # Verify a plain password against a hashed password
    @staticmethod
    def verify(plain_password: str, hashed_password: str) -> bool:
        return pwd_cxt.verify(plain_password, hashed_password)

# print(Hash.bcrypt("adminpass"))
    

