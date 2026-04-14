#############################################
#  README.md
#
#  Script for ATS
#  
#  Situation: ATS uses change implementation documents before releasing to test team
#             for further testing/before releasing to PROD environment.
#             There are many change implementation documents that have important details.
#             It is a painful process to open them in MS word and read through the
#             document.
#  Solution: Therefore, this script will read through the folder with all the 
#            documents. Send them to an AI with OCR and image capabilities, and ask
#            the AI to create a JSON output. Then, we will create a simple web interface
#            with the database.
#############################################
import requests
import os
import base64
import json

from io import BytesIO
from pdf2image import convert_from_path
from src.classes import Logger

ID='39adbefa9e984e81a984f7034088ff68'
NAME='Create ATS Database'
DESCRIPTION='Create database by parsing PDF to IMAGE and extract information using AI'

def execute():
    
    logger = Logger(ID)
    
    # constants
    FOLDER_NAME="inputs"
    URL="http://192.168.4.128:5000/v1/chat/completions" # http://192.168.4.128:5000/v1/chat/completions
    
    logger.log(FOLDER_NAME)
    logger.log(URL)

    # create the standardised prompt
    # PROMPT = "Only do this: reply 'Hi!' in JSON format"
    PROMPT = """Role: You are a Data Extraction Specialist. Your task is to analyze a 'Change Implementation' document and extract specific fields into a structured JSON object for database ingestion.

INPUT:
The change implementation document 'typically' has this structure
- Overview
- Benefits/Justification
- Pre-Requisites and Applicability
- Implementation which consists of
  - Technical Information: Ignore any details written here
  - Proview Information
  - Validation
- Verification
- versions (or versions.xml)

INSTRUCTIONS:
1. Analyze the document sections: Overview, Benefits/Justification, Pre-Requisites, Implementation (Proview, Validation, Verification), and Versions.
2. IGNORE any section labeled "Technical Information".
3. Output MUST be valid JSON only. Do not include markdown code blocks (```json), comments, or explanations.
4. If a specific field is missing in the document, use "N/A" for strings, null for objects, or [] for arrays.
5. For "Validations" (which are phrased as questions), rewrite them as declarative sentences.
6. The most important data are pre-requisites, validations, job names, inventory data and versions (XML data).
7. For "Inventory", it is usually in the form of 'TXID="AA", Name="Inventory_column_name", Value="value"'. The TXID data consists of strictly 2 alphabets.
8. For "Versions" (XML data), break it down to "checksum", "packagename", timestamp", "maj", "min", "rel" and "bld". Use "N/A" if it does not exist.

REQUIRED JSON STRUCTURE:
{
    "overview": "String: Short summary of the document.",
    "jira_ticket": "String: JIRA ID if found, otherwise 'N/A'.",
    "benefits_justification": [
        "String: Bullet point summary of benefits."
    ],
    "pre_requisites_applicability": {
        "manufacturer": "String: (e.g., NCR, DN Series, CINEO or WN)",
        "models": "String: List of models",
        "application": "String: Application context"
    },
    "proview_information": [
        {
            "overview": "String: Proview overview if exists, else 'N/A'",
            "job_names": [
                "String: List of job names"
            ],
            "validations": [
                "String: Validation criteria converted to full sentences"
            ],
            "verifications": [
                {
                    "information": "String: Summary of key details (registries, file checks)",
                    "inventory_data": [
                        "String: 'TXID=txid, Name=name, Value=value'"
                    ],
                    "versions": [
                        {
                            "packagename": "String: the value inside <PACKAGENAME>, else 'N/A'",
                            "checksum": "String: the checksum inside <CHECKSUM>, else 'N/A'",
                            "timestamp": "String: the value inside <TIMESTAMP>, else 'N/A'",
                            "version": "String: MAJ.MIN.REL.BLD format, else 'N/A'",
                        }
                    ]
                }
            ]
        }
    ],
    "other_information": [
        "String: Any other key details not captured above"
    ]
}

IMPORTANT: Ensure the output is strictly parseable JSON."""

    logger.log(str(os.path.join(FOLDER_NAME)))

    # iterate each file in the folder
    output_json = {}
    for filename in os.listdir(os.path.join(FOLDER_NAME)):
        
        logger.log(f"Currently at {filename}")
        
        if ("change" not in filename.lower()):
            logger.log(f"{filename} does not have the keyword 'change'")
            logger.log(f"Skipping {filename}")
            continue
        
        # construct the payload
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": PROMPT,
                        },
                    ]
                }
            ],
            "stream": False,
            "return_progress": False,
            "reasoning_format": "auto",
            "temperature": 1.0,
            "max_tokens": -1,
            "dynatemp_range": 0,
            "dynatemp_exponent": 1,
            "top_k": 20,
            "top_p": 0.95,
            "min_p": 0,
            "xtc_probability": 0,
            "xtc_threshold": 0.1,
            "typ_p": 1,
            "repeat_last_n": 64,
            "repeat_penalty": 1,
            "presence_penalty": 1.5,
            "frequency_penalty": 0,
            "dry_multiplier": 0,
            "dry_base": 1.75,
            "dry_allowed_length": 2,
            "dry_penalty_last_n": -1,
            "samplers": [
                "penalties",
                "dry",
                "top_n_sigma",
                "top_k",
                "typ_p",
                "top_p",
                "min_p",
                "xtc",
                "temperature"
            ],
            "timings_per_token": True,
        }
                
        # get the input file
        # filename = "Change_Implemetation_RejectRecycleOFF.pdf"
        input_file = os.path.join("inputs", filename)

        # convert PDF to images
        images = convert_from_path(input_file, dpi=300, fmt="png")
        for index, image in enumerate(images):
            
            logger.log(f"Converting Image to Base64: [{index + 1}/{len(images)}]")
            
            # convert to Base64
            buffered = BytesIO()
            image.save(buffered, format='PNG')
            base64_img = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            # construct the image payload
            img_payload = {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{base64_img}"
                }
            }
            payload.get("messages")[0].get("content").append(img_payload)
            
        logger.log("Converted PDF to Images successfully")
        logger.log("Sending prompt posted to URL")

        # create the request
        response = requests.post(
            url=URL,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0"
            },
            json=payload,
            stream=False
        )
        
        logger.log("Getting result from URL")

        # stream the response
        if response.status_code == 200:
            
            # get response in JSON format
            data = response.json()
            
            # get the actual content
            content = data['choices'][0]['message']['content']
            try:
                json_content = json.loads(content)
                output_json[filename] = json_content # add to overall json output
                
                # write to the file
                with open(os.path.join("outputs", f"{filename}.json"), "w") as fp:
                    json.dump(output_json, fp)
                logger.log("Write to file successful")
            
            except json.decoder.JSONDecodeError as e:
                logger.log("Failed to parse content to JSON format")
                
                # write as a text string
                with open(os.path.join("outputs", f"{filename}.txt"), "w") as f:
                    f.write(content)
            
            finally:
                response.close()
            