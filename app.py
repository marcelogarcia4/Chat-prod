import os
import json
import requests
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv
import logging # Import logging module

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)  # Enable CORS for all routes

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
RAPIDAPI_URL = "https://real-time-product-search.p.rapidapi.com/search"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat_with_ai():
    if not DEEPSEEK_API_KEY:
        app.logger.error("Deepseek API key not configured")
        return jsonify({"error": "Deepseek API key not configured"}), 500

    try:
        data = request.get_json()
        messages = data.get('messages')

        if not messages:
            app.logger.warning("No messages provided in chat request")
            return jsonify({"error": "No messages provided"}), 400

        system_prompt = {
            "role": "system",
            "content": (
                "You are a friendly and helpful product assistant. "
                "Your goal is to understand the user's needs through conversation. "
                "When you have enough information to suggest products, you MUST respond "
                "ONLY with a JSON object in the following format: "
                "{\"action\": \"search\", \"keywords\": [\"keyword1\", \"keyword2\", \"feature\"]}. "
                "The keywords array should contain relevant search terms based on user's request. "
                "Do not include any other text or explanation before or after the JSON object if you are outputting the search action. "
                "Otherwise, if you need more information or want to clarify, continue the conversation naturally. "
                "Do not ask if the user is ready to search, determine it yourself and then provide the JSON."
            )
        }

        payload = {
            "model": "deepseek-chat",
            "messages": [system_prompt] + messages,
            "max_tokens": 1024,
            "temperature": 0.7,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }

        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)

        ai_response = response.json()
        ai_message_content = ai_response.get("choices", [{}])[0].get("message", {}).get("content", "")

        app.logger.info(f"Deepseek raw response content: {ai_message_content}")

        action = None
        reply_to_user = ai_message_content # Default reply is the AI's content

        try:
            # Check if the message content is a valid JSON string for a search action
            # It's good to check if it starts and ends with curly braces for initial check
            if ai_message_content.strip().startswith("{") and ai_message_content.strip().endswith("}"):
                parsed_action = json.loads(ai_message_content)
                if isinstance(parsed_action, dict) and \
                   parsed_action.get("action") == "search" and \
                   isinstance(parsed_action.get("keywords"), list) and \
                   len(parsed_action["keywords"]) > 0:
                    action = parsed_action
                    reply_to_user = "Okay, I'm searching for products based on your request now!" # A friendly message to user
        except json.JSONDecodeError:
            # Not a JSON action, so it's a regular text message, continue with default reply_to_user
            pass

        return jsonify({
            "reply": reply_to_user, # Send the friendly message or regular chat reply
            "action": action
        })

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Deepseek API request error: {e.response.text if e.response else e}")
        return jsonify({"error": f"Error communicating with AI: {str(e)}"}), 500
    except Exception as e:
        app.logger.error(f"Unexpected error in /api/chat: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/search-products', methods=['GET'])
def search_products_api():
    if not RAPIDAPI_KEY:
        app.logger.error("RapidAPI key not configured")
        return jsonify({"error": "RapidAPI key not configured"}), 500

    query = request.args.get('q')
    if not query:
        app.logger.warning("Search query (q) parameter is missing")
        return jsonify({"error": "Search query (q) parameter is required"}), 400

    headers = {
        "x-rapidapi-host": "real-time-product-search.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY
    }

    params = {
        "q": query,
        "country": "us",
        "language": "en",
        "page": "1" # For simplicity, always fetch first page. Extend for pagination.
    }

    try:
        response = requests.get(RAPIDAPI_URL, headers=headers, params=params)
        response.raise_for_status() # Raise an exception for HTTP errors

        product_data = response.json()
        
        # CORRECTED: Access 'products' list which is inside 'data'
        products = product_data.get("data", {}).get("products", [])

        if not products:
            app.logger.info(f"No products found for query: {query}")
            return jsonify([]) # Return an empty list if no products

        return jsonify(products) # Return the list of products

    except requests.exceptions.RequestException as e:
        app.logger.error(f"RapidAPI request error: {e.response.text if e.response else e}")
        error_details = "Error communicating with product search API."
        if e.response is not None:
            try:
                error_resp = e.response.json()
                if "message" in error_resp:
                    error_details = error_resp["message"]
            except json.JSONDecodeError:
                error_details = f"Product API returned non-JSON error: {e.response.text}"
        return jsonify({"error": error_details}), 500
    except Exception as e:
        app.logger.error(f"Unexpected error in /api/search-products: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Ensure you are in 'debug=True' ONLY for development, not production
    app.run(debug=True, port=5000)
