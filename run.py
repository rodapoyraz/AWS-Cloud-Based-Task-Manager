from app import create_app
from dotenv import load_dotenv

load_dotenv()   # loads .env locally

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
