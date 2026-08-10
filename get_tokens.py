import requests

# 🔹 ЗАПОЛНИТЕ ЭТИ 5 ЗНАЧЕНИЙ:
CLIENT_ID = "54654494"
CLIENT_SECRET = "ee0ca5a1ee0ca5a1ee0ca5a17eed4d53bfeee0cee0ca5a18432cf6fef48ce6d1d4c4b29"
AUTHORIZATION_CODE = "vk2.a.bxDaJO8arZGcbj4tefc9R2HEADVb-_0SNxa_D39iZtiU9UkpPVVbLtqD7oMeKP-Nd7phVLQROxmFXzaJZDAVJsFsYZ8YDknyo9ok8-Aoj-M1mBy_FD5w6B2STlTwpYx6YXIu4Yz6coNaJCHjJ9L3JdppQUexCaW7wc0UaRmCH7XXHJFPAo1PUegXC3ECghkXo1Vx83V5OoYddat1E_Jz6jiid53uF2mXxkaVZAv3pCA"
DEVICE_ID = "Y1TxVp9j8pKQvsXP--JHk3RBW83grB7TPx7MjQMCUUHxCFPF4cVzSCPk7H8VICxa_qnTf0GW1vwJWK3506gHcw"
CODE_VERIFIER = "x4qBhEiKs-0whv054IBif41fEcBhn4UNMsVXBB23gHuukvde30VMXzmbSw3229v6eE5rU_3lEEIhQlvII7154Q"

REDIRECT_URI = "https://oauth.vk.com/blank.html"
TOKEN_URL = "https://id.vk.com/oauth2/auth"

payload = {
    'grant_type': 'authorization_code',
    'code': AUTHORIZATION_CODE,
    'redirect_uri': REDIRECT_URI,
    'client_id': CLIENT_ID,
    'client_secret': CLIENT_SECRET,
    'device_id': DEVICE_ID,
    'code_verifier': CODE_VERIFIER,
    'state': '12345'
}

headers = {'Content-Type': 'application/x-www-form-urlencoded'}

print("Обмениваем code на токены...")
response = requests.post(TOKEN_URL, data=payload, headers=headers)
data = response.json()

if "access_token" in data:
    print("\n✅ УСПЕХ! Сохраните эти данные в ваш .env файл:")
    print(f"VK_ACCESS_TOKEN={data['access_token']}")
    print(f"VK_REFRESH_TOKEN={data.get('refresh_token', '')}")
    print(f"VK_DEVICE_ID={DEVICE_ID}")
    print(f"VK_CODE_VERIFIER={CODE_VERIFIER}")
    print(f"VK_TOKEN_EXPIRES_AT={int(__import__('time').time()) + data.get('expires_in', 3600)}")
else:
    print("\n❌ ОШИБКА:", data)