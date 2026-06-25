from vk_api.keyboard import VkKeyboard, VkKeyboardColor

def moderation_keyboard() -> str:
    keyboard = VkKeyboard(one_time=False, inline=True)
    keyboard.add_callback_button("Подтвердить", color=VkKeyboardColor.POSITIVE, payload={"action": "confirm"})
    keyboard.add_callback_button("Редактировать", color=VkKeyboardColor.PRIMARY, payload={"action": "edit"})
    keyboard.add_line()
    keyboard.add_callback_button(
        "Указать дату публикации",
        color=VkKeyboardColor.SECONDARY,
        payload={"action": "publish_date"},
    )
    keyboard.add_callback_button("Показать черновик", color=VkKeyboardColor.SECONDARY, payload={"action": "show_draft"})
    return keyboard.get_keyboard()

def back_keyboard() -> str:
    keyboard = VkKeyboard(one_time=False, inline=True)
    keyboard.add_callback_button("Назад", color=VkKeyboardColor.SECONDARY, payload={"action": "back"})
    return keyboard.get_keyboard()
