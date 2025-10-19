from flask import Flask, render_template, request, jsonify
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

app = Flask(__name__)

# Load the pre-trained DialoGPT model and tokenizer
model_name = "microsoft/DialoGPT-medium"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name)

# Global chat history to maintain conversation context (list of token IDs)
chat_history_ids = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_response', methods=['POST'])
def get_response():
    global chat_history_ids
    user_input = request.form['msg']

    # Encode the new user input and add the eos_token
    new_user_input_ids = tokenizer.encode(user_input + tokenizer.eos_token, return_tensors='pt')

    # Append the new user input to the chat history
    bot_input_ids = torch.cat([chat_history_ids, new_user_input_ids], dim=-1) if chat_history_ids is not None else new_user_input_ids

    # Generate a response from the model (limit to 1000 tokens total history)
    chat_history_ids = model.generate(
        bot_input_ids,
        max_length=1000,
        pad_token_id=tokenizer.eos_token_id,
        do_sample=True,  # For more natural responses
        top_p=0.95,      # Nucleus sampling
        top_k=50         # Top-k sampling
    )

    # Decode the bot's response (extract only the new part after user input)
    bot_response = tokenizer.decode(chat_history_ids[:, bot_input_ids.shape[-1]:][0], skip_special_tokens=True)

    return jsonify({'response': bot_response})

if __name__ == '__main__':
    app.run(debug=True)