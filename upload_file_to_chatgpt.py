from openai import OpenAI
def process_file_from_url(_client, model, url, task):
    """
    Process a file from a given URL and upload it to ChatGPT.
    
    Args:
        client: The OpenAI client instance.
        model (str): The model to use for processing.
        url (str): The URL of the file to be processed.
        task (str): The task description for processing.
    
    Returns:
        dict: The response from the ChatGPT API after uploading the file.
    
    Raises:
        Exception: If the API call fails.

    Sample Usage:
    from openai import OpenAI
    CLIENT = OpenAI(api_key = your_api_key, default_headers={"Authorization": f"Bearer {your_api_key}"})
    
    url = https://api.liverpoolcityregion-ca.gov.uk/wp-content/uploads/2023/09/LCR-LCWIP-Final.pdf
    basic_task = "Please answer these two questions only.  Does the report in the file mention decarbonisation or a similar term such as climate emergency, net zero or climate change. If it does, please tell me how decarbonisation or similar is mentioned and tell me if what the plans are for implementation.  Make each plan a separate topic."
    extra_instructions = "output your data as a json file with the key being the point topic, and the value being a summary of the information.  do not include any other text, only write the json file." 
    task = f"{basic_task} {extra_instructions}" #note that if you want standard outputs you can add them to the extra instructions
    model = 'gpt-5-mini'
    
    for url in url_list:
        response = process_file_from_url(CLIENT, model, url, task)
        response = json.loads(response) # since I specified I wanted a json file, I can load the response as a json object. 
        print(response)

        # no exception handling here, but you can add it if you want to handle errors gracefully.
    


    """
    response = _client.responses.create(
        model=model,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": task,
                    },
                    {
                        "type": "input_file",
                        "file_url": url,
                    },
                ],
            },
        ]
    )
    
    
    return response.output[1].content[0].text