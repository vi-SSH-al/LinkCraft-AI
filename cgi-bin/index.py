#!/usr/bin/env python3
import os
import cgi
import requests
import openai
import time
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np


print("Content-type: text/html\n")
openai.api_key = ''
ACCESS_TOKEN = ""
# PERSON_URN = ""
PERSON_URN = ""



form = cgi.FieldStorage()
post_topic = form.getvalue("post_topic")
target = form.getvalue("target")
num_of_days = form.getvalue("num_of_days")
num_of_days = int(num_of_days) if num_of_days is not None else 1
target_audience = form.getvalue("target_audience")

prompt = f"You are an expert technical content writer who focuses on LinkedIn Post. Each post must be under 600 characters. Write about: Topic: {post_topic}\nTarget: {target}\nTarget Audience: {target_audience}\nGenerate content for the post:"
imageprompt=f"We are a comapny of {post_topic}\nGenerate image for the post:"


def generate_image(imageprompt, post_topic):
    response = openai.Image.create(
        prompt=imageprompt,
        n=1,
        size="512x512",
    )

    if "data" in response and isinstance(response["data"], list) and len(response["data"]) > 0:
        image_data = response["data"][0]
        image_url = image_data.get("url")
        if image_url:
            image = Image.open(requests.get(image_url, stream=True).raw)

            # Convert PIL image to OpenCV format
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

            # Define the box coordinates and color
            x1, y1, x2, y2 = 100, 100, 400, 200
            box_color = (240, 240, 240)  # Light gray color in BGR format

            # Create a mask for the transparent box
            box_mask = np.zeros(cv_image.shape, dtype=np.uint8)
            cv2.rectangle(box_mask, (x1, y1), (x2, y2), box_color, -1)

            # Make the box transparent
            transparency = 0.5  # Set the transparency level (0.0 to 1.0)
            cv_image = cv2.addWeighted(cv_image, 1 - transparency, box_mask, transparency, 0)

            # Define the font and text color
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.8
            text_color = (0, 0, 0)  # Black color in BGR format

            # Get the size of the text
            (text_width, text_height), _ = cv2.getTextSize(post_topic, font, font_scale, 1)

            # Calculate the position to center the text within the box
            text_x = x1 + (x2 - x1 - text_width) // 2
            text_y = y1 + (y2 - y1 + text_height) // 2

            # Put the post_topic text on the image
            cv2.putText(cv_image, post_topic, (text_x, text_y), font, font_scale, text_color, 1)

            # Convert back to PIL format
            image_with_box = Image.fromarray(cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB))
            return image_with_box

    return None

def upload_image(image_path):
    url = "https://api.linkedin.com/v2/assets?action=registerUpload"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    data = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": PERSON_URN,
            "serviceRelationships": [{
                "relationshipType": "OWNER",
                "identifier": "urn:li:userGeneratedContent"
            }]
        }
    }
    
    # register image
    res_data = requests.post(url, json=data, headers=headers).json()
    
    # Get the upload url and binary image
    upload_url = res_data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
    asset = res_data["value"]["asset"]
    
    ## read the image
    with open(image_path, "rb") as image_file:
        image_data = image_file.read()
        
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }
    
    res = requests.post(upload_url, data=image_data, headers=headers)
    print(res.status_code)  
    
    return asset   

def post_to_linkedin(content, image_path):
    url = "https://api.linkedin.com/v2/ugcPosts"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    image_asset = upload_image(image_path)

    post_data = {
    "author": PERSON_URN,
    "lifecycleState": "PUBLISHED",
    "specificContent": {
        "com.linkedin.ugc.ShareContent": {
            "shareCommentary": {
                "text": content            
            },
            "shareMediaCategory": "IMAGE",
            "media": [
                {
                    "status": "READY",
                    "description": { "text": content }, 
                    "media": image_asset,
                    "title": { "text": "LinkedIn Post" }
                }
            ]
        }
    },
    "visibility": { "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC" }
}

    try:
        response = requests.post(url, json=post_data, headers=headers)
        response.raise_for_status()
        print(f"Successfully posted on LinkedIn: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error posting on LinkedIn: {e}")


image = generate_image(imageprompt,post_topic)

try:
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
    )
except Exception as e:
    print("Error:", e)

if response is not None:
    generated_content = response['choices'][0]['message']['content']

# Get the generated content from the response
generated_content = response['choices'][0]['message']['content']

# Save the generated content to a file
output_directory = './generated_images'
for day in range(1, num_of_days + 1):
    post_heading = generated_content
    image = generate_image(post_heading,post_topic)

    image_with_box_path = f"{output_directory}/image_with_box_day{day}.png"
    image.save(image_with_box_path)



    # Print the generated content and image for each day 
    print("<h1>LinkedIn Post Automator - Content Generated</h1>")
    print("<p>Generated Content for Day:", day, ":</p>")
    print("<p>", generated_content, "</p>")
    print("<p>Generated Image for Day:", day, ":</p>")
    print(f'<img src="{image_with_box_path}" alt="Generated Image" width="400">')

    # Save the generated content to a file for each day
    output_filename = f'cgi-bin/result_day{day}.txt'  
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write(generated_content)

    # Post to LinkedIn
    post_to_linkedin(generated_content, image_with_box_path)

    if day < num_of_days:
        time.sleep(24*60*60)

try:
    print("Location: /result_page.html\n")
except Exception as e:
    print("Error:", e)

