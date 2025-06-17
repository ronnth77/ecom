from fastapi import HTTPException, status
from tortoise.exceptions import DoesNotExist
from passlib.context import CryptContext
import jwt
from dotenv import dotenv_values
from models import User
from fastapi import status
from mail import config_credentials

#logging
import logging


logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated = "auto")

def get_hashed_password(password):
    logger.debug("hashing password")
    return pwd_context.hash(password)

async def very_token(token: str):
    try:
        logger.info("Verifying token")
        payload = jwt.decode(token, config_credentials["SECRET"], algorithms=["HS256"])
        logger.debug(f"Token payload: {payload}")
        user = await User.get(id=payload.get("id"))
        logger.info(f"Token valid for user ID {user.id}")
    except DoesNotExist:
        logger.warning(f"User not found for token ID: {payload.get('id')}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User no longer exists"
        )
    except Exception as e:  # This goes LAST
        logger.error(f"Invalid or expired token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user
async def verify_password(plain_password, hashed_password):
    #LOG verifying password
    logger.info("Verifying user password")
    result = pwd_context.verify(plain_password, hashed_password)
    if result:
        logger.debug("Password verification successful")
    else:
        logger.debug("Password verification failed")
    return result

async def authenticate_user(username, password):
    #LOG verifying username
    logger.info("Verifying username")
    try:
        user = await User.get(username = username)
    except DoesNotExist:
        logger.warning(f"Authentication failed user: {username} does not exist")
        return False
    
    if user and await verify_password(password, user.password):
        logger.info(f"Verification of username: {username} successfull")
        return user
    logger.warning(f"Authentication failed user: {username}")
    return False


async def token_generator(username: str, password: str):
    logger.info(f"Generating token for user: {username}")
    user = await authenticate_user(username, password)
    if not user:
        logger.warning(f"Token generation failed for user: {username}")
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Invalid username or password",
            headers = {"WWW-AUTHENTICATE": "Bearer"}

        )
    
    token_data = {
        "id": user.id,
        "username": user.username
    }

    token = jwt.encode(token_data, config_credentials["SECRET"])
    logger.info(f"Token generated for user: {username}")
    return token

    