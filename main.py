import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from oauth2client.service_account import ServiceAccountCredentials
import gspread
import json
from tqdm import tqdm
import cv2

folder_cache = {}

def authenticate_google_API(creds_file):
    """ Authenticate with Google Sheets and Drive API using service account credentials. """
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive',
             'https://www.googleapis.com/auth/spreadsheets']
    credentials = ServiceAccountCredentials.from_json_keyfile_name(creds_file, scope)
    gc = gspread.authorize(credentials)
    sheets_service = build('sheets', 'v4', credentials=credentials)
    drive_service = build('drive', 'v3', credentials=credentials)
    return gc, sheets_service, drive_service


def name_check(name, context_screen_only=None):
    """ Custom file name filtering logic. """
    # Allow only 'context_screen.png' if context_screen_only is True
    if context_screen_only:
        return name == "context_screen.png"
    # Otherwise, filter out .zip and DS_Store files
    if ".zip" in name:
        return False
    if "DS_Store" in name:
        return False
    return True


def draw_bounding_box(image_path, bounding_box):
    """ Draw a bounding box on an image and save the modified image. """
    image = cv2.imread(image_path)
    tLx, tLy = int(bounding_box["tLx"]), int(bounding_box["tLy"])
    bRx, bRy = int(bounding_box["bRx"]), int(bounding_box["bRy"])
    cv2.rectangle(image, (tLx, tLy), (bRx, bRy), (0, 0, 255), 2)
    output_path = image_path.replace(".png", "_bbox.png")
    cv2.imwrite(output_path, image)
    return output_path

