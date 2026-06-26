import requests

CLIENT_ID = "54654494"
CLIENT_SECRET = "jMg5lVyg8HbjtkuMtX2d"  # из настроек приложения
REDIRECT_URI = "https://oauth.vk.com/blank.html"
CODE = "ВСТАВЬ_СЮДА_CODE_ИЗ_URL"      # то, что получил после авторизации

url = "https://oauth.vk.com/access_token"
params = {
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "redirect_uri": REDIRECT_URI,
    "code": CODE
}

r = requests.post(url, data=params)
r.raise_for_status()
data = r.json()

print("✅ НОВЫЙ ТОКЕН:", data["access_token"])
print("scope:", data.get("scope"))
print("user_id:", data.get("user_id"))
