from fastapi import FastAPI, HTTPException, Request, status, Depends
from tortoise.contrib.fastapi import register_tortoise
from models import *
import os

#logging
import logging

logging.basicConfig(
    level=logging.INFO,  # Change to DEBUG for more verbosity
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="app.log",         # Log file path/name
    filemode="a"                # Append to the log file (use "w" to overwrite each time)
)

logger = logging.getLogger(__name__)


#authentication
from authentication import *
from fastapi.security import (OAuth2PasswordBearer, OAuth2PasswordRequestForm)

#signals
from tortoise.signals import post_save
from typing import List, Optional, Type
from tortoise import BaseDBAsyncClient
from tortoise.exceptions import IntegrityError
from mail import send_email

#image uplaod
from fastapi import File, UploadFile
import secrets
from fastapi.staticfiles import StaticFiles
from PIL import Image

#response classes
from fastapi.responses import HTMLResponse

#datetime
from datetime import datetime
app = FastAPI()

#templates
from fastapi.templating import Jinja2Templates

oath2_scheme = OAuth2PasswordBearer(tokenUrl = "token")

# static file setup config
#becomes available by http://localhost:8000/static/images/logo.png
#improve for security purposes
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.post("/token", include_in_schema=False)
async def generate_token(request_form: OAuth2PasswordRequestForm = Depends()):
    #LOG generating token
    logger.info(f"Login attempt for user: {request_form.username}")
    token = await token_generator(request_form.username, request_form.password)
    return {"access_token": token, "token_type": "bearer"}

async def get_current_user(token: str = Depends(oath2_scheme)):
    try:
        payload = jwt.decode(token, config_credentials["SECRET"], algorithms=["HS256"])
        logger.debug(f"Token payload decoded for user ID: {payload.get('id')}")
        user = await User.get(id = payload.get("id"))
    
    except Exception as e:
        logger.warning(f"Invalid token access attempt: {e}")
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Invalid username or password",
            headers = {"WWW-AUTHENTICATE": "Bearer"}
        )
    return user

@app.post("/user/me")
async def user_login(user: user_pydanticIn = Depends(get_current_user)):
    business = await Business.get(owner = user)
    logo = business.logo
    logo_path = "localhost:8000/static/images/"+logo


    return {
        "status": "ok",
        "data": {
            "username": user.username,
            "email": user.email,
            "verified": user.is_verified,
            "joined_date": user.join_date.strftime("%b %d %Y"),
            "logo": logo_path
        }
    }

@post_save(User)
async def create_business(
    sender: "Type[User]",
    instance: User,
    created: bool,
    using_db: "Optional[BaseDBAsyncClient]",
    update_fields: List[str]
) -> None:
    
    if created:
        #LOG creatin and saving a business profile of user in database
        bussiness_obj = await Business.create(
            business_name = instance.username,
            owner = instance
        )

        await business_pydantic.from_tortoise_orm(bussiness_obj)
        # LOG the sending of email
        await send_email([instance.email], instance)

@app.post("/registration")
# LOG registration process started
async def user_registration(user: user_pydanticIn):
    logger.info(f"Registration attempt for username: {user.username}, email: {user.email}")
    user_info = user.dict(exclude_unset=True)

    # LOG Optional pre-check(username)
    if await User.filter(username=user_info["username"]).exists():
        raise HTTPException(status_code=400, detail="Username already exists")
    # LOG pre-check(email)
    if await User.filter(email=user_info["email"]).exists():
        raise HTTPException(status_code=400, detail="Email already exists")

    # Hash the password
    user_info["password"] = get_hashed_password(user_info["password"])

    try:
        # LOG Create user and save
        user_obj = await User.create(**user_info)
        new_user = await user_pydantic.from_tortoise_orm(user_obj)
        logger.info(f"User created: {new_user.username}")
    except IntegrityError as e:
        raise HTTPException(status_code=400, detail="Username or Email already exists")

    # LOG oncverting from orm model to pydantic model
    new_user = await user_pydantic.from_tortoise_orm(user_obj)

    return {
        "status": "ok",
        "data": f"Hello {new_user.username}, thanks for choosing our services."
    }

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
@app.get("/verification", response_class=HTMLResponse)
# LOG verification starting
async def email_verification(request: Request, token: str): #what is request
    logger.info(f"Verification attempt with token")
    user = await very_token(token)
    if user:
        if user.is_verified:
            # LOG already verified, return a message indicating they are already verified
            logger.info(f"User {user.username} already verified ")
            return templates.TemplateResponse("already_verified.html", 
                                              {"request": request, "username": user.username})
        else:
            # LOG user was not verified, verify the user
            user.is_verified = True
            await user.save()
            logger.info(f"User {user.username} verified successfully")
            return templates.TemplateResponse("verification.html", 
                                              {"request": request, "username": user.username})
    #LOG error
    raise HTTPException(
            status_code = status.HTTP_403_UNAUTHORIZED,
            detail = "Invalid Token or expired token",
            headers = {"WWW-Authenticate": "Bearer"}
        )



@app.get("/")
# LOG app started
def index():
    return {"Message": "Hello World"}