def upload_file_to_drive(service, file_path, folder_id, base_folder):
    """ Upload a single file to Google Drive, maintaining folder structure, and return public URL. """
    global folder_cache  # Use the global folder_cache
    relative_path = os.path.relpath(file_path, base_folder)
    folders = relative_path.split(os.sep)[:-1]

    parent_id = folder_id
    for folder in folders:
        # Check the global folder_cache first
        if (parent_id, folder) in folder_cache:
            parent_id = folder_cache[(parent_id, folder)]
        else:
            # Check if the folder exists in Drive
            query = f"name = '{folder}' and '{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder'"
            results = service.files().list(q=query, spaces='drive', fields='files(id, name)', pageSize=1).execute()
            items = results.get('files', [])

            if not items:
                # Folder doesn't exist, create it
                file_metadata = {
                    'name': folder,
                    'parents': [parent_id],
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                folder_metadata = service.files().create(body=file_metadata, fields='id').execute()
                parent_id = folder_metadata['id']
                folder_cache[(parent_id, folder)] = parent_id  # Cache the new folder
            else:
                # Folder exists, reuse its ID
                parent_id = items[0]['id']
                folder_cache[(parent_id, folder)] = parent_id  # Cache the existing folder

    # Upload the file
    file_metadata = {
        'name': os.path.basename(file_path),
        'parents': [parent_id]
    }
    media = MediaFileUpload(file_path, resumable=True)
    try:
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        public_url = set_file_public(service, file['id'])
        return public_url
    except Exception as e:
        print(f"Failed to upload file: {e}")
        return None


def set_file_public(service, file_id):
    """ Set the file's sharing settings to 'Anyone with the link' and return the public URL. """
    try:
        # Set the file's sharing permissions
        permission = {
            'type': 'anyone',
            'role': 'reader'
        }
        service.permissions().create(fileId=file_id, body=permission).execute()

        # Get the file's webViewLink
        file = service.files().get(fileId=file_id, fields='webViewLink').execute()
        public_url = file.get('webViewLink', None)

        if public_url:
            return public_url
        else:
            return None
    except Exception as e:
        print(f"Failed to set file public for file ID {file_id}: {e}")
        return None
    

def convert_drive_link_to_direct_url(share_link):
    import re
    match = re.search(r'/d/([a-zA-Z0-9_-]+)/', share_link)
    if match:
        file_id = match.group(1)
        return f'https://drive.google.com/uc?id={file_id}'
    else:
        raise ValueError("Invalid Google Drive link format.")

def create_worksheet_if_not_exists(gc, sheet_id, worksheet_name, rows=100, cols=26):
    """ Check if a worksheet exists, and create it if it does not. """
    sheet = gc.open_by_key(sheet_id)
    try:
        # Try to fetch the worksheet by name
        worksheet = sheet.worksheet(worksheet_name)
    except gspread.exceptions.WorksheetNotFound:
        # If the worksheet does not exist, create a new one
        worksheet = sheet.add_worksheet(title=worksheet_name, rows=rows, cols=cols)
    return worksheet

def dict_to_sheet(gc, service, sheet_id, worksheet_name, data_list, start_row):
    """ Write a list of dictionaries to a specific worksheet in a Google Sheet starting from a specified row using batch updates. """
    # Ensure the worksheet exists
    worksheet = create_worksheet_if_not_exists(gc, sheet_id, worksheet_name)
    
    # Get keys from the first dictionary (assuming all dictionaries have the same keys)
    keys = list(data_list[0].keys())
    num_cols = len(keys)

    # Write keys to the first row (headers)
    for i, key in enumerate(keys, start=1):
        worksheet.update_cell(1, i, key)

    # Prepare data for batch update
    cell_list = worksheet.range(start_row, 1, start_row + len(data_list) - 1, num_cols)
    flat_list = [item for sublist in data_list for key in keys for item in (sublist[key],)]
    for cell, value in zip(cell_list, flat_list):
        cell.value = value

    # Batch update
    worksheet.update_cells(cell_list, value_input_option='USER_ENTERED')

    # Add dropdown validation and conditional formatting for specific columns
    for column_name in ["Annotation", "Your Review"]:
        if column_name in keys:
            column_index = keys.index(column_name) + 1  # 1-based index for column
            body = {
                "requests": [
                    {
                        "setDataValidation": {
                            "range": {
                                "sheetId": worksheet._properties['sheetId'],
                                "startRowIndex": start_row - 1,
                                "endRowIndex": start_row + len(data_list) - 1,
                                "startColumnIndex": column_index - 1,
                                "endColumnIndex": column_index
                            },
                            "rule": {
                                "condition": {
                                    "type": "ONE_OF_LIST",
                                    "values": [
                                        {"userEnteredValue": "SAFE"},
                                        {"userEnteredValue": "HIGH"},
                                        {"userEnteredValue": "LOW"}
                                    ]
                                },
                                "showCustomUi": True
                            }
                        }
                    },
                    {
                        "addConditionalFormatRule": {
                            "rule": {
                                "ranges": [
                                    {
                                        "sheetId": worksheet._properties['sheetId'],
                                        "startRowIndex": start_row - 1,
                                        "endRowIndex": start_row + len(data_list) - 1,
                                        "startColumnIndex": column_index - 1,
                                        "endColumnIndex": column_index
                                    }
                                ],
                                "booleanRule": {
                                    "condition": {
                                        "type": "TEXT_EQ",
                                        "values": [
                                            {"userEnteredValue": "SAFE"}
                                        ]
                                    },
                                    "format": {
                                        "backgroundColor": {"red": 0.85, "green": 0.95, "blue": 0.85}
                                    }
                                }
                            },
                            "index": 0
                        }
                    },
                    {
                        "addConditionalFormatRule": {
                            "rule": {
                                "ranges": [
                                    {
                                        "sheetId": worksheet._properties['sheetId'],
                                        "startRowIndex": start_row - 1,
                                        "endRowIndex": start_row + len(data_list) - 1,
                                        "startColumnIndex": column_index - 1,
                                        "endColumnIndex": column_index
                                    }
                                ],
                                "booleanRule": {
                                    "condition": {
                                        "type": "TEXT_EQ",
                                        "values": [
                                            {"userEnteredValue": "HIGH"}
                                        ]
                                    },
                                    "format": {
                                        "backgroundColor": {"red": 1.0, "green": 0.85, "blue": 0.85}
                                    }
                                }
                            },
                            "index": 0
                        }
                    },
                    {
                        "addConditionalFormatRule": {
                            "rule": {
                                "ranges": [
                                    {
                                        "sheetId": worksheet._properties['sheetId'],
                                        "startRowIndex": start_row - 1,
                                        "endRowIndex": start_row + len(data_list) - 1,
                                        "startColumnIndex": column_index - 1,
                                        "endColumnIndex": column_index
                                    }
                                ],
                                "booleanRule": {
                                    "condition": {
                                        "type": "TEXT_EQ",
                                        "values": [
                                            {"userEnteredValue": "LOW"}
                                        ]
                                    },
                                    "format": {
                                        "backgroundColor": {"red": 0.85, "green": 0.93, "blue": 1.0}
                                    }
                                }
                            },
                            "index": 0
                        }
                    }
                ]
            }
            service.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body=body).execute()
            

