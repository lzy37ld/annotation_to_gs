# Instructions for Using the Annotation Script

1. Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```

2. 
   1. Place all the zip files containing the annotation results in the current directory.
   2. Put the [credential file](https://drive.google.com/drive/u/3/folders/1SS7jzhF-OzVN1s0cgS7KREADbCzhaKoa) in the current dir. Please directly request permission via this link.

3. Run the `unzip.sh` script:
    ```bash
    bash unzip.sh <folder_name>
    ```
    This ensures that all zip files are fully extracted.

    For example, `bash unzip.sh eventbrite`

4. Run the following command:
    ```python
    python main.py <folder_name>
    ```
    This command converts the annotation files into a Google Sheet (examples are provided [here](https://docs.google.com/spreadsheets/d/1mF1dtMrjQbPpBmmUtwVh8x90oQEcpHU5qWR_A-ogtYo/edit?gid=1681197158#gid=1681197158)). 

    Each sheet is named exactly as `<folder_name>`.

    For example, `python main.py eventbrite`
---

## Logic

1. Extract all zip files.
2. Upload all `context_screen.png` files to Google Drive using the credential file, which connects to Google Drive and Google Sheets.
3. Convert each annotation into a Google Sheet.
4. Currently, the google drive folder is [here](https://drive.google.com/drive/u/3/folders/10_NHtdgp71iJytz3pIz8xdJWnpP7ROxW) and the goole sheet is [here](https://docs.google.com/spreadsheets/d/1mF1dtMrjQbPpBmmUtwVh8x90oQEcpHU5qWR_A-ogtYo/edit?gid=1681197158#gid=1681197158).

---

## How It Works

A new Google account was created with a linked service account. This script uses the service account to upload images to Google Drive and transfer each annotation into a Google Sheet.

Each Google account has 15GB of Google Drive storage, which should suffice for all current and future annotation results.

---

## Notes

1. Let me know if you need the account/password for this new Google account.

2. (**IMPORTANT**) Please do not disclose the credential file in any cases! Otherwise, the credential file will be disabled automatically.