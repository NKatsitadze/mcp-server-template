"""Fake API payloads in the example API's real shapes, with personal data that must never leak."""

EMAIL = "leak-check@example.test"
PHONE = "555-0100-LEAK"
STREET = "Leakage Street"

USER = {
    "id": 1,
    "name": "Leanne Graham",
    "username": "Bret",
    "email": EMAIL,
    "phone": PHONE,
    "website": "leak.example.test",
    "address": {"street": STREET, "suite": "Apt. 1", "city": "Town", "zipcode": "000", "geo": {"lat": "1"}},
    "company": {"name": "Romaguera-Crona", "catchPhrase": "x", "bs": "y"},
}
USER_3 = {**USER, "id": 3, "name": "Clementine Bauch", "username": "Samantha", "company": {"name": "R-J"}}
USERS = [USER, USER_3]

TODOS = [
    {"userId": 1, "id": 1, "title": "first todo", "completed": False},
    {"userId": 1, "id": 2, "title": "second todo", "completed": True},
    {"userId": 1, "id": 3, "title": "third todo", "completed": False},
]
POSTS = [
    {"userId": 1, "id": 1, "title": "hello world", "body": "nesciunt body"},
    {"userId": 1, "id": 2, "title": "other title", "body": "plain"},
]
LEAKS = (EMAIL, PHONE, STREET, "leak.example.test")
