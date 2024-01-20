import imaplib
import email
import requests
import os
import configparser
import re
import html
import html2text
from bs4 import BeautifulSoup
import argparse
import tempfile

######## INITIALIZATION ########
# Initialize parser
parser = argparse.ArgumentParser(description='Process some emails.')
parser.add_argument('-c', '--config', type=str, help='Path to configuration file')

# Read arguments from the command line
args = parser.parse_args()

# If --config is provided, use it as the config path, otherwise default to 'config.ini'
config_path = args.config if args.config else 'config.ini'
#print (f"Using config path: {config_path}")

# Counters for unseen emails and Joplin notes
unseen_emails_count = 0
joplin_notes_count = 0

######## CONFIGURATION ########

# Read configuration from the config.ini file located one directory up
config = configparser.ConfigParser()
config.read(config_path)  # Updated location of the config file

# IMAP and Joplin configuration from the config file
imap_server = config.get('IMAP', 'server')
imap_user = config.get('IMAP', 'user')
imap_pass = config.get('IMAP', 'password')
imap_folder = config.get('IMAP', 'folder')
imap_processed_folder = config.get('IMAP', 'processed_folder', fallback=None)

joplin_token = config.get('Joplin', 'token')
joplin_notebook_name = config.get('Joplin', 'notebook_name')  # Specify by name in config
joplin_api_url = config.get('Joplin', 'api_url')

# print("Configuration loaded successfully.")

######## FUNCTIONS ########

# FUNCTION: Upload an attachment to Joplin
def upload_attachment_to_joplin(file_path, file_name, is_image=False):
    try:
        # print(f"Uploading {'image' if is_image else 'file'}: {file_name} from {file_path}")
        files = {
            'data': (file_name, open(file_path, 'rb')),
            'props': (None, '{"title":"' + file_name + '"}'),
        }
        r = requests.post(f'{joplin_api_url}/resources?token={joplin_token}', files=files)
        # print(f"Upload request status: {r.status_code}")
        if r.status_code == 200:
            resource_id = r.json().get('id')
            #print(f"Uploaded successfully. Resource ID: {resource_id}")
            
            # Return the formatted link based on whether it's an image or file
            return f"![{file_name}](:/{resource_id})" if is_image else f"[{file_name}](:/{resource_id})"
        else:
            print(f"Failed to upload. Response: {r.text}")
    except Exception as e:
        print(f"Error uploading: {e}")
    finally:
        if 'data' in files and files['data'][1]:
            files['data'][1].close()  # Ensure file is closed after upload
    return ""

# FUNCTION: Get Notebook ID
def get_notebook_id(notebook_name):
    try:
        response = requests.get(f'{joplin_api_url}/folders?token={joplin_token}')
        response.raise_for_status()
        data = response.json()

        # Access the 'items' key from the response which contains the list of notebooks
        notebooks = data.get('items', [])

        # print(f"Looking for notebook named: '{notebook_name}'.")
        # print("Available notebooks:")

        # Iterate through notebooks and match by name
        for notebook in notebooks:
            # Print each notebook title and id for diagnostics
            # print(f"- Found '{notebook.get('title', 'No Title')}' (ID: {notebook.get('id', 'No ID')})")

            # Check if the current notebook title matches the desired notebook name
            if notebook.get('title', '').lower() == notebook_name.lower():
               # print(f"Match found for notebook '{notebook_name}'.")
                return notebook['id']

        # print(f"No match found for: '{notebook_name}'. Available notebooks are listed above.")

    except requests.RequestException as e:
        print(f"Error accessing Joplin API: {e}")
    except ValueError as e:
        print(f"Error parsing Joplin response: {e}")
    return None

# FUNCTION: Remove irregular spaces
def remove_irregular_spaces(text):
    # Replace any sequence of whitespace characters with a single space
    return re.sub(r'\s+', ' ', text).strip()

# FUNCTION: Remove indentation for forwarded emails
def remove_forwarded_indentations(email_content, content_type):
    if content_type == 'text/plain':
        # Regular expression to find and remove typical forwarding characters like '>'
        return re.sub(r'^[>|]+\s?', '', email_content, flags=re.MULTILINE)
    elif content_type == 'text/html':
        # Use BeautifulSoup to parse HTML content
        soup = BeautifulSoup(email_content, 'html.parser')

        # Find all blockquote elements with "Forwarded in them"
        blockquotes = soup.find_all('blockquote')
        # print("Processing HTML for forwarding formatting in blockquotes...")
        for blockquote in blockquotes:
            if "Forwarded" in blockquote.get_text(strip=True):
                blockquote.unwrap()  # Remove blockquote elements

        # Find all div elements and check for "Forwarded message"
        divs = soup.find_all('div')
        # print("Processing HTML for forwarding formatting in divs...")
        for div in divs:
            if "Forwarded" in div.get_text(strip=True):
                for blockquote in blockquotes:
                            # Check if blockquote is still part of the HTML tree
                    if blockquote.parent is not None:
                        # This will unwrap the content of blockquote
                        blockquote.unwrap()
        # Return the cleaned HTML as a string
        return str(soup)
    else:
        # If the content type is neither text/plain nor text/html, return the original content
        return email_content

