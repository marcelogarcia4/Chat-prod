import os
import json
import requests
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv

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
        return jsonify({"error": "Deepseek API key not configured"}), 500

    try:
        data = request.get_json()
        messages = data.get('messages')

        if not messages:
            return jsonify({"error": "No messages provided"}), 400

        system_prompt = {
            "role": "system",
            "content": (
                "You are a friendly and helpful product assistant. "
                "Your goal is to understand the user's needs through conversation. "
                "When you have enough information to suggest products, you MUST respond "
                "ONLY with a JSON object in the following format: "
                "{\"action\": \"search\", \"keywords\": [\"keyword1\", \"keyword2\", \"feature\"]}. "
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
        response.raise_for_status()  # Raise an exception for HTTP errors

        ai_response = response.json()
        ai_message_content = ai_response.get("choices", [{}])[0].get("message", {}).get("content", "")

        # Attempt to parse the AI's message as JSON for a search action
        action = None
        try:
            # Check if the message content is a valid JSON string
            if ai_message_content.strip().startswith("{") and ai_message_content.strip().endswith("}"):
                parsed_action = json.loads(ai_message_content)
                if isinstance(parsed_action, dict) and parsed_action.get("action") == "search" and "keywords" in parsed_action:
                    action = parsed_action
                    # If it's an action, we don't want to send the JSON as a message to the user
                    ai_message_content = "Okay, I'll search for that now!"
        except json.JSONDecodeError:
            # Not a JSON action, so it's a regular text message
            pass

        return jsonify({
            "reply": ai_message_content,
            "action": action
        })

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Deepseek API request error: {e}")
        return jsonify({"error": f"Error communicating with AI: {str(e)}"}), 500
    except Exception as e:
        app.logger.error(f"Error in /api/chat: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/search-products', methods=['GET'])
def search_products_api():
    if not RAPIDAPI_KEY:
        return jsonify({"error": "RapidAPI key not configured"}), 500

    query = request.args.get('q')
    if not query:
        return jsonify({"error": "Search query (q) parameter is required"}), 400

    headers = {
        "x-rapidapi-host": "real-time-product-search.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY
    }

    params = {
        "q": query,
        "country": "us",
        "language": "en",
        "page": "1"
    }

    try:
        response = requests.get(RAPIDAPI_URL, headers=headers, params=params)
        response.raise_for_status() # Raise an exception for HTTP errors

        product_data = response.json()
        if product_data.get("status") == "OK" and product_data.get("data"):
             return jsonify(product_data["data"])
        elif product_data.get("status") == "OK" and not product_data.get("data"):
            return jsonify([]) # No products found
        else:
            return jsonify({"error": "Failed to fetch products", "details": product_data.get("message", "Unknown error")}), 500

    except requests.exceptions.RequestException as e:
        app.logger.error(f"RapidAPI request error: {e}")
        # Try to parse error response from RapidAPI if available
        error_details = "Error communicating with product search API."
        try:
            error_resp = e.response.json()
            if "message" in error_resp:
                error_details = error_resp["message"]
        except: # If parsing response fails, use generic error
            pass
        return jsonify({"error": error_details}), 500
    except Exception as e:
        app.logger.error(f"Error in /api/search-products: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