#LOG upload pictures
@app.post("/uploadfile/profile")
async def create_upload_file(file: UploadFile = File(...), user: user_pydantic = Depends(get_current_user)):
    logger.info(f"User {user.username} uploading profile image: {file.filename}")
    FILEPATH = "./static/images/"
    filename = file.filename
    extension = filename.split(".")[1]

    if extension not in ["png", "jpg"]:
        return {"status": "error", "detail": "File extension not allowed"}
    
    token_name = secrets.token_hex(10)+"."+extension
    generated_name = FILEPATH + token_name
    file_content = await file.read()

    #LOG image is saving
    with open(generated_name, "wb") as file:
        file.write(file_content)

    # PILLOW
    img = Image.open(generated_name)
    img = img.resize(size = (200, 200))
    img.save(generated_name)

    file.close()
    logger.info(f"Image saved")

    business = await Business.get(owner = user) #shouldnt it be before saving image?
    owner = await business.owner

    if owner == user:
        business.logo = token_name
        await business.save()

    else:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Not authenticated to perform this acton",
            headers = {"WWW-Authenticate": "Bearer"}
        )
    file_url = "localhost:8000"+generated_name[1:]
    return {"status": "ok", "filename": file_url}

@app.post("/uploadfile/product/{id}")
async def create_upload_file(id: int, file: UploadFile = File(...), user: user_pydantic = Depends(get_current_user)):
    FILEPATH = "./static/images/"
    filename = file.filename
    extension = filename.split(".")[1]

    if extension not in ["png", "jpg"]:
        return {"status": "error", "detail": "File extension not allowed"}
    
    token_name = secrets.token_hex(10)+"."+extension
    generated_name = FILEPATH + token_name
    file_content = await file.read()

    with open(generated_name, "wb") as file:
        file.write(file_content)

    # PILLOW
    img = Image.open(generated_name)
    img = img.resize(size = (200, 200))
    img.save(generated_name)

    file.close()

    product = await Product.get(id = id)
    business = await product.business_owner
    owner = await business.owner

    if owner == user:
        product.product_image = token_name
        await product.save()

    else:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Not authenticated to perform this acton",
            headers = {"WWW-Authenticate": "Bearer"}
        )

# CRUD functionality

@app.post("/products")
async def add_new_product(product: product_pydanticIn, user: user_pydantic = Depends(get_current_user)):
    logger.info(f"New product being added by user: {user.username}")
    product = product.dict(exclude_unset = True)
    if product["original_price"] > 0:
        product["percentage_discount"] = ((product["original_price"] - product["new_price"])
                                          / product["original_price"]) * 100
        business = await Business.get(owner=user)
        product_obj = await Product.create(**product, business_owner=business)

        product_obj = await product_pydantic.from_tortoise_orm(product_obj)

        return {"status": "ok", "data": product_obj}
    
    else:

        return {"status": "error"}
    

@app.get("/product")
async def get_product():
    response = await product_pydantic.from_queryset(Product.all())
    return {"status": "ok", "data": response}


@app.get("/product/{id}")
async def get_product(id: int):
    product = await Product.get(id=id)
    business = await product.business_owner
    owner = await business.owner
    response = await product_pydantic.from_queryset_single(product.get(id=id))

    return {
        "status": "ok",
        "data": {
            "product_details": response,
            "business_details": {
                "name": business.business_name,
                "city": business.city,
                "region": business.region,
                "description": business.business_description,
                "logo": business.logo,
                "owner_id": owner.id,
                "business_id": business.id,
                "email": owner.email,
                "join_date": owner.join_date.strftime("%b %d %Y")
            }
        }
    }


@app.delete("/product/{id}")
async def delete_product(id: int, user: user_pydantic = Depends(get_current_user)):
    logger.info(f"Delete attempt for product ID {id} by user {user.username}")
    product = await Product.get(id=id)
    business = await product.business_owner
    owner = await business.owner
    
    if user == owner:
        await product.delete()
        #return {"status": "YAYA"}
    else:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Not authenticated to perform this acton",
            headers = {"WWW-Authenticate": "Bearer"}
        )

    return {"status": "ok"}


@app.put("/product/{id}")
async def update_product(id: int, update_info: product_pydanticIn, user: user_pydantic = Depends(get_current_user)):
    logger.info(f"Update attempt on product ID {id} by user {user.username}")
    product = await Product.get(id=id)
    business = await product.business_owner
    owner = await business.owner

    update_info = update_info.dict(exclude_unset=True)
    update_info["date_published"] = datetime.utcnow()

    if user == owner and update_info["original_price"] > 0:
        update_info["percentage_discount"] = ((update_info["original_price"] - update_info["new_price"])
                                              / update_info["original_price"]) * 100
        product = await product.update_from_dict(update_info)
        await product.save()
        response = await product_pydantic.from_tortoise_orm(product)
        return {"status": "ok", "data": response}
    else:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Not authenticated or invalid input",
            headers = {"WWW-Authenticate": "Bearer"}
        )
    

@app.post("/business/{id}")
async def update_business(id: int, update_business: business_pydanticIn, user: user_pydantic=Depends(get_current_user)):
    logger.info(f"Business update request for business ID {id} by user {user.username}")
    update_business = update_business.dict()
    business = await Business.get(id=id)
    business_owner = await business.owner

    if user == business_owner:
        await business.update_from_dict(update_business)
        business.save()
        response = await business_pydantic.from_tortoise_orm(business)
        return {"status": "ok", "data": response}
    
    else:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Not authenticated or invalid input",
            headers = {"WWW-Authenticate": "Bearer"}
        )




register_tortoise(
    app,
    db_url = "sqlite://database.sqlite3",
    modules = {"models": ["models"]},
    generate_schemas = True,
    add_exception_handlers = True

)