# FUNCTION: Convert HTML Table to Markdown
def html_table_to_markdown(table):
    markdown = ""
    rows = table.find_all('tr')
    if not rows:  # Check if the list is empty
        return table  # Or return whatever makes sense in your context

    # Extract headers if present
    headers = rows[0].find_all(['th', 'td'])
    header_row = "| " + " | ".join([header.get_text(strip=True) for header in headers]) + " |"
    markdown += header_row + "\n"

    # Separator row for Markdown table
    markdown += "| " + " | ".join(['---' for _ in headers]) + " |" + "\n"

    # Process each row
    for row in rows[1:]:  # Skip the header row
        cells = row.find_all(['td', 'th'])
        row_markdown = "| " + " | ".join([cell.get_text(strip=True) for cell in cells]) + " |"
        markdown += row_markdown + "\n"
    return markdown

# FUNCTION: Convert HTML Text To Markdown
def convert_html_to_markdown(html_content):
    # Remove <center> tags from the HTML
    html_content = remove_bad_tags(html_content)

    soup = BeautifulSoup(html_content, 'html.parser')
    # Initialize the converter
    text_maker = html2text.HTML2Text()
    text_maker.bypass_tables = True  # Bypass the default table conversion
    text_maker.ignore_links = False  # Adjust options as necessary
    text_maker.body_width = 0  # Setting it to 0 will prevent word wrapping

    # Convert non-table parts
    markdown = text_maker.handle(str(soup))

    # Manually convert tables
    for table in soup.find_all('table'):
        markdown_table = html_table_to_markdown(table)
        markdown = markdown.replace(str(table), str(markdown_table))
    
    return markdown

