import os
from langchain.docstore.document import Document
from langchain_community.document_transformers import BeautifulSoupTransformer

# Directory containing the HTML files
html_dir = 'erasmus-site-parsed'
cleaned_data_dir = 'cleaned-data'

# Ensure the cleaned data directory exists
os.makedirs(cleaned_data_dir, exist_ok=True)

# Initialize BeautifulSoupTransformer
bs_transformer = BeautifulSoupTransformer()

def clean_html(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        html_content = file.read()
    document = [Document(page_content=html_content)]
    transformed_document = bs_transformer.transform_documents(document, tags_to_extract=["span", "table", "li", "d", "h1", "h2", "h3", "h4", "h5", "p"], unwanted_tags=["a"])[0]
    return transformed_document.page_content

def save_cleaned_data(file_name, text):
    clean_file_path = os.path.join(cleaned_data_dir, file_name)
    with open(clean_file_path, 'w', encoding='utf-8') as file:
        file.write(text)

def process_html_files():
    for file_name in os.listdir(html_dir):
        file_path = os.path.join(html_dir, file_name)
        if os.path.isfile(file_path) and file_name.endswith('.html'):
            cleaned_text = clean_html(file_path)
            save_cleaned_data(file_name.replace('.html', '.txt'), cleaned_text)

if __name__ == '__main__':
    process_html_files()
    print("HTML content cleaned and saved successfully!")
