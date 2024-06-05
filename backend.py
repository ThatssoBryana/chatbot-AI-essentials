import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from flask import Flask, request, jsonify, render_template
import os
import logging
from dotenv import load_dotenv
from langchain.docstore.document import Document
from langchain_community.document_transformers import BeautifulSoupTransformer

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure Azure OpenAI API key and endpoint from environment variables
API_KEY = os.getenv('API_KEY')
ENDPOINT = os.getenv('ENDPOINT')
DEPLOYMENT_ID = os.getenv('DEPLOYMENT_ID')

# Base URL for scraping
base_url = "https://www.erasmushogeschool.be/nl/opleidingen"

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Function to scrape links and save HTML content
def scrape_and_save_links():
    try:
        # Make a request to the website
        r = requests.get(base_url)
        soup = BeautifulSoup(r.content, 'html.parser')

        # Find all links on page
        links = soup.findAll('a')

        # Filter and save the links
        for link in links:
            href = link.get('href')
            if href and (href.startswith('/nl/opleidingen/') or 
                         (href.startswith('https://www.erasmushogeschool.be/nl/') and 
                          not href.startswith('https://www.erasmushogeschool.be/nl/opleidingen') and 
                          href.count('/') == 4)):
                full_url = urljoin(base_url, href)
                file_name = full_url.replace('https://www.erasmushogeschool.be/nl/', '').replace('/', '_') + '.html'
                # Make a request to the link
                r = requests.get(full_url)
                soup = BeautifulSoup(r.content, 'html.parser')
                # Write the parsed content to a file
                with open(f"erasmus-site-parsed/{file_name}", "w", encoding='utf-8') as file:
                    file.write(str(soup.prettify()))
        logging.info("Links scraped and HTML content saved successfully!")
    except Exception as e:
        logging.error(f"An error occurred while scraping: {e}")

# Function to clean and process HTML files
def process_html_files():
    bs_transformer = BeautifulSoupTransformer()
    cleaned_contents = []

    for file_name in os.listdir('erasmus-site-parsed'):
        if file_name.endswith('.html'):
            with open(f'erasmus-site-parsed/{file_name}', 'r', encoding='utf-8') as file:
                html_content = file.read()
                
            # Limit the context length to 1000 characters
            context_length = 1000
            truncated_html = html_content[:context_length]

            document = [Document(page_content=truncated_html)]
            doc_transformed = bs_transformer.transform_documents(
                document, 
                tags_to_extract=["span", "table", "li", "d", "h1", "h2", "h3", "h4", "h5", "p"], 
                unwanted_tags=["a"]
            )[0]
            cleaned_contents.append(doc_transformed.page_content)

    # Concatenate all the cleaned contents
    all_cleaned_content = ' '.join(cleaned_contents)
    return all_cleaned_content

# Function to tokenize a text and count tokens
def count_tokens(text):
    return len(text.split())

# Route for scraping links and saving HTML content
@app.route('/scrape')
def scrape_links():
    scrape_and_save_links()
    return "Links scraped and HTML content saved successfully!"

# Route for handling questions
@app.route('/ask', methods=['POST'])
def ask_question():
    user_question = request.json.get('question')

    # Clean and process HTML files
    cleaned_content = process_html_files()

    # Define the maximum token limit for the prompt
    max_total_tokens = 8192
    max_completion_tokens = 300
    max_prompt_tokens = max_total_tokens - max_completion_tokens

    # Token counts for question and available tokens for content
    user_question_tokens = count_tokens(user_question)
    available_tokens_for_content = max_prompt_tokens - user_question_tokens - 10  # Buffer for additional tokens

    # Log the token counts for debugging
    logging.debug(f"User question tokens: {user_question_tokens}")
    logging.debug(f"Available tokens for content: {available_tokens_for_content}")

    if available_tokens_for_content <= 0:
        return jsonify({'answer': 'The question is too long.'})

    # Trim the cleaned content to fit within the available tokens
    cleaned_content_tokens = cleaned_content.split()
    trimmed_content_tokens = cleaned_content_tokens[:available_tokens_for_content]
    trimmed_content = ' '.join(trimmed_content_tokens)

    # Log the trimmed content length for debugging
    logging.debug(f"Trimmed content tokens: {len(trimmed_content.split())}")

    # Construct the prompt with the trimmed content and the user's question
    prompt = f"{trimmed_content}\n\nQuestion: {user_question}\nAnswer:\n"

    # Ensure prompt is clean and contains no unintended content
    prompt = prompt.strip()
    prompt = prompt.replace('\n\nQuestion:', ' Question:').replace('\nAnswer:', ' Answer:')

    # Log the prompt length for debugging
    logging.debug(f"Prompt tokens: {count_tokens(prompt)}")

    # Send the question to Azure OpenAI
    headers = {
        'Content-Type': 'application/json',
        'api-key': API_KEY
    }
    payload = {
        'prompt': f"{cleaned_content}\n\nQuestion: {user_question}\nAnswer:",
        'max_tokens': max_completion_tokens,
        'stop': ['\n']  
    }

    response = requests.post(f"{ENDPOINT}/openai/deployments/{DEPLOYMENT_ID}/completions?api-version=2022-12-01", headers=headers, json=payload)

    # Log the response text
    logging.debug(f"Response text: {response.text}")

    if response.status_code == 200:
        result = response.json()
        response_text = result['choices'][0]['text'].strip()

        # Extract the relevant answer
        answer = response_text.split('\n')[0].strip()
    else:
        answer = "Er is een fout opgetreden bij het genereren van een antwoord."

    return jsonify({'answer': answer})

# Route for root URL to render the HTML form
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    # Run the Flask app
    app.run(debug=True)

