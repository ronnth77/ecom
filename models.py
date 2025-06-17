from tortoise.models import Model #When you define a class that inherits from Model, you're creating a representation of a table in your database. Each attribute defined with a fields.*Field is a column in that table.
from tortoise import fields # Field module is a submodule of Tortoise ORM that provides field definitions for model classes. Each item in fields corresponds to a type of column you would find in a relational database.
from datetime import datetime
from tortoise.contrib.pydantic import pydantic_model_creator
""" It converts Tortoise ORM models (like User, Business, Product) into Pydantic schemas, which are typically used for:

Request validation (e.g. when creating or updating data)

Response serialization (e.g. when returning data to the client)

📌 Why It's Used:
Manually creating Pydantic schemas for each model can be repetitive. pydantic_model_creator reduces boilerplate by automatically generating them from the Tortoise model definitions.

🔍 Example:
Let's say you have this Tortoise ORM model:

python
Copy
Edit
class User(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=20)
    email = fields.CharField(max_length=100)
You can generate a Pydantic schema like this:

python
Copy
Edit
from tortoise.contrib.pydantic import pydantic_model_creator

user_pydantic = pydantic_model_creator(User, name="User")
Now, user_pydantic is a Pydantic class that you can use in FastAPI like this:

python
Copy
Edit
@app.get("/users/{id}", response_model=user_pydantic)
async def get_user(id: int):
    user = await User.get(id=id)
    return await user_pydantic.from_tortoise_orm(user)"""

class User(Model):
    id = fields.IntField(pk=True, index=True)
    username = fields.CharField(max_length=20, null=False, unique=True)
    email = fields.CharField(max_length=200, null=False, unique=True)
    password = fields.CharField(max_length=100, null=False)
    is_verified = fields.BooleanField(default=False)
    join_date = fields.DatetimeField(default=datetime.utcnow)

class Business(Model):
    id = fields.IntField(pk=True, index=True)
    business_name = fields.CharField(max_length=20, null=False, unique=True)
    city = fields.CharField(max_length=100, null=False, default="Unspecified")
    region = fields.CharField(max_length=100, null=False, default="Unspecified")
    business_description = fields.TextField(null=True)
    logo = fields.CharField(max_length=200, null=False, default="default.jpg")
    owner = fields.ForeignKeyField("models.User", related_name="businesses")
    """This means:

Each Business has one owner, who is a User.

Each User can have many businesses.

This is equivalent to a FOREIGN KEY (owner_id) REFERENCES user(id) in SQL.

🔎 Let’s break it down:
📄 Business model:
python
Copy
Edit
class Business(Model):
    ...
    owner = fields.ForeignKeyField("models.User", related_name="businesses")
"models.User": This is a string reference to the User model, to avoid circular import issues.

related_name="businesses": This tells Tortoise to add a reverse relation so that you can do user.businesses to get all businesses owned by that user.

🔧 What it does behind the scenes:
It creates a column like this in the Business table:

sql
Copy
Edit
owner_id INTEGER REFERENCES user(id)
And allows you to do:

Forward Access (from Business to User):
python
Copy
Edit
business = await Business.get(id=1)
owner = await business.owner  # This fetches the related User object
Reverse Access (from User to Business list):
python
Copy
Edit
user = await User.get(id=1)
businesses = await user.businesses.all()  # Thanks to related_name="businesses"
✅ Real Example:
python
Copy
Edit
# Create a user
user = await User.create(username="bob", email="bob@mail.com", password="123")

# Create a business for that user
business = await Business.create(business_name="Bob's Burgers", owner=user)

# Fetch owner from business
owner = await business.owner
print(owner.username)  # "bob"

# Fetch businesses from user
user_businesses = await user.businesses.all()
print([b.business_name for b in user_businesses])  # ["Bob's Burgers"]
"""

class Product(Model):
    id = fields.IntField(pk=True, index=True)
    name = fields.CharField(max_length=100, null=False, unique=True)
    category = fields.CharField(max_length=30, index=True)
    original_price = fields.DecimalField(max_digits=12, decimal_places=2)
    new_price = fields.DecimalField(max_digits=12, decimal_places=2)
    percentage_discount = fields.IntField()
    offer_expiration_date = fields.DateField(default=datetime.utcnow)
    product_image = fields.CharField(max_length=200, null=False, default="productDefault.jpg")
    business_owner = fields.ForeignKeyField("models.Business", related_name="products")


# Pydantic Schemas
user_pydantic = pydantic_model_creator(User, name="User", exclude=("is_verified",))
user_pydanticIn = pydantic_model_creator(User, name="UserIn", exclude_readonly=True, exclude=("is_verified", "join_date"))
user_pydanticOut = pydantic_model_creator(User, name="UserOut", exclude=("password",))

business_pydantic = pydantic_model_creator(Business, name="Business")
business_pydanticIn = pydantic_model_creator(Business, name="BusinessIn", exclude_readonly=True)

product_pydantic = pydantic_model_creator(Product, name="Product")
product_pydanticIn = pydantic_model_creator(Product, name="ProductIn", exclude=("percentage_discount", "id"))

"""✅ 1. user_pydantic → General Model (exclude is_verified)
python
Copy
Edit
exclude=("is_verified",)
This model includes all fields from the User model except is_verified.

Useful if you don't want the is_verified status exposed or accepted by default.

Can be used for general views or documentation where this field shouldn't be visible.

✅ 2. user_pydanticIn → Input Schema (for creating users)
python
Copy
Edit
exclude_readonly=True
exclude_readonly=True excludes read-only fields, like:

id (auto-generated)

join_date (has a default)

This makes sure clients only provide fields they're allowed to set manually, like:

username, email, password

✅ Used for:

python
Copy
Edit
@app.post("/users", response_model=UserOut_Pydantic)
async def create_user(user: UserIn_Pydantic):
    ...
✅ 3. user_pydanticOut → Output Schema (for returning users)
python
Copy
Edit
exclude_readonly=("password",)
This is a bit tricky — here, you're using exclude_readonly=("password",) but it likely should be:

python
Copy
Edit
exclude=("password",)
password is not a read-only field, so exclude_readonly=("password",) won't exclude it.

To remove password from the output, use:

python
Copy
Edit
exclude=("password",)
✅ Purpose: Prevent exposing sensitive fields (like passwords) when returning user data."""