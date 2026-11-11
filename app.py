"""Punto de entrada de la aplicación web: python app.py"""
from src.web import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
