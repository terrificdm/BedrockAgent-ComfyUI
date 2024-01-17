import os
import json
import random
from urllib import request, parse

server_address = os.environ['server_address']
prompt_text = os.environ['prompt_text']

def lambda_handler(event, context):
    print(event)
    
    api_path = event['apiPath']
    image_description = next((parameter['value'] for parameter in event['parameters'] if parameter['name'] == 'description'), None)
    print(image_description)
  
    def queue_prompt(prompt):
        p = {"prompt": prompt}
        data = json.dumps(p).encode('utf-8')
        req =  request.Request("http://{}/prompt".format(server_address), data=data)
        # request.urlopen(req)
        return json.loads(request.urlopen(req).read())
      
    def get_history(prompt_id):
        while True:
          with request.urlopen("http://{}/history/{}".format(server_address, prompt_id)) as response:
            data = json.loads(response.read())
            if data:
              return data
        
    def get_image(filename, subfolder, folder_type):
        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url_values = parse.urlencode(data)
        image_url = "http://{}/view?{}".format(server_address, url_values)

        return image_url
      
    prompt = json.loads(prompt_text)
    
    #set the text prompt for our positive and negtive CLIPTextEncode
    prompt["6"]["inputs"]["text"] = prompt["15"]["inputs"]["text"] = image_description
    negative_prompt = "ugly, disfigured, distorted body, bad anatomy, bad hands, text, watermark"
    prompt["7"]["inputs"]["text"] = prompt["16"]["inputs"]["text"] = negative_prompt
    
    #set the seed for our KSampler node
    random_integer = random.randint(1, 18446744073709551615)
    prompt["10"]["inputs"]["noise_seed"] = random_integer
    
    if api_path == '/createImage':
        resp = queue_prompt(prompt)
        prompt_id = resp['prompt_id']
    
        history = get_history(prompt_id)[prompt_id]
    
        output_images = {}
        for node_id in history['outputs']:
          node_output = history['outputs'][node_id]
          if 'images' in node_output:
            images_output = []
            for image in node_output['images']:
              image_data = get_image(image['filename'], image['subfolder'], image['type'])
              images_output.append(image_data)
          output_images[image_description] = images_output
    else:
        response_code = 404
        output_images = f"Unrecognized api path: {action_group}::{api_path}"
    
    response_body = {
        'application/json': {
            'body': output_images
        }
    }
    
    action_response = {
        'actionGroup': event['actionGroup'],
        'apiPath': event['apiPath'],
        'httpMethod': event['httpMethod'],
        'httpStatusCode': 200,
        'responseBody': response_body
    }
    
    session_attributes = event['sessionAttributes']
    prompt_session_attributes = event['promptSessionAttributes']
    
    api_response = {
        'messageVersion': '1.0', 
        'response': action_response,
        'sessionAttributes': session_attributes,
        'promptSessionAttributes': prompt_session_attributes
    }
    
    print(api_response)
    
    return api_response
    

