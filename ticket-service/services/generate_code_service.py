import random
import string

def generate_code(length=6):
    characters = string.ascii_uppercase + string.digits  # Letras maiúsculas e números
    return ''.join(random.choice(characters) for _ in range(length))