# FUNCTION: Remove problematic tags
def remove_bad_tags(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all <center> tags and unwrap them
    for center_tag in soup.find_all('center'):
        if center_tag.parent is not None:
            center_tag.unwrap()

    return str(soup)

# FUNCTION: Remove leftover tags from Markdown

def remove_tags_from_markdown(markdown_content):
    # Parsing the HTML content
    soup = BeautifulSoup(markdown_content, 'html.parser')

    # Tags to remove
    tags_to_remove = ['table', 'tr', 'td']

    # Finding and removing the tags
    for tag in tags_to_remove:
        for tag_instance in soup.find_all(tag):
                tag_instance.decompose()

    # Return the modified content
    return str(soup)

# FUNCTION: Decode MIME Words
def decode_mime_words(s):
    decoded_words = email.header.decode_header(s)
    # Concatenate decoded words.
    # Decoding only when the word is a byte string, otherwise, it's already a string.
    return ''.join(word.decode(encoding or 'utf-8') if isinstance(word, bytes) else word
                   for word, encoding in decoded_words)

# FUNCTION: Process the email body
def process_email_body(msg):
    text_body = None
    html_body = None

    if msg.is_multipart():
        for part in msg.walk():
            # Look for text/plain and text/html parts
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            if content_type == "text/plain" and "attachment" not in content_disposition:
                text_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
            elif content_type == "text/html" and "attachment" not in content_disposition:
                html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')

    else:  # If the email is not multipart
        if msg.get_content_type() == "text/plain":
            text_body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        elif msg.get_content_type() == "text/html":
            html_body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
    
    # Clean up the HTML content before converting it to Markdown
    if html_body:
        noforwards = remove_forwarded_indentations(html_body, "text/html")
        cleaned_html = convert_html_to_markdown(noforwards)
        # Remove "_​_" characters
        cleaned_html = cleaned_html.replace('_​_[ _ ', '[')
        # Not using this function right now
        # cleaned_html2 = remove_tags_from_markdown(cleaned_html)
        # write_body_to_markdown(cleaned_html)
        print("Converted HTML to Markdown.")
        return cleaned_html
        
    elif text_body:
        # Clean up plain text
        noforwards = remove_forwarded_indentations(text_body, "text/plain")
        cleaned_plain = remove_irregular_spaces(noforwards)
        print("Converted Plain Text to Markdown.")
        return cleaned_plain 

    return "No content could be decoded."

# FUNCTION: Write Email Body to Markdown File in tmp directory
def write_body_to_markdown(body_content):

    # Define the path for the markdown file in the tmp directory
    
    # use system temp directory
    # tmp_md_path = os.path.join(tempfile.gettempdir(), "email_body.md")

    # use relative /tmp dir instead
    tmp_md_path = os.path.join('/tmp', "email_body.md")

    # Write the body content to a markdown file
    with open(tmp_md_path, 'w') as md_file:
        md_file.write(body_content)

    print(f"Body content written to {tmp_md_path}")

######## MAIN PROCESSING ########

# Get Joplin notebook ID from the name
joplin_notebook_id = get_notebook_id(joplin_notebook_name)
if joplin_notebook_id is None:
    print(f"Error: Notebook '{joplin_notebook_name}' not found in Joplin.")
    exit()

# print(f"Using notebook: {joplin_notebook_name} with ID {joplin_notebook_id}")

# Connect to IMAP server
print("Connecting to IMAP server.")
mail = imaplib.IMAP4_SSL(imap_server)
mail.login(imap_user, imap_pass)
# print(f"Logged in as {imap_user}")

mail_folder = imap_folder # Specify the folder here
mail.select(mail_folder)
# print(f"Selected mail folder: {mail_folder}")

# Search for unseen emails
#print("Searching for unseen emails...")
result, data = mail.uid('search', None, 'UNSEEN')

# MAIN Procressing

if result == 'OK' and data[0]:

    for num in data[0].split():
        unseen_emails_count += 1  # Incrementing unseen emails count
        # print(f"Processing email number: {num.decode()}")
        #OLD: result, data = mail.fetch(num, '(RFC822)')

        #Better handling version
        try:
            result, data = mail.uid('fetch', num, '(RFC822)')
            if result != 'OK':
                print(f"Error fetching email with UID {num.decode()}: {result}")
                continue
        except imaplib.IMAP4.error as e:
            print(f"IMAP4 error fetching email with UID {num.decode()}: {e}")
            continue

        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)
        # Initialize an empty list to hold attachment links
        attachment_links = []

        subject = msg['subject']
        if subject is not None:
            decoded_subject = decode_mime_words(subject)
        else:
         # Handle the case where subject is None, e.g., set to a default value or log a warning
            decoded_subject = "Untitled"
        print(f"Processing email with Subject: {decoded_subject}")
        
        # Email parsing for body and attachments
        #body = ""
        
        # When processing the email body
        body = process_email_body(msg)

        # When iterating over the parts of the email:
        for part in msg.walk():
            content_disposition = str(part.get("Content-Disposition"))
            content_id = str(part.get("Content-ID"))

            if part.get_filename():  # We have an attachment
                file_name = part.get_filename()
                file_path = os.path.join('/tmp', file_name)
                with open(file_path, 'wb') as f:
                    f.write(part.get_payload(decode=True))
                
                # Check if it's an inline image (embedded) or just a regular attachment
                is_image = part.get_content_maintype() == 'image'
                link = upload_attachment_to_joplin(file_path, file_name, is_image)
                attachment_links.append(link)

        # Create the note in Joplin with the note content including attachments if available
        
        # Assemble the note content
        note_content = ""
        
        if attachment_links:  # Check if there are any attachments
            note_content += "# Attachments\n" + '\n'.join(attachment_links) + "\n\n"
        # Add a header for the message body and then the body content
        note_content += f'# {decoded_subject}\n\n{body}\n\n'
        payload = {'title': decoded_subject, 'body': note_content, 'parent_id': joplin_notebook_id}
        r = requests.post(f'{joplin_api_url}/notes?token={joplin_token}', json=payload)

        # Check the response from Joplin API
        if r.status_code == 200:
            joplin_notes_count += 1  # Incrementing Joplin notes count
            print("Note created successfully in Joplin.")
        else:
            print(f"Failed to create note in Joplin. Status Code: {r.status_code}")

        # Optional: Mark the email as seen after creating the note
        mail.uid('store', num, '+FLAGS', '\\Seen')
        # print("Email marked as seen.")

        # Optional: Keep as Unread
        # mail.uid('store', num, '-FLAGS', '\\Seen')
               
        if imap_processed_folder:  # Check if the processed_folder is specified in the config
            # Use the UID to move the email to the processed_folder
            result_2, _ = mail.uid('MOVE', num, imap_processed_folder)
            print(f"Moved email UID {num.decode()} to folder {imap_processed_folder}")
            if result_2 != 'OK':
                print(f"Error moving email UID {num.decode()} to folder {imap_processed_folder}")

else:
    print("No unseen emails found.")

mail.logout()
print("Logged out successfully.")

# Output the counts
print(f'Unseen emails processed: {unseen_emails_count}')
print(f'Joplin notes created: {joplin_notes_count}')
print('--------------')
