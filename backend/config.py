"""Limites configuráveis no ambiente; tamanhos em MiB."""
import os

def positive_int(name,default):
    try: value=int(os.getenv(name,str(default)))
    except ValueError: raise ValueError(f'{name} deve ser um número inteiro positivo.') from None
    if value<1: raise ValueError(f'{name} deve ser um número inteiro positivo.')
    return value

MAX_FEATURES=positive_int('MAX_FEATURES',500000)
MAX_UPLOAD_MB=positive_int('MAX_UPLOAD_MB',200)
MAX_ZIP_MB=positive_int('MAX_ZIP_MB',500)
MAX_ZIP_FILES=positive_int('MAX_ZIP_FILES',5000)