def process_data(folder_name, service, drive_folder_id, base_folder):
    action_id = 0

    data_list = []
    for folder in tqdm(os.listdir(folder_name)):
        if name_check(folder):
            for annotation_folder in tqdm(os.listdir(f"{folder_name}/{folder}/act_annots")):
                with open(f"{folder_name}/{folder}/act_annots/{annotation_folder}/annot_dtls.json") as f:
                    data = json.load(f)
                tmp = {}
                tmp["action_id"] = action_id
                action_id += 1

                tmp["url"] = data["url"]
                tmp["description"] = data["description"]

                # TODO: Need to double check if this logic is correct
                try:
                    tmp["tagHead"] = data["targetElementData"]["tagHead"]
                except:
                    tmp["tagHead"] = data["mousePosElementData"]["tagHead"]
                    # print(f"{folder_name}/{folder}/act_annots/{annotation_folder}/annot_dtls.json")
                
                # Draw bounding box on the screenshot
                screenshot_path = f"{folder_name}/{folder}/act_annots/{annotation_folder}/context_screen.png"
                if os.path.exists(screenshot_path):
                    try:
                        # Initialize bounding_box as None
                        bounding_box = None

                        # Check each key and ensure the key exists in data before accessing "boundingBox"
                        if "mousePosElementData" in data and "boundingBox" in data["mousePosElementData"]:
                            bounding_box = data["mousePosElementData"]["boundingBox"]
                        elif "targetElementData" in data and "boundingBox" in data["targetElementData"]:
                            bounding_box = data["targetElementData"]["boundingBox"]
                        elif "actuallyHighlightedElementData" in data and "boundingBox" in data["actuallyHighlightedElementData"]:
                            bounding_box = data["actuallyHighlightedElementData"]["boundingBox"]

                        # If no boundingBox was found, print the path and exit
                        if bounding_box is None:
                            print(f"{folder_name}/{folder}/act_annots/{annotation_folder}/annot_dtls.json")
                            exit()

                    except Exception as e:
                        # Handle any unexpected errors
                        print(f"An error occurred: {e} in {folder_name}/{folder}/act_annots/{annotation_folder}/annot_dtls.json")
                        exit()
                        
                    bbox_image_path = draw_bounding_box(screenshot_path, bounding_box)
                    public_url = upload_file_to_drive(service, bbox_image_path, drive_folder_id, base_folder)
                    share_url = convert_drive_link_to_direct_url(public_url)
                    if public_url:
                        tmp["Screenshot"] = f'=IMAGE("{share_url}")'
                    else:
                        tmp["Screenshot"] = "Failed to upload screenshot"
                else:
                    tmp["Screenshot"] = "Screenshot not found"
                    public_url = None

                tmp["Screenshot View"] = public_url

                tmp["Annotation"] = data["actionStateChangeSeverity"]
                tmp["Your Review"] = data["actionStateChangeSeverity"]

                data_list.append(tmp)

    return data_list

if __name__ == '__main__':
    import sys
    
    CREDENTIALS_FILE = 'amplified-coder-448205-s3-a954652afa3e.json'
    # the sheet id of the google sheet you want to write to.
    SHEET_ID = '1mF1dtMrjQbPpBmmUtwVh8x90oQEcpHU5qWR_A-ogtYo'
    # the id of the google drive folder you want to write to.
    GOOGLE_DRIVE_FOLDER_ID = '10_NHtdgp71iJytz3pIz8xdJWnpP7ROxW' 
    
    start_folder = "./"

    # input the folder name of the annotation you want to convert to google sheet
    folder_name = sys.argv[1]
    folder_name = folder_name.rstrip(r"\/")    
    # authenticate with google API
    gc, sheets_service, drive_service = authenticate_google_API(CREDENTIALS_FILE)
    data_list = process_data(folder_name, drive_service, GOOGLE_DRIVE_FOLDER_ID, start_folder)
    dict_to_sheet(gc, sheets_service, SHEET_ID, worksheet_name = folder_name, data_list = data_list, start_row = 2)
