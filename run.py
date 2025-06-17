# Importujemy funkcję create_app z Twojego pakietu 'app'
# Ta linia odwołuje się do funkcji create_app z app/__init__.py
from app import create_app

# Wywołujemy funkcję create_app(), która zwraca skonfigurowaną instancję aplikacji Flask.
app = create_app()


if __name__ == '__main__':
    app.run(debug=True) # debug=True jest dobre dla rozwoju