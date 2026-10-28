"""Normalización de órdenes sin alterar los argumentos de archivos o notas."""
import re
import unicodedata


def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.casefold())
                   if unicodedata.category(c) != 'Mn').strip(' ¿?¡!.,:;')


def clean_request(text):
    text = unicodedata.normalize('NFC', text)
    text = re.sub(r'\s+', ' ', text).strip(' ¿?¡!.,:;')
    prefixes = (
        r'por favor[, ]+',
        r'(?:(?:me )?(?:puedes|podrias)|puede usted|podria usted)\s+',
        r'(?:quiero|necesito) que\s+',
        r'(?:hazme|haga) el favor de\s+',
    )
    for _ in range(3):
        previous = text
        for pattern in prefixes:
            match = re.match(pattern, fold(text))
            if match:
                text = text[match.end():].lstrip()
                break
        if previous == text:
            break
    # La cortesía final se elimina solo cuando está separada de la petición.
    match = re.search(r'[, ]+por favor$', fold(text))
    if match:
        text = text[:match.start()].rstrip(' ,')
    # Formas frecuentes en una petición dirigida al asistente.
    verbs = {'abrir': 'abre', 'abrirme': 'abre', 'abreme': 'abre',
             'muéstrame': 'muestra', 'muestrame': 'muestra',
             'buscar': 'busca', 'buscarme': 'busca', 'buscame': 'busca',
             'pausar': 'pausa', 'reanudar': 'reanuda'}
    first, sep, rest = text.partition(' ')
    verb = verbs.get(fold(first))
    if verb:
        text = verb + (sep + rest if sep else '')
    return text.strip(' ¿?¡!.,:;')


def wake_command(text, words):
    """El nombre debe encabezar la frase; conserva la orden que lo sigue."""
    text = unicodedata.normalize('NFC', text).strip(' ¿?¡!.,:;')
    names = '|'.join(re.escape(fold(word)) for word in sorted(words, key=len, reverse=True))
    match = re.match(r'^(?:(?:oye|hola|hey|ok|okay)\s+)?(?:' + names + r')(?!\w)[\s,.:;!?¿¡-]*', fold(text))
    return text[match.end():].strip(' ¿?¡!.,:;') if match else None


def is_stop_request(text):
    return fold(clean_request(text)) in {
        'detente', 'detenerte', 'detenete', 'deten', 'parate', 'para', 'parar',
        'te detengas', 'te pares', 'pares', 'dejes de escuchar', 'no escuches mas',
        'ya no escuches', 'deten tu funcionamiento', 'deten el asistente',
        'deja de escuchar', 'para de escuchar', 'dejar de escuchar', 'deja de escucharme',
        'deja de hablar', 'dejar de hablar', 'silencio', 'callate', 'apagate',
        'cierra jarvis', 'cerrar jarvis', 'salir', 'terminar', 'termina', 'adios', 'hasta luego'}
