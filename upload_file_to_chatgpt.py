import os
import json
from dotenv import load_dotenv
from openai import OpenAI
import requests
import base64

load_dotenv()

def process_pdf_with_gpt(_client, model, url, task):
    """
    Process a given PDF with ChatGPT by downloading and sending it as base64 data.
    
    Args:
        _client: The OpenAI client instance.
        model (str): The model to use for processing.
        url (str): The URL of the PDF to process.
        task (str): The task description for processing.
    
    Returns:
        str: The response from the ChatGPT API.
    
    Raises:
        Exception: If the API call or PDF download fails.
    """
    print(f"Downloading PDF from {url}...")
    response = requests.get(url)
    response.raise_for_status()
    pdf_base64 = base64.b64encode(response.content).decode('utf-8')
    data_url = f"data:application/pdf;base64,{pdf_base64}"
    print("PDF downloaded and encoded.")

    print("Sending PDF to GPT for processing...")
    response = _client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": task,
                    },
                    {
                        "type": "file",
                        "file": {
                            "filename": "document.pdf",
                            "file_data": data_url
                        }
                    },
                ],
            },
        ],
        extra_body={
            "plugins": [
                {
                    "id": "file-parser",
                    "pdf": {
                        "engine": "pdf-text"
                    },
                },
            ]
        }
    )
    
    print("Received response from API.")
    return response.choices[0].message.content

if __name__ == "__main__":
    # The API key is loaded from the .env file.
    # Make sure your .env file has: OPENROUTER_API_KEY="your_api_key"
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in environment variables.")

    CLIENT = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key
    )
    
    # Load the schema from the JSON config file
    with open('lcwip_results_schema.json', 'r') as f:
        schema_data = json.load(f)

    schema = schema_data['schema']
    
    # Construct the task from the schema
    prompts = [item['prompt'] for item in schema]
    basic_task = "Please answer the following questions based on the document:\n" + "\n".join(prompts)
    
    json_keys = [item['name'] for item in schema]
    extra_instructions = f"Output your data as a single JSON object. The keys of the JSON object should be: {', '.join(json_keys)}. Do not include any other text, only write the JSON file."
    
    task = f"{basic_task}\n\n{extra_instructions}"
    
    # Load the first 3 URLs from the database JSON file
    with open('LCWIP_database_v1.json', 'r') as dbfile:
        db_data = json.load(dbfile)
    url_list = [entry['pdf_url'] for entry in db_data[:3]]
    model = 'gpt-4o'

    results = []
    for url in url_list:
        try:
            print(f"Processing URL: {url}")
            response_text = process_pdf_with_gpt(CLIENT, model, url, task)
            print("Raw response from API:")
            print(response_text)
            try:
                # The response might be wrapped in ```json ... ```, so we need to extract it.
                if response_text.strip().startswith("```json"):
                    response_text = response_text.strip()[7:-3].strip()
                response = json.loads(response_text)
                print(json.dumps(response, indent=2))
                results.append(response)
            except json.JSONDecodeError:
                print("Failed to decode JSON from response.")
        except Exception as e:
            print(f"An error occurred: {e}")

    # Output all results to LCWIP_database_v2.json
    with open('LCWIP_database_v2.json', 'w') as outfile:
        json.dump(results, outfile, indent=2)
    print("Results written to LCWIP_database_v2.json")