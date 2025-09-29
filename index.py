import os
import json
import re
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import google.generativeai as genai
import tempfile
from werkzeug.utils import secure_filename
import fitz  # PyMuPDF
# Load API key from .env
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY is not set")
genai.configure(api_key=api_key)

app = Flask(__name__)

# Use the right model name for your account
model = genai.GenerativeModel("gemini-2.5-flash")  # Change if needed

# Utility function for file handling
def save_uploaded_file(file):
    """Save uploaded file to temp location and return filepath"""
    if not file or not file.filename:
        return None
    
    filename = secure_filename(file.filename)
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        file.save(tmp_file.name)
        return tmp_file.name
    return None

@app.route('/extract_text', methods=['POST'])
def extract_text():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename.endswith('.pdf'):
        return jsonify({'error': 'Only PDF files allowed'}), 400

    filepath = save_uploaded_file(file)
    if not filepath:
        return jsonify({'error': 'Failed to save file'}), 500

    try:
        
        doc = fitz.open(filepath)
        all_text = ""
        for page in doc:
            page_text = page.get_text()
            all_text += page_text + "\n"
        doc.close()
        # Replace actual line breaks with literal "\n" for JSON
        all_text = all_text.replace('\n', '\\n')
        # return jsonify({"text": all_text})
        noisy_text = all_text

        if not noisy_text:
            return jsonify({"error": "No text provided"}), 400

        prompt = f"""
                    Convert the following noisy text into valid JSON.

                    Follow this schema strictly (keys must not be missing, even if values are empty):

                    {{
                    "AckDate": "string",
                    "AckNo": "string",
                    "IRN": "string",
                    "amountInWords": "string",
                    "bankDetails": {{
                        "IFSC": "string",
                        "accountHolder": "string",
                        "accountNo": "string",
                        "bankName": "string",
                        "branch": "string"
                    }},
                    "buyer": {{
                        "GSTIN": "string",
                        "address": "string",
                        "name": "string",
                        "state": "string",
                        "stateCode": "string"
                    }},
                    "companyPAN": "string",
                    "consignee": {{
                        "GSTIN": "string",
                        "address": "string",
                        "name": "string",
                        "state": "string",
                        "stateCode": "string"
                    }},
                    "deliveryNoteDate": "string",
                    "invoiceNo": "string",
                    "items": [
                        {{
                        "SlNo": 0,
                        "description": "string",
                        "HSN": "string",
                        "quantity": "string",
                        "rate": "string",
                        "amount": "string",
                        "GST": "string",
                        "CGST": "string",
                        "SGST": "string"
                        }}
                    ],
                    "placeOfSupply": "string",
                    "supplier": {{
                        "FSSAI": "string",
                        "GSTIN": "string",
                        "address": "string",
                        "name": "string",
                        "state": "string",
                        "stateCode": "string"
                    }},
                    "taxAmountInWords": "string",
                    "taxSummary": {{
                        "HSN": "string",
                        "centralTax": "string",
                        "stateTax": "string",
                        "taxableValue": "string",
                        "totalTax": "string"
                    }},
                    "total": "string"
                    }}

                    Now clean and extract data from this text:
                    {noisy_text}

                    Output ONLY valid JSON without markdown or explanations.
                    """


        response = model.generate_content(prompt)

        raw_output = response.text
        cleaned_output = clean_json_output(raw_output)

        try:
            json_data = json.loads(cleaned_output)
        except json.JSONDecodeError:
            return jsonify({"error": "Model output is not valid JSON", "raw_output": raw_output}), 500

        return jsonify(json_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)


def clean_json_output(text):
    """Remove Markdown fences and extract JSON."""
    # Remove ```json ... ``` or ``` ... ```
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return cleaned

@app.route("/text-to-json", methods=["POST"])
def text_to_json():
    
    try:
        data = request.get_json()
        
        noisy_text = data.get("text", "")

        if not noisy_text:
            return jsonify({"error": "No text provided"}), 400

        prompt = f"""
        Convert the following noisy text into valid JSON:
        {noisy_text}
        Output ONLY JSON without markdown code blocks or explanations.
        """

        response = model.generate_content(prompt)

        raw_output = response.text
        cleaned_output = clean_json_output(raw_output)

        try:
            json_data = json.loads(cleaned_output)
        except json.JSONDecodeError:
            return jsonify({"error": "Model output is not valid JSON", "raw_output": raw_output}), 500

        return jsonify(json_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
if __name__ == "__main__":
    # For local development only
    app.run(host="0.0.0.0", port=5000, debug=True)
